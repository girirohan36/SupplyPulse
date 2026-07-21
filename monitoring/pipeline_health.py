"""
Pipeline Health Monitor — Freshness, volume anomaly, and null-rate checks.

Runs as the FINAL task in the Airflow DAG. Posts to Slack on any failure.

Checks implemented:
  1. freshness_check     — is data stale beyond SLA?
  2. volume_anomaly      — is today's row count >3 std deviations below the 30-day avg?
  3. null_rate_check     — are critical fields above an acceptable null threshold?

Design principle: checks should WARN loudly rather than fail silently.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
import snowflake.connector

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: str           # "critical" | "warning"
    message: str
    actual_value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class HealthReport:
    checked_at: datetime = field(default_factory=datetime.utcnow)
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def critical_failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == "critical"]

    def summary(self) -> dict:
        return {
            "checked_at": self.checked_at.isoformat(),
            "overall_passed": self.passed,
            "total_checks": len(self.results),
            "passed_checks": sum(1 for r in self.results if r.passed),
            "critical_failures": [r.name for r in self.critical_failures],
            "results": [vars(r) for r in self.results],
        }


class PipelineHealthMonitor:

    FRESHNESS_SLA_HOURS = 8         # data must be no older than 8 hours
    VOLUME_ANOMALY_STDDEV = 3.0     # flag if count is >3 std devs below 30-day avg
    MAX_NULL_RATE = 0.02            # allow up to 2% nulls on critical fields

    def __init__(self, snowflake_conn_params: dict, slack_webhook_url: str):
        self.conn_params = snowflake_conn_params
        self.slack_webhook = slack_webhook_url

    def _get_conn(self):
        return snowflake.connector.connect(**self.conn_params)

    # -----------------------------------------------------------------------
    # Individual checks
    # -----------------------------------------------------------------------

    def freshness_check(self) -> CheckResult:
        """
        How stale is the most recent data in the Bronze layer?
        Triggered after every load to catch silent extraction failures.
        """
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT DATEDIFF('hour', MAX(dbt_loaded_at), CURRENT_TIMESTAMP())
            FROM ANALYTICS.BRONZE.BRONZE_GITHUB_PRS
        """)
        hours_stale = cur.fetchone()[0] or 9999
        cur.close(); conn.close()

        passed = hours_stale <= self.FRESHNESS_SLA_HOURS
        return CheckResult(
            name="freshness_check",
            passed=passed,
            severity="critical",
            message=(
                f"Data is {hours_stale}h old (SLA: {self.FRESHNESS_SLA_HOURS}h)"
                if not passed
                else f"Data freshness OK: {hours_stale}h old"
            ),
            actual_value=hours_stale,
            threshold=self.FRESHNESS_SLA_HOURS,
        )

    def volume_anomaly_check(self) -> CheckResult:
        """
        Detect sudden drops in daily PR volume using a z-score approach.

        A 30-day rolling avg ± stddev baseline is computed, then today's
        count is compared. Drops > 3 std devs below the mean = alert.

        This caught a real incident: the GitHub token expired silently
        and we were loading 0 rows — no extract failure, just empty data.
        """
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            WITH daily_counts AS (
                SELECT
                    DATE(dbt_loaded_at)     AS load_date,
                    COUNT(*)                AS daily_rows
                FROM ANALYTICS.BRONZE.BRONZE_GITHUB_PRS
                WHERE dbt_loaded_at >= DATEADD('day', -31, CURRENT_DATE())
                GROUP BY 1
            ),
            stats AS (
                SELECT
                    AVG(daily_rows)         AS avg_rows,
                    STDDEV(daily_rows)      AS stddev_rows,
                    MAX(CASE WHEN load_date = CURRENT_DATE()
                             THEN daily_rows END) AS today_rows
                FROM daily_counts
                WHERE load_date < CURRENT_DATE()    -- baseline excludes today
            )
            SELECT
                today_rows,
                avg_rows,
                stddev_rows,
                CASE
                    WHEN stddev_rows > 0
                    THEN (avg_rows - today_rows) / stddev_rows
                    ELSE 0
                END AS z_score
            FROM stats
        """)
        row = cur.fetchone()
        cur.close(); conn.close()

        if not row or row[0] is None:
            return CheckResult(
                name="volume_anomaly_check",
                passed=True,
                severity="warning",
                message="Not enough history for volume baseline (< 2 days)",
            )

        today_rows, avg_rows, stddev_rows, z_score = row
        passed = z_score < self.VOLUME_ANOMALY_STDDEV

        return CheckResult(
            name="volume_anomaly_check",
            passed=passed,
            severity="critical",
            message=(
                f"ANOMALY: today={today_rows} rows (avg={avg_rows:.0f}, z={z_score:.1f})"
                if not passed
                else f"Volume OK: {today_rows} rows today (avg={avg_rows:.0f})"
            ),
            actual_value=z_score,
            threshold=self.VOLUME_ANOMALY_STDDEV,
        )

    def null_rate_check(self) -> CheckResult:
        """Check that critical fields stay below the acceptable null threshold."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT
                SUM(CASE WHEN created_at IS NULL THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS null_created_at_rate,
                SUM(CASE WHEN author_login IS NULL THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS null_author_rate
            FROM ANALYTICS.BRONZE.BRONZE_GITHUB_PRS
            WHERE dbt_loaded_at >= DATEADD('hour', -25, CURRENT_TIMESTAMP())
        """)
        null_created, null_author = cur.fetchone()
        cur.close(); conn.close()

        max_null_rate = max(null_created or 0, null_author or 0)
        passed = max_null_rate <= self.MAX_NULL_RATE

        return CheckResult(
            name="null_rate_check",
            passed=passed,
            severity="warning",
            message=(
                f"High null rates: created_at={null_created:.1%}, author={null_author:.1%}"
                if not passed
                else f"Null rates OK: created_at={null_created:.1%}, author={null_author:.1%}"
            ),
            actual_value=max_null_rate,
            threshold=self.MAX_NULL_RATE,
        )

    # -----------------------------------------------------------------------
    # Run all checks & alert
    # -----------------------------------------------------------------------

    def run_all_checks(self) -> HealthReport:
        report = HealthReport()
        checks = [
            self.freshness_check,
            self.volume_anomaly_check,
            self.null_rate_check,
        ]
        for check_fn in checks:
            try:
                result = check_fn()
                report.results.append(result)
                status = "✅" if result.passed else "❌"
                logger.info(f"{status} {result.name}: {result.message}")
            except Exception as e:
                report.results.append(CheckResult(
                    name=check_fn.__name__,
                    passed=False,
                    severity="critical",
                    message=f"Check raised exception: {e}",
                ))
                logger.error(f"Check {check_fn.__name__} failed with exception", exc_info=True)

        if not report.passed:
            self._alert_slack(report)

        return report

    def _alert_slack(self, report: HealthReport):
        """Post a Slack alert for any pipeline health failure."""
        failures = [r for r in report.results if not r.passed]
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 DevMetrics Pipeline Health Alert"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{len(failures)} check(s) failed* at `{report.checked_at.strftime('%Y-%m-%d %H:%M UTC')}`"
                }
            }
        ]
        for r in failures:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{r.name}* ({r.severity})\n{r.message}"}
            })

        try:
            resp = requests.post(self.slack_webhook, json={"blocks": blocks}, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

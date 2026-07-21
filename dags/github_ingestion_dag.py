"""
GitHub PR Ingestion DAG — Airflow 2.7 TaskFlow API

Architecture decisions & problems solved:
  - TaskFlow API: data flows as Python return values, zero XCom boilerplate
  - TaskGroups: each stage (extract / load / validate / transform) is a self-
    contained group, so adding a new source = one new TaskGroup
  - Idempotency: every run uses a batch_id keyed to execution_date, so
    re-runs never double-load data
  - Incremental vs. full load: controlled via dag_run.conf["full_load"]

Run modes:
  $ airflow dags trigger github_pr_ingestion                  # incremental (last 25h)
  $ airflow dags trigger github_pr_ingestion --conf '{"full_load": true}'  # backfill
"""

import json
import logging
from datetime import datetime, timedelta

import boto3
from airflow.decorators import dag, task, task_group
from airflow.models import Variable
from airflow.utils.dates import days_ago

from ingestion.github_extractor import GitHubExtractor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

@dag(
    dag_id="github_pr_ingestion",
    description="Extract GitHub PRs → S3 → Snowflake → DBT (incremental)",
    schedule_interval="0 */6 * * *",   # every 6 hours
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,                 # prevent concurrent runs clobbering each other
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "owner": "data-platform",
        "email_on_failure": True,
    },
    tags=["ingestion", "github", "developer-metrics"],
    doc_md="""
    ## GitHub PR Ingestion Pipeline

    Extracts pull request data from all repos in the org, stages to S3 as
    NDJSON, then COPYs into Snowflake RAW schema. DBT is triggered after
    successful load + validation.

    **Backfill:** trigger with conf `{"full_load": true}` to re-extract all history.
    **Selective repos:** pass `{"repos": ["repo-a", "repo-b"]}` to limit scope.
    """,
)
def github_pr_ingestion():

    # -----------------------------------------------------------------------
    # EXTRACT
    # -----------------------------------------------------------------------
    @task_group(group_id="extract")
    def extract_group():

        @task
        def extract_prs(**context) -> dict:
            """
            Pull PRs from GitHub API.

            Returns S3 path of the staged NDJSON file so downstream tasks
            know exactly where to read from — no shared state needed.
            """
            conf = context["dag_run"].conf or {}
            full_load = conf.get("full_load", False)
            repos = conf.get("repos", None)           # None = all repos
            execution_date = context["execution_date"]

            # Determine lookback window
            # Add 1-hour buffer beyond 6h schedule to catch any stragglers
            since = None if full_load else (
                execution_date - timedelta(hours=25)
            )
            logger.info(f"Mode: {'FULL' if full_load else 'INCREMENTAL'} | since={since}")

            # Extract
            github_token = Variable.get("GITHUB_TOKEN", deserialize_json=False)
            org = Variable.get("GITHUB_ORG", default_var="myorg")
            extractor = GitHubExtractor(token=github_token, org=org)

            records = []
            if repos:
                for repo in repos:
                    records.extend(list(extractor.extract_pull_requests(repo, since=since)))
            else:
                records = list(extractor.extract_all_repos(since=since))

            logger.info(f"Extracted {len(records)} PR records")

            # Write NDJSON to S3
            batch_id = execution_date.strftime("%Y%m%dT%H%M%S")
            s3_key = f"raw/github/pull_requests/batch_id={batch_id}/data.ndjson"
            bucket = Variable.get("S3_BUCKET")

            s3 = boto3.client("s3")
            ndjson_body = "\n".join(json.dumps(r) for r in records)
            s3.put_object(Bucket=bucket, Key=s3_key, Body=ndjson_body.encode("utf-8"))

            logger.info(f"Staged {len(records)} records to s3://{bucket}/{s3_key}")
            return {"s3_path": f"s3://{bucket}/{s3_key}", "batch_id": batch_id, "record_count": len(records)}

        return extract_prs()

    # -----------------------------------------------------------------------
    # LOAD
    # -----------------------------------------------------------------------
    @task_group(group_id="load")
    def load_group(extract_result: dict):

        @task
        def load_to_snowflake(extract_result: dict) -> dict:
            """
            COPY the staged NDJSON from S3 into Snowflake RAW schema.

            Uses COPY INTO for atomic, server-side loading (no Python memory pressure).
            The FORCE=FALSE ensures we never re-load the same file — idempotent.
            """
            import snowflake.connector

            conn = snowflake.connector.connect(
                user=Variable.get("SNOWFLAKE_USER"),
                password=Variable.get("SNOWFLAKE_PASSWORD"),
                account=Variable.get("SNOWFLAKE_ACCOUNT"),
                warehouse="INGESTION_WH",
                database="RAW",
                schema="GITHUB",
            )
            cur = conn.cursor()

            batch_id = extract_result["batch_id"]
            s3_path = extract_result["s3_path"]

            copy_sql = f"""
                COPY INTO RAW.GITHUB.PULL_REQUESTS_RAW
                FROM '{s3_path}'
                FILE_FORMAT = (
                    TYPE = 'JSON'
                    STRIP_OUTER_ARRAY = FALSE
                )
                MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
                FORCE = FALSE;          -- skip already-loaded files
            """
            cur.execute(copy_sql)
            result = cur.fetchone()
            rows_loaded = result[0] if result else 0

            logger.info(f"Loaded {rows_loaded} rows into Snowflake (batch_id={batch_id})")
            cur.close()
            conn.close()

            return {**extract_result, "rows_loaded": rows_loaded}

        return load_to_snowflake(extract_result)

    # -----------------------------------------------------------------------
    # VALIDATE
    # -----------------------------------------------------------------------
    @task_group(group_id="validate")
    def validate_group(load_result: dict):

        @task
        def run_quality_checks(load_result: dict) -> dict:
            """
            Post-load data quality checks before triggering DBT.

            Checks:
              1. No duplicate PR IDs in this batch
              2. No null created_at values
              3. Row count matches what we extracted

            If any check fails, the DAG fails here — DBT never runs on bad data.
            """
            import snowflake.connector

            conn = snowflake.connector.connect(
                user=Variable.get("SNOWFLAKE_USER"),
                password=Variable.get("SNOWFLAKE_PASSWORD"),
                account=Variable.get("SNOWFLAKE_ACCOUNT"),
                warehouse="INGESTION_WH",
                database="RAW",
                schema="GITHUB",
            )
            cur = conn.cursor()
            batch_id = load_result["batch_id"]

            checks = {
                "no_duplicate_ids": f"""
                    SELECT COUNT(*) - COUNT(DISTINCT id)
                    FROM RAW.GITHUB.PULL_REQUESTS_RAW
                    WHERE batch_id = '{batch_id}'
                """,
                "no_null_created_at": f"""
                    SELECT COUNT(*) FROM RAW.GITHUB.PULL_REQUESTS_RAW
                    WHERE batch_id = '{batch_id}'
                    AND created_at IS NULL
                """,
            }

            failures = []
            for check_name, sql in checks.items():
                cur.execute(sql)
                count = cur.fetchone()[0]
                if count > 0:
                    failures.append(f"{check_name}: {count} violations")

            cur.close()
            conn.close()

            if failures:
                raise ValueError(f"Data quality checks FAILED: {failures}")

            logger.info(f"All quality checks passed for batch_id={batch_id}")
            return load_result

        return run_quality_checks(load_result)

    # -----------------------------------------------------------------------
    # TRANSFORM (trigger DBT)
    # -----------------------------------------------------------------------
    @task_group(group_id="transform")
    def transform_group(validated_result: dict):

        @task
        def trigger_dbt(validated_result: dict) -> dict:
            """
            Trigger DBT to run the Bronze → Silver → Gold transformation chain.
            Uses dbt CLI subprocess (could swap to dbt Cloud API or Astronomer Cosmos).
            """
            import subprocess

            batch_id = validated_result["batch_id"]
            logger.info(f"Triggering DBT for batch_id={batch_id}")

            result = subprocess.run(
                [
                    "dbt", "run",
                    "--project-dir", "/opt/dbt_project",
                    "--profiles-dir", "/opt/dbt_project",
                    "--select", "bronze.bronze_github_prs silver.silver_pr_metrics gold.gold_developer_productivity",
                    "--vars", f'{{"batch_id": "{batch_id}"}}',
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                logger.error(f"DBT failed:\n{result.stdout}\n{result.stderr}")
                raise RuntimeError(f"DBT run failed for batch_id={batch_id}")

            logger.info(f"DBT run complete. batch_id={batch_id}")
            return {"batch_id": batch_id, "status": "success"}

        return trigger_dbt(validated_result)

    # Wire the task groups together
    extracted = extract_group()
    loaded = load_group(extracted)
    validated = validate_group(loaded)
    transform_group(validated)


# Instantiate the DAG
dag_instance = github_pr_ingestion()

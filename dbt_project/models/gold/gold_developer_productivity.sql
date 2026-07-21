-- =============================================================================
-- GOLD: gold_developer_productivity.sql
-- =============================================================================
-- Layer purpose:  Weekly aggregates for dashboards and self-service analytics.
-- Materialization: TABLE (full refresh)
--   WHY NOT INCREMENTAL HERE?
--   Gold is an aggregation — if we only re-run the current week, week-over-week
--   deltas would be computed against a stale prior-week snapshot. Full refresh
--   on Gold is cheap because Silver already filters to recent data. We pay a
--   small compute cost for correctness.
--
-- CLUSTER BY: The most common dashboard queries filter by merged_week + repo.
--   Clustering on these keys reduces Snowflake micro-partition scans from
--   18M rows → ~200K, cutting credit consumption ~4x.
-- =============================================================================

{{ config(
    materialized = 'table',
    cluster_by   = ['merged_week', 'repo_name'],
    tags         = ['gold', 'github', 'developer-productivity']
) }}

WITH weekly_base AS (
    SELECT
        merged_week,
        repo_name,
        org_name,
        pr_size,

        -- Volume metrics
        COUNT(DISTINCT pr_id)                       AS total_prs,
        COUNT(DISTINCT author_login)                AS distinct_authors,
        SUM(total_changes)                          AS total_lines_changed,
        SUM(changed_files)                          AS total_files_changed,

        -- Cycle time stats (only on merged PRs with valid timestamps)
        COUNT(CASE WHEN merged_date IS NOT NULL THEN 1 END) AS merged_prs,
        AVG(CASE WHEN merged_date IS NOT NULL
                 THEN time_to_merge_hours END)      AS avg_cycle_time_hours,
        MEDIAN(CASE WHEN merged_date IS NOT NULL
                    THEN time_to_merge_hours END)   AS p50_cycle_time_hours,
        PERCENTILE_CONT(0.75) WITHIN GROUP (
            ORDER BY time_to_merge_hours
        )                                           AS p75_cycle_time_hours,
        PERCENTILE_CONT(0.95) WITHIN GROUP (
            ORDER BY time_to_merge_hours
        )                                           AS p95_cycle_time_hours,

        -- Review engagement
        AVG(review_comments)                        AS avg_review_comments,
        SUM(review_comments)                        AS total_review_comments,

        -- PR size breakdown
        COUNT(CASE WHEN pr_size = 'XS' THEN 1 END) AS xs_prs,
        COUNT(CASE WHEN pr_size = 'S'  THEN 1 END) AS s_prs,
        COUNT(CASE WHEN pr_size = 'M'  THEN 1 END) AS m_prs,
        COUNT(CASE WHEN pr_size = 'L'  THEN 1 END) AS l_prs,
        COUNT(CASE WHEN pr_size = 'XL' THEN 1 END) AS xl_prs,

        -- Flags
        SUM(CASE WHEN is_hotfix         THEN 1 ELSE 0 END) AS hotfix_prs,
        SUM(CASE WHEN is_breaking_change THEN 1 ELSE 0 END) AS breaking_change_prs

    FROM {{ ref('silver_pr_metrics') }}
    WHERE merged_week IS NOT NULL        -- only count merged PRs in weekly metrics

    GROUP BY 1, 2, 3, 4
),

-- Week-over-week delta: how did each repo's cycle time change vs last week?
with_wow AS (
    SELECT
        w.*,
        LAG(avg_cycle_time_hours) OVER (
            PARTITION BY repo_name
            ORDER BY merged_week
        )                                           AS prev_week_avg_cycle_time_hours,

        LAG(merged_prs) OVER (
            PARTITION BY repo_name
            ORDER BY merged_week
        )                                           AS prev_week_merged_prs,

        -- Percent change in cycle time (negative = improvement)
        ROUND(
            (avg_cycle_time_hours - LAG(avg_cycle_time_hours) OVER (
                PARTITION BY repo_name ORDER BY merged_week
            )) / NULLIF(
                LAG(avg_cycle_time_hours) OVER (
                    PARTITION BY repo_name ORDER BY merged_week
                ), 0
            ) * 100,
        2)                                          AS cycle_time_wow_pct_change

    FROM weekly_base w
)

SELECT
    -- Dimensions
    merged_week,
    repo_name,
    org_name,
    pr_size,

    -- Volume
    total_prs,
    merged_prs,
    distinct_authors,
    total_lines_changed,
    total_files_changed,

    -- Cycle time distribution
    ROUND(avg_cycle_time_hours, 2)                  AS avg_cycle_time_hours,
    ROUND(p50_cycle_time_hours, 2)                  AS p50_cycle_time_hours,
    ROUND(p75_cycle_time_hours, 2)                  AS p75_cycle_time_hours,
    ROUND(p95_cycle_time_hours, 2)                  AS p95_cycle_time_hours,

    -- WoW trends
    ROUND(prev_week_avg_cycle_time_hours, 2)        AS prev_week_avg_cycle_time_hours,
    prev_week_merged_prs,
    cycle_time_wow_pct_change,

    -- Review & size
    ROUND(avg_review_comments, 1)                   AS avg_review_comments,
    total_review_comments,
    xs_prs, s_prs, m_prs, l_prs, xl_prs,

    -- Health signals
    hotfix_prs,
    breaking_change_prs,

    -- Metadata
    CURRENT_TIMESTAMP()                             AS dbt_updated_at

FROM with_wow
ORDER BY merged_week DESC, repo_name

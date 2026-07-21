-- =============================================================================
-- SILVER: silver_pr_metrics.sql
-- =============================================================================
-- Layer purpose:  Clean, enrich, compute cycle time metrics, apply quality flags.
-- Materialization: incremental with a 3-DAY LOOK-BACK WINDOW
--
-- WHY THE 3-DAY LOOK-BACK? (This is a key interview talking point)
-- A PR opened on Monday and merged on Thursday gets extracted on Thursday.
-- But our Bronze model already has the Monday row from the first extraction —
-- with merged_at = NULL. A naive incremental would never update that row.
-- The 3-day window ensures we re-process any PR that was updated (merged,
-- closed, reviewed) within the past 3 days, catching late state changes.
-- =============================================================================

{{ config(
    materialized    = 'incremental',
    unique_key      = 'pr_id',
    on_schema_change = 'sync_all_columns',
    cluster_by      = ['merged_week', 'repo_name'],
    tags            = ['silver', 'github']
) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_github_prs') }}

    {% if is_incremental() %}
        -- 3-day look-back to catch late-arriving merges/closures
        WHERE extracted_at >= DATEADD('day', -3, CURRENT_TIMESTAMP())
    {% endif %}
),

enriched AS (
    SELECT
        pr_id,
        pr_number,
        repo_name,
        org_name,
        pr_title,
        pr_state,
        author_login,
        base_branch,

        -- Timestamps
        created_at,
        updated_at,
        merged_at,
        closed_at,
        extracted_at,

        -- CYCLE TIME (hours from open to merge)
        -- Calculated here in Silver — not pushed to Gold — so all consumers
        -- get the same definition. Using NULLIF prevents division issues.
        CASE
            WHEN merged_at IS NOT NULL AND created_at IS NOT NULL
            THEN DATEDIFF('hour', created_at, merged_at)
            ELSE NULL
        END                                                 AS time_to_merge_hours,

        -- First-review-to-merge (proxy: updated_at is often the last review event)
        CASE
            WHEN merged_at IS NOT NULL AND updated_at IS NOT NULL
            THEN DATEDIFF('hour', updated_at, merged_at)
            ELSE NULL
        END                                                 AS time_in_review_hours,

        -- Code size
        additions,
        deletions,
        (additions + deletions)                             AS total_changes,
        changed_files,
        review_comments,

        -- PR size buckets (used for analysis segmentation in Gold)
        CASE
            WHEN (additions + deletions) <= 10   THEN 'XS'
            WHEN (additions + deletions) <= 100  THEN 'S'
            WHEN (additions + deletions) <= 500  THEN 'M'
            WHEN (additions + deletions) <= 2000 THEN 'L'
            ELSE 'XL'
        END                                                 AS pr_size,

        -- Label-derived feature flags
        ARRAY_CONTAINS('hotfix'::VARIANT, labels_raw)       AS is_hotfix,
        ARRAY_CONTAINS('breaking-change'::VARIANT, labels_raw) AS is_breaking_change,
        ARRAY_CONTAINS('automated'::VARIANT, labels_raw)    AS is_automated_pr,

        -- Date dimensions for grouping
        DATE(merged_at)                                     AS merged_date,
        DATE_TRUNC('week', merged_at)                       AS merged_week,
        DATE_TRUNC('month', merged_at)                      AS merged_month,
        DAYOFWEEK(merged_at)                                AS merged_day_of_week,

        -- DATA QUALITY FLAG
        -- Problem solved: bot PRs had merged_at < created_at, producing negative
        -- cycle times. The is_valid flag lets consumers filter them out while
        -- keeping the raw rows for audit purposes.
        CASE
            WHEN created_at IS NULL                          THEN FALSE
            WHEN merged_at IS NOT NULL
             AND merged_at < created_at                      THEN FALSE
            WHEN time_to_merge_hours < 0                    THEN FALSE
            ELSE TRUE
        END                                                 AS is_valid,

        dbt_loaded_at

    FROM source
)

SELECT * FROM enriched
WHERE is_valid = TRUE       -- downstream Gold only gets clean data

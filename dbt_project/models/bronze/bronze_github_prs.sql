-- =============================================================================
-- BRONZE: bronze_github_prs.sql
-- =============================================================================
-- Layer purpose:  Parse raw JSON → typed columns. Add pipeline metadata.
-- Materialization: incremental (append-only on batch_id)
-- Why incremental here: raw JSON blobs are immutable once loaded.
--   No need to reprocess old batches — just pick up new ones.
-- =============================================================================

{{ config(
    materialized = 'incremental',
    unique_key   = ['pr_id', 'batch_id'],
    on_schema_change = 'sync_all_columns',
    cluster_by   = ['loaded_date'],
    tags         = ['bronze', 'github']
) }}

WITH raw AS (
    SELECT
        -- The raw Snowflake VARIANT column from COPY INTO
        src.$1                                             AS raw_json,
        METADATA$FILENAME                                  AS source_file,
        METADATA$FILE_ROW_NUMBER                           AS file_row_number,
        CURRENT_TIMESTAMP()                                AS dbt_loaded_at

    FROM {{ source('raw_github', 'pull_requests_raw') }} src

    {% if is_incremental() %}
        -- Only process new batches we haven't seen before
        WHERE src.$1:batch_id::STRING > (
            SELECT MAX(batch_id) FROM {{ this }}
        )
    {% endif %}
)

SELECT
    -- Identifiers
    raw_json:id::INTEGER                                   AS pr_id,
    raw_json:number::INTEGER                               AS pr_number,
    raw_json:repo::STRING                                  AS repo_name,
    raw_json:org::STRING                                   AS org_name,
    raw_json:batch_id::STRING                              AS batch_id,

    -- PR attributes
    raw_json:title::STRING                                 AS pr_title,
    raw_json:state::STRING                                 AS pr_state,
    raw_json:author::STRING                                AS author_login,
    raw_json:base_branch::STRING                           AS base_branch,

    -- Timestamps (all cast to TIMESTAMP_NTZ for consistent timezone handling)
    TRY_TO_TIMESTAMP_NTZ(raw_json:created_at::STRING)     AS created_at,
    TRY_TO_TIMESTAMP_NTZ(raw_json:updated_at::STRING)     AS updated_at,
    TRY_TO_TIMESTAMP_NTZ(raw_json:merged_at::STRING)      AS merged_at,
    TRY_TO_TIMESTAMP_NTZ(raw_json:closed_at::STRING)      AS closed_at,
    TRY_TO_TIMESTAMP_NTZ(raw_json:extracted_at::STRING)   AS extracted_at,

    -- Code change metrics
    COALESCE(raw_json:additions::INTEGER, 0)               AS additions,
    COALESCE(raw_json:deletions::INTEGER, 0)               AS deletions,
    COALESCE(raw_json:changed_files::INTEGER, 0)           AS changed_files,
    COALESCE(raw_json:review_comments::INTEGER, 0)         AS review_comments,

    -- Labels (keep as VARIANT for flexibility in Silver)
    raw_json:labels                                        AS labels_raw,

    -- Pipeline metadata
    source_file,
    file_row_number,
    dbt_loaded_at,
    DATE(TRY_TO_TIMESTAMP_NTZ(raw_json:created_at::STRING)) AS loaded_date

FROM raw

-- Guard against malformed JSON rows
WHERE pr_id IS NOT NULL

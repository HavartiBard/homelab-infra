CREATE TABLE IF NOT EXISTS runs (
  run_uuid           VARCHAR PRIMARY KEY,
  started_at         TIMESTAMP NOT NULL,
  ended_at           TIMESTAMP NOT NULL,
  endpoint_url       VARCHAR NOT NULL,
  model_id           VARCHAR NOT NULL,
  runtime            VARCHAR NOT NULL,
  host               VARCHAR,
  suite_id           VARCHAR NOT NULL,
  quantization       VARCHAR,
  ctx_length         INTEGER,
  sampling_params    JSON,
  infra_git_sha      VARCHAR,
  catalog_git_sha    VARCHAR,
  warm_time_sec      DOUBLE,
  notes              VARCHAR,
  status             VARCHAR NOT NULL,
  error              VARCHAR,
  scores             JSON NOT NULL,
  artifacts          JSON NOT NULL,
  source             VARCHAR NOT NULL DEFAULT 'local'
);

CREATE TABLE IF NOT EXISTS refs (
  model_id              VARCHAR NOT NULL,
  source                VARCHAR NOT NULL,
  display_name          VARCHAR NOT NULL,
  num_params_b          DOUBLE,
  license               VARCHAR,
  arc_challenge_acc     DOUBLE,
  gsm8k_strict_match    DOUBLE,
  humaneval_pass1       DOUBLE,
  ifeval_strict_acc     DOUBLE,
  citation_url          VARCHAR,
  as_of                 DATE NOT NULL,
  imported_at           TIMESTAMP NOT NULL,
  PRIMARY KEY (model_id, source)
);

CREATE OR REPLACE VIEW leaderboard_v AS
SELECT
  run_uuid, model_id, runtime, host,
  CAST(json_extract_string(scores, '$.quality_avg')           AS DOUBLE) AS quality_avg,
  CAST(json_extract_string(scores, '$.speed_score')           AS DOUBLE) AS speed_score,
  CAST(json_extract_string(scores, '$.ttft_p95_ms')           AS DOUBLE) AS ttft_p95_ms,
  CAST(json_extract_string(scores, '$.decode_tokens_per_sec') AS DOUBLE) AS decode_tokens_per_sec,
  CAST(json_extract_string(scores, '$.vram_gb_peak')          AS DOUBLE) AS vram_gb_peak,
  started_at, source, NULL AS num_params_b
FROM runs
UNION ALL
SELECT
  NULL AS run_uuid, model_id, NULL AS runtime, NULL AS host,
  CASE WHEN (
    (CASE WHEN arc_challenge_acc  IS NULL THEN 0 ELSE 1 END) +
    (CASE WHEN gsm8k_strict_match IS NULL THEN 0 ELSE 1 END) +
    (CASE WHEN humaneval_pass1    IS NULL THEN 0 ELSE 1 END) +
    (CASE WHEN ifeval_strict_acc  IS NULL THEN 0 ELSE 1 END)
  ) >= 2
  THEN (
    COALESCE(arc_challenge_acc,0) + COALESCE(gsm8k_strict_match,0) +
    COALESCE(humaneval_pass1,0)   + COALESCE(ifeval_strict_acc,0)
  ) / (
    (CASE WHEN arc_challenge_acc  IS NULL THEN 0 ELSE 1 END) +
    (CASE WHEN gsm8k_strict_match IS NULL THEN 0 ELSE 1 END) +
    (CASE WHEN humaneval_pass1    IS NULL THEN 0 ELSE 1 END) +
    (CASE WHEN ifeval_strict_acc  IS NULL THEN 0 ELSE 1 END)
  )
  ELSE NULL
  END AS quality_avg,
  NULL AS speed_score, NULL AS ttft_p95_ms,
  NULL AS decode_tokens_per_sec, NULL AS vram_gb_peak,
  CAST(as_of AS TIMESTAMP) AS started_at, source, num_params_b
FROM refs;

CREATE OR REPLACE VIEW merged_refs_v AS
WITH ranked AS (
  SELECT *,
    CASE source
      WHEN 'frontier_curated'   THEN 1
      WHEN 'hf_open_llm_v2'     THEN 2
      WHEN 'hf_open_llm_v1'     THEN 3
      WHEN 'bigcode_humaneval'  THEN 4
      ELSE 9
    END AS priority
  FROM refs
)
SELECT
  model_id,
  first(display_name      ORDER BY priority) AS display_name,
  first(num_params_b      ORDER BY priority) AS num_params_b,
  first(license           ORDER BY priority) AS license,
  first(arc_challenge_acc  ORDER BY priority) FILTER (WHERE arc_challenge_acc  IS NOT NULL) AS arc_challenge_acc,
  first(gsm8k_strict_match ORDER BY priority) FILTER (WHERE gsm8k_strict_match IS NOT NULL) AS gsm8k_strict_match,
  first(humaneval_pass1    ORDER BY priority) FILTER (WHERE humaneval_pass1    IS NOT NULL) AS humaneval_pass1,
  first(ifeval_strict_acc  ORDER BY priority) FILTER (WHERE ifeval_strict_acc  IS NOT NULL) AS ifeval_strict_acc
FROM ranked
GROUP BY model_id;

# Stage 3 — Databricks bronze ingest

Lands raw Open-Meteo weather + air-quality JSON for one location into a
single Delta table: `env_events_v1.bronze_api_response`. See
`PROJECT_PLAN.md` Stage 3 for the full scope; this folder (`stage3_bronze/`)
is Stage 3 only — no silver/gold, no PySpark transforms, no Jobs/schedule,
no multi-location.

## Files

- `bronze_ingest.py` — plain Python (no pyspark import): HTTP fetch
  helpers that reuse Stage 1's `src/openmeteo.py` URL/field-list constants,
  plus `build_bronze_rows()` which returns two row dicts (one per source)
  and the `CREATE SCHEMA` / `CREATE TABLE` DDL strings. Importable and
  testable locally without Databricks.
- `bronze_ingest_notebook.py` — a Databricks notebook (Databricks "source
  format" `.py` file — the `# Databricks notebook source` header and
  `# COMMAND ----------` cell markers are what Databricks reads to render
  it as a notebook). This is the only file that touches `spark`/Delta.

Note: this folder is named `stage3_bronze/` rather than `databricks/` on
purpose — Databricks Runtime commonly pre-installs packages (e.g.
`databricks-sdk`) that claim the top-level `databricks` Python namespace,
and a repo folder literally named `databricks/` with its own `__init__.py`
can shadow or conflict with that.

## Prerequisites

- Databricks workspace `7474655624747943` (noted for reference only — not
  a secret, and this environment cannot log into it to run or verify
  anything there).
- This repo cloned as a **Databricks Repo** (Repos -> Add Repo -> point at
  this GitHub repo), so the notebook can `import src...` / `import
  stage3_bronze...` from the repo root. Uploading just the single notebook
  file to the Workspace (outside a Repo) will not work — the imports will
  fail.
- `config/locations.yaml` filled in with your real location (same file
  Stage 1/2 already use — not duplicated here).
- A small cluster. Two HTTP calls and a 2-row Delta append need no more
  than the smallest/personal-compute single-node cluster your workspace
  offers. Don't spin up anything bigger "to be safe."

## How to run it once

1. Attach the small cluster.
2. Open `bronze_ingest_notebook.py` (from inside the Databricks Repo
   clone) and **Run All**.
3. Read the printed JSON-parse sanity check (cell 3) and the `display()`
   table near the bottom (cell 5) — you should see exactly 2 new rows for
   this run's `ingest_id`: one `source=open_meteo_weather`, one
   `source=open_meteo_aq`, both `http_status=200`.
4. **Stop the cluster** (Compute tab -> your cluster -> Terminate), or
   detach the notebook and let auto-termination finish the job. Nothing
   here needs an always-on cluster.

Re-running is safe: every run appends 2 more rows under a fresh
`ingest_id` and never deletes or overwrites existing bronze rows.

## Verifying the payload is real JSON

The notebook already does this (cell 3, before any Delta write): it calls
`json.loads()` on each raw response body and prints the top-level keys.
You can also do it later, offline, straight from the table:

```sql
SELECT ingest_id, source, http_status, payload
FROM env_events_v1.bronze_api_response
ORDER BY requested_at DESC
LIMIT 2;
```

then, in a Python cell: `json.loads(row.payload)` on either row.

## What this intentionally does NOT do

Per Stage 3's "what not to build" list: no silver parsing, no PySpark
transforms of the payload, no Delta `MERGE`, no Jobs/scheduling, no gold
tables, no SQL warehouse, no secrets machinery, no multi-location fanout,
no DLT/streaming/Terraform/CI/UI/ML. Those are later stages.

## Important caveat

**Table creation and the two bronze rows are only verified once you
actually run this notebook in workspace `7474655624747943`.** This
sandbox cannot attach to that workspace, run Spark, or write Delta
tables — `bronze_ingest.py`'s plain-Python HTTP/JSON logic was exercised
locally (see the PR description for the output), but the Delta
schema/table creation and the `display()` row count have not been and
cannot be verified from here.

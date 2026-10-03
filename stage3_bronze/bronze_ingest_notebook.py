# Databricks notebook source
# MAGIC %md
# MAGIC # Stage 3 — Bronze ingest: `env_events_v1.bronze_api_response`
# MAGIC
# MAGIC Lands raw Open-Meteo weather + air-quality JSON for **one location**
# MAGIC into a single Delta bronze table. No silver/gold, no Spark used for
# MAGIC the HTTP calls (that stays plain Python, reused from Stage 1), no
# MAGIC Jobs/scheduling yet. See `PROJECT_PLAN.md` Stage 3.
# MAGIC
# MAGIC ## Before you run this
# MAGIC - Workspace: `7474655624747943` (noted here for reference only, not a secret).
# MAGIC - Clone this GitHub repo as a **Databricks Repo** and open this notebook
# MAGIC   from inside that repo clone (so `src/` and `stage3_bronze/` import correctly —
# MAGIC   this will NOT work if you upload only this single file to the Workspace).
# MAGIC - Attach the **smallest cluster you have** — a single-node / personal-compute
# MAGIC   cluster is plenty; this notebook makes 2 HTTP calls and writes 2 rows.
# MAGIC - Confirm `config/locations.yaml` has your real lat/lon/timezone before running.
# MAGIC
# MAGIC ## How to run it once
# MAGIC 1. Attach the small cluster above.
# MAGIC 2. `Run All`.
# MAGIC 3. Check the `display()` output near the bottom: you should see **2 new rows**
# MAGIC    (`open_meteo_weather` and `open_meteo_aq`) for this run's `ingest_id`.
# MAGIC 4. **Stop the cluster** (Compute tab -> cluster -> Terminate), or detach the
# MAGIC    notebook and let auto-termination handle it. Nothing here needs an
# MAGIC    always-on cluster or warehouse.
# MAGIC
# MAGIC Re-running this notebook is safe: it only **appends** two more rows per run
# MAGIC (new `ingest_id` each time). It never deletes or overwrites bronze history.

# COMMAND ----------

import os
import sys

# Databricks Repos normally put the repo root on sys.path automatically.
# This is a defensive fallback for older runtimes / non-Repos checkouts:
# the repo root is the parent directory of this notebook's `stage3_bronze/` folder.
_NOTEBOOK_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
_REPO_ROOT = os.path.abspath(os.path.join(_NOTEBOOK_DIR, ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from src.config import load_location
    from stage3_bronze.bronze_ingest import (
        BRONZE_COLUMNS,
        CREATE_SCHEMA_SQL,
        CREATE_TABLE_SQL,
        FULL_TABLE_NAME,
        build_bronze_rows,
    )
except ImportError as exc:
    raise ImportError(
        "Could not import src.config / stage3_bronze.bronze_ingest. "
        "Make sure this notebook is opened from inside a Databricks Repo "
        "clone of the weatherAlertHQ repo (Repos -> Add Repo), not a "
        "single uploaded file."
    ) from exc

import json
import uuid
from datetime import datetime, timezone as dt_timezone

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create the schema + table if they don't exist yet
# MAGIC One schema (`env_events_v1`), one table (`bronze_api_response`) with a
# MAGIC `source` column distinguishing `open_meteo_weather` / `open_meteo_aq`
# MAGIC rows — per PROJECT_PLAN.md's spec correction (no per-API bronze tables,
# MAGIC no Unity Catalog multi-schema sprawl).

# COMMAND ----------

spark.sql(CREATE_SCHEMA_SQL)
spark.sql(CREATE_TABLE_SQL)
print(f"Schema/table ready: {FULL_TABLE_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load the one configured location and fetch both APIs (plain Python)
# MAGIC HTTP calls happen here in plain Python (`requests`, via
# MAGIC `stage3_bronze/bronze_ingest.py`, which reuses Stage 1's URL/field-list
# MAGIC constants) — not through Spark.

# COMMAND ----------

location = load_location()
print(f"Location: {location.name} ({location.location_id}) "
      f"lat/lon={location.latitude},{location.longitude} tz={location.timezone}")

ingest_id = str(uuid.uuid4())
requested_at = datetime.now(dt_timezone.utc)

rows = build_bronze_rows(location, ingest_id=ingest_id, requested_at=requested_at)

print(f"Built {len(rows)} bronze row(s) for ingest_id={ingest_id}")
for row in rows:
    print(f"  source={row['source']!r} http_status={row['http_status']} payload_bytes={len(row['payload'])}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Sanity-check the payloads parse as JSON *before* writing to Delta
# MAGIC This only needs plain Python — if this cell fails, don't bother writing
# MAGIC bad rows to the table.

# COMMAND ----------

for row in rows:
    if row["http_status"] != 200:
        print(f"WARNING: source={row['source']} returned http_status={row['http_status']} "
              f"— payload may be an error body, not forecast data.")
    parsed = json.loads(row["payload"])  # raises if payload isn't valid JSON
    print(f"OK: source={row['source']} payload parses as JSON, top-level keys={list(parsed.keys())[:6]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Append the two rows to the Delta bronze table
# MAGIC `mode("append")` only — reruns add new rows, never delete/overwrite
# MAGIC bronze history (idempotent-enough for Stage 3; MERGE/upsert semantics
# MAGIC are a Stage 4 silver concern, not bronze).

# COMMAND ----------

from pyspark.sql import Row
from pyspark.sql.types import (
    DateType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# Must stay in sync with CREATE_TABLE_SQL in stage3_bronze/bronze_ingest.py.
BRONZE_SPARK_SCHEMA = StructType([
    StructField("ingest_id", StringType(), nullable=False),
    StructField("location_id", StringType(), nullable=False),
    StructField("source", StringType(), nullable=False),
    StructField("requested_at", TimestampType(), nullable=False),
    StructField("payload", StringType(), nullable=False),
    StructField("http_status", IntegerType(), nullable=False),
    StructField("pull_date", DateType(), nullable=False),
])

spark_rows = [Row(**{col: row[col] for col in BRONZE_COLUMNS}) for row in rows]
bronze_df = spark.createDataFrame(spark_rows, schema=BRONZE_SPARK_SCHEMA)

bronze_df.write.format("delta").mode("append").saveAsTable(FULL_TABLE_NAME)
print(f"Appended {bronze_df.count()} row(s) to {FULL_TABLE_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Verify: this run's two bronze rows
# MAGIC You should see exactly 2 rows below (`open_meteo_weather`,
# MAGIC `open_meteo_aq`) for this run's `ingest_id`, each with `http_status=200`
# MAGIC and a non-empty `payload`.

# COMMAND ----------

display(
    spark.sql(
        f"SELECT ingest_id, location_id, source, requested_at, http_status, pull_date, "
        f"length(payload) AS payload_length "
        f"FROM {FULL_TABLE_NAME} WHERE ingest_id = '{ingest_id}' ORDER BY source"
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Stop here
# MAGIC Table creation and the two rows above are only verified once *you* run
# MAGIC this in workspace `7474655624747943` and see the output. Nothing in this
# MAGIC repo can confirm the Delta write succeeded from outside Databricks.
# MAGIC
# MAGIC **Now stop/terminate the cluster.** Stage 3 stops here — no silver
# MAGIC parsing, no MERGE, no Jobs/schedule, no gold tables yet.

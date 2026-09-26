Environmental Events — PROJECT_PLAN.md
Status: Living planning document (source of truth)
Last updated: 2026-09-26
Owner: Ryan Cedzo
Tooling split: Grok Bot = architecture, hard debugging, decision review · Cursor Pro = implement one milestone at a time
Rule: Do not implement past the current milestone. Update this document when decisions change or a milestone is accepted.

1. What we are building
Product vision (long-term)
A web/mobile app that forecasts interesting environmental/nature events and lets users set thresholds and get alerts (sunset quality, stargazing, auroras, etc.).

V1 prototype (near-term, this plan)
A sunset-condition forecasting prototype for a tiny number of fixed locations that:

Pulls weather + air-quality forecasts,
Builds sunset-window features,
Produces an explainable heuristic score (0–100) with human-readable drivers,
Runs on a small Databricks Job writing Delta tables, using PySpark where it teaches real data-engineering skills.
V1 is successful if you trust the ranking for evenings you can see yourself, and the pipeline reruns without babysitting.

Why we are building it this way
Goal	How the plan serves it
Useful prototype	Heuristic score + drivers before any cloud complexity
Learn Databricks / Delta / PySpark	Stages 3–7 introduce them only after local proof
Avoid fake infrastructure	No streaming, DLT, Terraform, K8s, Feature Store, auth, frontend in V1
Controllable AI cost	One milestone → one Cursor session; Grok for review between stages
2. V1 scope lock
In scope
1 location first (expand only in Stage 9)
Open-Meteo Weather + Open-Meteo Air Quality
Local solar geometry (library, not a third weather API)
Sunset window feature aggregation
heuristic_v1 score + drivers
Databricks: bronze → silver → gold Delta tables
PySpark for silver normalize + gold features
One scheduled daily Job + manual rerun
Notebook/SQL “today’s sunset” card
~2 weeks of personal 1–5 validation notes
Out of scope until explicitly pulled in later
Kafka, streaming, DLT, Terraform, CI/CD, multi-env, Kubernetes, Feature Store, Model Serving, complex Unity Catalog, microservices, user auth, web/mobile UI, ML, photo-preference model integration, multi-event types, arbitrary lat/lon API, commercial packaging

Component tags (used in milestones)
Product — needed for a useful sunset prototype
Learning — kept mainly to practice Databricks/Delta/PySpark
Defer — not now
3. Architecture (current intent — refine only after stages prove it)
Location config
  → HTTP ingest (Python): Open-Meteo weather + AQ
  → Bronze Delta: raw payloads
  → Silver (PySpark): hourly normalized forecasts (weather ⋈ AQ)
  → Solar events: sunset time + azimuth
  → Gold features (PySpark): sunset-window aggregates
  → Gold scores: heuristic_v1 + drivers
  → Demo: SQL/notebook card
  → Job: schedule daily, idempotent reruns

Stages 1–2 run entirely locally (no Databricks). Stages 3–7 move the same logic onto Databricks without redesigning the product brain.

Cost-control principles
Prefer job clusters that terminate over always-on warehouses/clusters
Develop transforms in notebooks; promote to Job only at Stage 7
One location until Stage 9 (API + compute scale with N)
Open-Meteo: few calls per run (2 HTTP calls per location per job)
Do not turn on Unity Catalog complexity, Photon experiments, or large clusters “to learn”
Stop interactive clusters when done for the day
4. Spec corrections / simplifications (vs earlier V1 tech spec)
Review these before treating the old spec as gospel:

Topic	Decision for this plan	Why
Open-Meteo feature availability	Keep cloud_cover, cloud_cover_low/mid/high, relative_humidity_2m, visibility, precipitation, weather_code, aerosol_optical_depth, pm2_5	Confirmed in Open-Meteo docs — obtainable
“Clear horizon” feature	Keep as crude proxy only — use low cloud in last 1–2h before sunset as horizon_block_risk	API has no directional horizon cloud; do not pretend otherwise
Sunset window	Default [sunset−2h, sunset+1h]	Captures pre-sunset cloud setup + early twilight; golden hour alone is shorter but cloud setup matters earlier. Revisit after Stage 1 inspection
Separate bronze tables per API	Simplify to one bronze_api_response with source column	Less catalog noise for one-location V1
dim_location as Delta from day 1	Start as config/locations.yaml (or JSON); promote to Delta only when useful	Avoid empty warehouse ceremony in Stage 1–2
Delta MERGE everywhere	Silver: MERGE (or partition overwrite) for changing forecasts — Learning + Product · Gold: overwrite by location+local_date+version	Forecasts rewrite the horizon daily; MERGE teaches a real pattern. For tiny gold tables, overwrite is fine and cheaper to reason about
Unity Catalog multi-schema	One schema env_events_v1 (or default DB)	Complex UC is Defer
Pandas UDF for solar	Plain Python over 1–3 locations	UDFs add debug cost for no scale benefit
Personal Slack in V1	Defer to Stage 9	Demo card is enough
Always-on SQL warehouse for demo	Use notebook display or serverless SQL only if already cheap/free; prefer notebook	Avoid warehouse idle cost
5. Technical decisions log
Record only decisions that are locked. Add rows as milestones complete.

ID	Decision	Status	Notes
D1	Event type for V1 = sunset conditions only	Locked	
D2	Score = transparent heuristic, not ML	Locked	
D3	Data = Open-Meteo weather + AQ	Locked	
D4	Solar geometry = local library	Locked	Pick concrete lib in Stage 1 (e.g. astral or equivalent)
D5	Stages 1–2 local-first before Databricks	Locked	
D6	PySpark used for silver + gold features (Learning)	Locked	Ingest stays Python
D7	First location lat/lon/timezone	Open	Required before Stage 1 coding
D8	Databricks workspace availability	Open	Required before Stage 3
D9	Horizon proxy = low-cloud pre-sunset	Locked (crude)	
D10	Demo = notebook/SQL card	Locked for V1	Notifications = Stage 9
6. Learning objectives (project-wide)
You should be able to explain, without reading Cursor’s code aloud:

What Open-Meteo returns and how hourly arrays map to timestamps
How sunset time depends on lat/lon/date/timezone
Why the score is a weighted, non-monotonic function of clouds/AOD/humidity
Bronze vs silver vs gold responsibilities
Why forecast tables need overwrite/MERGE semantics
How a Databricks Job differs from an interactive notebook
Where money is spent (cluster uptime, warehouse uptime)
Cursor may write code; you own these explanations at each stop point.

7. Deferred functionality
Everything in §2 “Out of scope,” plus: second event types, photo-ML labels as training input, public API, commercial ToS packaging, historical backfill beyond what Stage 1 needs for a few days of forecast horizon.

8. Open questions (resolve when blocking)
D7 — Home location: lat, lon, IANA timezone (or city + confirm coords).
D8 — Databricks: existing workspace? Free/community vs paid? Any credit limits?
Python solar library preference: any constraint, or pick simplest maintained option in Stage 1?
Repo home: new GitHub repo name/path when you start Stage 1 in Cursor.
Non-blocking until Stage 8: where you will log daily 1–5 ratings (notes app vs tiny CSV/table).

9. How to use this roadmap
Resolve any Open decisions blocking the next stage.
Read only that stage’s section.
Paste that stage’s Cursor prompt only.
Hit the Stop point and validate acceptance criteria yourself.
Optionally ask Grok to review diffs/decisions before the next stage.
Check the milestone Accepted and note date/learnings in §5 or a short Progress log at the bottom.
Milestones
Stage 1 — Local data prototype
Status: Not started
Tags: Product (API + window proof) · Learning (none Databricks yet)

Objective
Prove Open-Meteo weather + AQ return usable fields for one location, compute sunset + window, and print inspectable sunset-window feature values.

Why this milestone exists
Product: Without real payloads and a correct sunset window, later tables and Spark jobs encode fiction.
Learning: Databricks is intentionally absent — validate the domain first.

Inputs
Locked lat/lon/timezone (D7)
Python 3 environment you control
Network access to Open-Meteo
Expected outputs / artifacts
Small local project folder (e.g. env-events/) with minimal structure:
config/locations.yaml (one location)
src/ modules for fetch, solar, window features
requirements.txt (or equivalent)
optional fixtures/ sample JSON saved from a successful pull
Console or notebook output showing: sunset time, window bounds, key hourly rows, aggregated feature dict
Short note in repo or here: “fields confirmed present: …”
Implementation tasks (for Cursor)
Create minimal project skeleton (no Databricks, no Spark).
Load one location from config.
Fetch Open-Meteo forecast hourly: cloud_cover, cloud_cover_low/mid/high, relative_humidity_2m, visibility, precipitation, weather_code; timezone = location TZ; modest forecast_days (2 is enough).
Fetch Open-Meteo Air Quality hourly: aerosol_optical_depth, pm2_5.
Compute sunset UTC/local + azimuth via a local library.
Define window [sunset−2h, sunset+1h]; select hourly rows in window; join weather+AQ on timestamp.
Print aggregates: means for cloud layers, humidity, visibility, AOD, pm2_5; sum precip; list raw hours for eyeballing.
Save one raw JSON fixture pair for offline reruns (optional but useful).
Acceptance criteria
 Both APIs return data for your coordinates without manual URL hacking each time
 You can point to sunset time and verify it is plausible for the date/location
 Cloud low/mid/high, humidity, visibility, AOD appear in the parsed output (not just total cloud)
 Window contains a sensible small number of hourly rows (typically ~3–4 hours)
 No Databricks/Spark/Delta/scheduler code exists in the repo yet
What NOT to build
Score/heuristic, Delta, Spark, jobs, UI, multi-location loops, CAMS ADS, retry frameworks beyond basic HTTP errors, packaging for prod.

Likely difficulty
Low–medium. API shape and timezone/solar edge cases are the only likely snags.

Potential cost implications
Negligible (Open-Meteo free tier for personal use; local CPU only). Avoid hammering APIs in a tight loop while debugging — cache fixtures.

What you should understand personally
Open-Meteo hourly array alignment with time[]
Location timezone vs UTC for “which local date’s sunset”
Meaning of low vs mid vs high cloud cover in the API
That AOD is dimensionless column haze, not the same as PM2.5
Recommended Cursor prompt
Implement ONLY Stage 1 of Environmental Events (see PROJECT_PLAN.md Stage 1).

Scope: local Python prototype for ONE location from config/locations.yaml.
- Fetch Open-Meteo Weather + Air Quality for that lat/lon
- Compute sunset time/azimuth with a local solar library (no extra HTTP solar API)
- Build sunset window [sunset-2h, sunset+1h]
- Join hourly weather+AQ, print window rows and simple aggregates

Do NOT implement scoring, Databricks, Spark, Delta, jobs, UI, ML, multi-location, or later stages.
Keep the project tiny and readable. Stop when Stage 1 acceptance criteria are met.

Stop point
When acceptance boxes are checked and you have inspected one real evening’s window data. Do not start heuristic code until you trust the fields.

Stage 2 — Local heuristic
Status: Not started
Tags: Product (core “brain”)

Objective
Implement transparent heuristic_v1 → integer 0–100 + human-readable drivers from Stage 1 features.

Why this milestone exists
Product: The score is the prototype value.
Learning: No Spark yet — keep the formula easy to rewrite by hand.

Inputs
Stage 1 accepted (live fetch + feature dict/structure)
Expected outputs / artifacts
src/scoring/heuristic_v1.py (or equivalent) with version string heuristic_v1
Pure function: features → {score, grade?, drivers[]}
CLI or script path: fetch → features → print score card
Brief formula comment or docs/heuristic_v1.md (short; weights listed)
Implementation tasks
Define subscores (start from plan defaults; keep weights in one obvious place):
Cloud canvas (reward mid/high in ~30–70 band; penalize high low-cloud; penalize empty or socked-in sky)
Horizon access (inverse of low-cloud near sunset)
Aerosol/clarity (non-monotonic AOD; humidity amplifies haze penalty)
Hygiene (visibility bonus; precip/PM penalties)
Clamp/weight → 0–100.
Emit 3–6 driver strings referencing actual numbers.
Print a “today’s card” locally.
Manually tweak weights once and confirm output changes predictably.
Acceptance criteria
 Same input features always yield the same score
 Drivers mention real feature values
 You can change one weight and explain the score delta
 Still zero Databricks/Spark
What NOT to build
ML, persisted score history DB, notifications, tuning UI, calibration against labels (that’s Stage 8).

Likely difficulty
Low. Judgement call is weight design, not engineering.

Potential cost implications
None beyond Stage 1 API calls.

What you should understand personally
Why high AOD is not automatically “better reds”
Which inputs dominate your score on a clear vs cloudy evening
Versioning: changing weights means a new mental/compare baseline
Recommended Cursor prompt
Implement ONLY Stage 2 from PROJECT_PLAN.md.

Add a transparent heuristic_v1(features) -> {score: 0-100, drivers: [str, ...]}
using the Stage 1 sunset-window features. Keep weights in one obvious place.
Print a local score card (sunset time, score, drivers).

Do NOT add ML, Databricks, Spark, Delta, persistence beyond local script output,
notifications, or later stages. Do not refactor Stage 1 into a framework.

Stop point
You can run one command/notebook path and get a score you roughly agree or disagree with — disagreement is fine; opacity is not.

Stage 3 — Databricks Bronze
Status: Not started
Tags: Learning (Databricks + Delta intro) · Product (durable raw land)

Objective
Move HTTP ingestion into Databricks and land raw API responses in a minimal Delta bronze table.

Why this milestone exists
Product: Raw landing enables replay and schema evolution later.
Learning: First contact with workspace, notebooks/jobs-as-notebooks, Delta writes — without Spark transforms yet.

Inputs
Stages 1–2 accepted
Databricks workspace access (D8)
Same location config values
Expected outputs / artifacts
Schema/database env_events_v1 (simplest available on your tier)
Delta table bronze_api_response
Suggested columns: ingest_id, location_id, source, requested_at, payload (string), http_status, pull_date
Notebook (or repo-synced file) that: reads location → HTTP fetch → append/write bronze
Documented how to run it manually once
Implementation tasks
Create minimal schema; avoid UC sprawl.
Port fetch functions (or call same logic) from local project.
Write bronze rows for open_meteo_weather and open_meteo_aq.
Verify with DISPLAY/SELECT limited rows.
Confirm cluster terminates after you detach/stop.
Acceptance criteria
 Two bronze rows (weather + AQ) for one ingest visible in Delta
 Payload parses as JSON offline from the stored string
 You know how to stop the cluster
 No silver/gold/Spark parsing job required yet
What NOT to build
Silver parsing, MERGE logic, Jobs scheduler, SQL warehouse for vanity, secrets machinery unless required, multi-location fanout.

Likely difficulty
Medium if new to Databricks UI/permissions; Low if workspace is ready.

Potential cost implications
Main cost risk begins here. Use smallest cluster; stop when idle. Prefer notebook runs over keeping all-purpose clusters up. Avoid creating a SQL warehouse unless demo later needs it.

What you should understand personally
Cluster vs notebook vs table storage
What Delta commit looks like (version appears)
Difference between landing raw JSON and parsing it
Recommended Cursor prompt
Implement ONLY Stage 3 from PROJECT_PLAN.md.

Target: Databricks bronze landing for one location.
- Create/use schema env_events_v1
- Table bronze_api_response (raw payloads for open_meteo_weather and open_meteo_aq)
- Notebook/script: HTTP ingest → write Delta

Reuse Stage 1 fetch field lists. Do NOT build silver/gold, PySpark parsing,
MERGE, Jobs scheduling, UI, or later stages. Keep Unity Catalog usage minimal.

Stop point
You can rerun ingest and see new bronze rows without any transform code.

Stage 4 — PySpark Silver
Status: Not started
Tags: Learning (primary PySpark exercise) · Product (normalized hourly truth)

Objective
Parse bronze JSON with PySpark into silver_hourly_forecast, joining weather + AQ, with correct timestamps and timezone-derived local fields; write/MERGE so re-ingests update the forecast horizon.

Why this milestone exists
Learning: This is the justified Spark lesson (parse, explode/arrays → rows, join, time handling, Delta MERGE/overwrite).
Product: Stable hourly grain for features/scores.

Inputs
Stage 3 bronze data present
Understanding of Open-Meteo JSON shape from Stage 1
Expected outputs / artifacts
Table silver_hourly_forecast at grain location_id + valid_time_utc
Columns sufficient for scoring: cloud layers, humidity, visibility, precip, weather_code, aod, pm2_5, local_date, local_hour, ingest_id, updated_at
Notebook/job fragment demonstrating MERGE or partition overwrite idempotency
Note in decisions log: chosen write strategy (MERGE vs overwrite) and why
Implementation tasks
Read latest bronze payloads per source/location (define “latest” simply).
Parse hourly arrays to rows in Spark.
Join weather ⋈ AQ on location + timestamp.
Attach local_date/hour using location timezone.
MERGE/overwrite into silver for that location’s forecast span.
Run twice; confirm no duplicate hours and updated values replace stale forecast.
Acceptance criteria
 One hour = one silver row for the location
 AOD and cloud_mid exist on same rows after join
 Re-run does not duplicate grain keys
 You can explain the MERGE/overwrite keys in one minute
What NOT to build
Gold features/scores, streaming, SCD2 history of every forecast version (optional later), great expectations suite, multi-hop medallion across catalogs.

Likely difficulty
Medium–high. JSON-from-Open-Meteo + times + MERGE is where Cursor often hides bugs — verify manually.

Potential cost implications
Spark jobs use cluster time. Develop with small data (one location, few days). Don’t cache huge tables. Stop clusters after runs.

What you should understand personally
Why forecast tables are updated in place for the horizon
UTC vs local_date for sunset-day grouping
Join fanout risks if timestamps don’t align
Delta MERGE match condition
Recommended Cursor prompt
Implement ONLY Stage 4 from PROJECT_PLAN.md.

Use PySpark to read bronze_api_response, parse Open-Meteo hourly JSON into rows,
join weather + AQ, add local_date/hour, and MERGE or overwrite into
silver_hourly_forecast for one location.

Idempotent re-runs required. Do NOT build gold features, scoring, Jobs scheduler,
or later stages. No streaming/DLT. Keep code readable over clever.

Stop point
Silver looks right for tonight’s hours when compared to Stage 1 local printout.

Stage 5 — Gold sunset features
Status: Not started
Tags: Learning (window aggregate patterns) · Product (model features)

Objective
Build gold_sunset_features / solar events: sunset per local_date, filter sunset window, aggregate features with PySpark.

Why this milestone exists
Product: Features are the contract for scoring.
Learning: Filter, join solar, groupBy aggregations, Delta write — applied to a real window problem.

Inputs
Silver hourly accepted
Same solar rules as Stage 1 (port logic; don’t silently change window)
Expected outputs / artifacts
silver_solar_events or compute solar inline then write gold_sunset_features
Grain: location_id + local_date
Feature columns aligned with heuristic_v1 inputs + feature_version
Parity check: gold aggregates ≈ Stage 1 local aggregates for same day
Implementation tasks
Compute sunset for today/tomorrow for the location.
Define window bounds columns.
Filter silver hours into window; aggregate.
Compute horizon_block_risk from low cloud in final pre-sunset hours (document crude proxy).
Write gold features (overwrite per location+date is fine).
Diff against Stage 1 numbers; investigate material gaps.
Acceptance criteria
 Feature row exists for today’s sunset date
 Window hour count plausible
 Aggregates within sanity tolerance of local Stage 1 (same pull/day)
 Proxy documented as proxy
What NOT to build
Scoring table yet (Stage 6), fancy window functions for their own sake, satellite features.

Likely difficulty
Medium. Off-by-one timezone/date bugs are likely.

Potential cost implications
Same as Stage 4 — short job cluster runs.

What you should understand personally
Grouping by local sunset date vs UTC date
Why feature_version exists
Limits of the horizon proxy
Recommended Cursor prompt
Implement ONLY Stage 5 from PROJECT_PLAN.md.

Using PySpark + silver_hourly_forecast, compute sunset times for the location,
filter [sunset-2h, sunset+1h], aggregate gold_sunset_features for today/tomorrow,
including crude horizon_block_risk from pre-sunset low cloud.

Match Stage 1 window semantics. Do NOT implement scoring, Jobs, or later stages.

Stop point
Gold features match local prototype closely enough that scoring will be meaningful.

Stage 6 — Gold scoring + demo
Status: Not started
Tags: Product (demo) · Learning (light — applying known formula on Spark/SQL)

Objective
Apply heuristic_v1 to gold features → gold_sunset_scores; create simplest notebook/SQL “today’s sunset” card.

Why this milestone exists
Product: First end-to-end useful artifact on Databricks.
Learning: Secondary; prefer porting the same Stage 2 formula, not a rewrite.

Inputs
Stage 2 heuristic + Stage 5 features
Expected outputs / artifacts
Table gold_sunset_scores (location_id, local_date, score, score_version, drivers, scored_at)
Notebook section or SQL view v_sunset_today showing sunset time, score, drivers
Confirmation Stage 2 vs Stage 6 scores match on same features
Implementation tasks
Port heuristic_v1 without “improving” weights silently.
Write scores for today/tomorrow.
Build minimal demo cell/view.
Parity test vs local Stage 2.
Acceptance criteria
 Demo shows sunset time, score, drivers for Home
 Score parity with local heuristic on identical features
 Still no scheduled Job required
What NOT to build
Slack/email, dashboards, warehouses if notebook suffices, ML metrics UI.

Likely difficulty
Low–medium. Parity bugs if float/column naming drifts.

Potential cost implications
Notebook cluster time only.

What you should understand personally
drivers as product UX, not debug dump
score_version discipline
Recommended Cursor prompt
Implement ONLY Stage 6 from PROJECT_PLAN.md.

Port the existing local heuristic_v1 unchanged onto gold_sunset_features,
write gold_sunset_scores, and create the simplest notebook/SQL today's card
(sunset time, score, drivers).

Do NOT schedule a Job, add alerts, ML, or later stages. No formula redesign
unless required for column-name mapping.

Stop point
You would actually open this card before sunset. Manual run is fine.

Stage 7 — Databricks Job
Status: Not started
Tags: Learning (orchestration) · Product (hands-off refresh)

Objective
Schedule the working pipeline as a daily Job; support manual rerun; idempotent; cheap cluster settings.

Why this milestone exists
Product: Prototype that updates without you babysitting notebooks.
Learning: Jobs vs interactive; task order; failure visibility.

Inputs
Stages 3–6 work when run manually in order
Expected outputs / artifacts
Databricks Job definition: ingest → silver → gold features → score (task split as simple as your tier allows)
Schedule: once daily late morning in location timezone (approx)
Notes: cluster size, max workers, auto-termination
Successful run history entry + manual “Run now” proof
Implementation tasks
Wire tasks to existing notebooks/wheels — avoid rewrite.
Schedule + timezone clarity.
Re-run same day twice; silver/gold remain correct.
Confirm cluster not left running.
Acceptance criteria
 Scheduled run produces/updates today’s card data
 Second run same day is safe (idempotent)
 You can find logs when something fails
 No always-on cluster required
What NOT to build
Airflow, sensors, multi-env promotion, alerts to PagerDuty, complex retry graphs.

Likely difficulty
Medium. Packaging/path/permission issues common.

Potential cost implications
Primary ongoing cost: daily job minutes. Keep cluster minimal; one location; don’t schedule hourly. Disable job if pausing the project.

What you should understand personally
What the Job would cost if it failed in a retry loop
Difference between job cluster and all-purpose cluster
Recommended Cursor prompt
Implement ONLY Stage 7 from PROJECT_PLAN.md.

Turn the existing manual Databricks bronze→silver→gold→score path into a
scheduled daily Job with manual rerun and idempotent writes. Use the smallest
reasonable job cluster and auto-termination.

Do NOT add Alerting products, Airflow, CI/CD, Terraform, extra environments,
or Stage 8/9 features.

Stop point
Two successful scheduled (or run-now) executions on different days, or same-day double run proving idempotency plus one next-day run.

Stage 8 — Validation (≈2 weeks)
Status: Not started
Tags: Product (trust) · Learning (evaluation mindset, not ML ops)

Objective
Compare heuristic to your eyes; tune weights; no ML.

Why this milestone exists
Product: Without calibration, the score is a toy.
Learning: Teaches evaluation discipline before model training.

Inputs
Stage 7 producing daily scores
Your ability to observe many sunsets at Home (weather permitting)
Expected outputs / artifacts
Simple log: date, your 1–5 rating, notes, model score, maybe top drivers (CSV, note app, or tiny Delta table — pick easiest)
Updated weights in heuristic_v1 with version bump if material
Short writeup: what the heuristic gets wrong
Implementation tasks
Choose logging medium (prefer dead simple).
Daily: record rating + notes.
Weekly: compare misses; adjust one weight family at a time.
Bump score_version when formula changes.
Acceptance criteria
 ≥ ~10 rated evenings OR two calendar weeks attempted
 You can cite 2 systematic errors (e.g. “punishes dry clear skies too hard”)
 Any weight change is versioned
 Still no ML training code
What NOT to build
Labeling apps, active learning, MLflow, automatic hyperparameter search.

Likely difficulty
Low engineering / medium discipline.

Potential cost implications
Job continues daily — pause if traveling and not observing.

What you should understand personally
Difference between forecast error and preference mismatch
When more features won’t fix a bad target definition
Recommended Cursor prompt
Implement ONLY Stage 8 support from PROJECT_PLAN.md: a minimal way to log
daily personal sunset ratings (1-5) alongside gold_sunset_scores for comparison.
Optional: helper to bump heuristic_v1 weights/version.

Do NOT add ML, MLflow, labeling UIs, or Stage 9 expansion.

Stop point
You either trust the score enough to expand locations, or you’ve documented why the heuristic needs different inputs (still not ML by default).

Stage 9 — Expansion (only after Stage 8)
Status: Gated
Tags: Product stretch · selective Learning

Objective
Add 2nd (then maybe 3rd) location; optionally personal notifications; only then consider simple UI or ML using collected ratings.

Why this milestone exists
Product: Multi-location and alerts are product surfaces.
Learning: Scaling locations tests whether silver grain and Job design were honest.

Inputs
Stage 8 insights; stable heuristic
Expected outputs / artifacts
Depends on chosen sub-scope — pick one expansion at a time:
9a. Second location in config + pipeline
9b. Personal notification (email/Slack) with draft-on-approval mindset
9c. Extremely simple read-only web page
9d. First ML experiment only if labels exist and heuristic plateaued

Implementation tasks
Define in a short addendum when you enter Stage 9; do not pre-design all four.

Acceptance criteria
Per chosen sub-scope; require updating this plan first.

What NOT to build
Full multi-event platform, auth system, mobile app store release, commercial data contracts (until needed).

Likely difficulty
Varies; 9a medium, 9b medium, 9c medium–high, 9d high.

Potential cost implications
Linear-ish in locations for API + slightly more compute; notifications cheap; web+auth not cheap in complexity.

What you should understand personally
Whether the architecture’s location_id grain was real or fake.

Recommended Cursor prompt
(Fill in only after updating PROJECT_PLAN Stage 9 with the single chosen expansion.)
Implement ONLY Stage 9a/9b/... as newly written in PROJECT_PLAN.md.
Do not include other expansions or deferred platform work.

Stop point
After each single expansion, re-validate cost and trust before the next.

10. Progress log
Date	Milestone	Result	Notes
2026-09-26	Plan authored	—	Awaiting D7/D8 before Stage 1

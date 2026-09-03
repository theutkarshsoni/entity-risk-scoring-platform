# Decisions Log

Format: Date — Decision — Why / trade-off

---

**2026-09-03** — `login_events` retains `source_country` as a direct field from the generator, rather than deriving it via a separate IP-to-country enrichment step in Silver.
Why: whether an auth system logs geolocation directly or only raw IP varies by real-world system maturity (e.g. Okta/Azure AD enrich at capture; simpler in-house systems don't) — both are defensible. Since entity resolution (system_identifier → entity_id) already forces a genuine lookup/join in Silver, an IP-geo enrichment step would duplicate that skill rather than add a new one, so it wasn't worth the added dependency it would create for impossible-travel scoring.

**2026-09-03** — Data generation split into two distinct phases: an 8-month historical backfill (Jan 1 – Aug 31, 2026), generated once as a batch job, used for exploration and calibrating scoring logic; and live streaming generation (Sep 1, 2026 onward) via rate source + AvailableNow trigger, treated as held-out test data to validate the pipeline/model against unseen data — analogous to a train/test split.
Final parameters: 100 entities (70 human / 20 service_account / 10 agent), 10% dirty-data rate, 5% anomaly rate (both tunable), JSON landing format.

**2026-09-03** — Bronze→Silver uses a quarantine pattern, not row-dropping. Bronze retains all raw rows unfiltered. Rows that pass structural checks (resolvable entity, valid/correctable timestamp, valid types) move to Silver. Rows that fail move to a `_quarantine` table — preserved, not deleted, for human investigation of root cause. DLT expectations mostly use `warn` (log + keep, after correction) rather than `drop`; a small subset of unrecoverable failures (e.g. entity_id unresolvable against dim_entity) route to quarantine instead of Silver, since an event that can't be attached to an entity can't be scored — but it is never deleted.
Why: reflects real-world constraint that signal must not be lost alongside noise — an anomalous event that's also malformed must still surface, not silently vanish with a dropped row.

**2026-09-03** — Use Structured Streaming with a synthetic rate source for ingestion, feeding a landing zone that Auto Loader reads into Bronze — rather than a plain script writing files directly.
Why: exercises real streaming semantics (watermarks, checkpointing) while keeping Auto Loader in the pipeline story.

**2026-09-03** — Use `Trigger.AvailableNow` instead of continuous/always-on streaming, orchestrated via a scheduled Databricks Job.
Why: Databricks Free Edition is serverless-only with fair-usage quotas; exceeding them shuts down compute for the rest of the day (or month). AvailableNow processes available data then stops, simulating streaming behavior within free-tier limits — also a legitimate cost-driven pattern used in real production pipelines.

**2026-09-03** — `dim_entity` and `access_grants` will be static (Phase 1), with SCD Type 2 added as an explicit Phase 1.5, not built in from day one.
Why: isolates the complexity of point-in-time joins and change-tracking so it's debuggable on its own, after the core pipeline already works end-to-end.

**2026-09-03** — Power BI connects via DirectQuery on a Databricks SQL Warehouse, not Import mode.
Why: live queries against Gold, more realistic to a production BI setup, at the cost of needing SQL Warehouse compute running for report access.

**2026-09-03** — Gold layer stores per-feature score contributions (e.g. `travel_score`, `access_violation_score`, `volume_anomaly_score`) alongside the final aggregated score, not just the final number.
Why: explainability — lets Power BI and the future LangGraph agent (Phase 2) show which feature drove a given risk score.

**2026-09-03** — Ground truth anomalies are injected directly by the synthetic data generator and logged to a separate `ground_truth_anomalies` table, never written into Bronze/Silver/Gold.
Why: gives an objective way to validate detection — otherwise there's no way to confirm the scoring model actually catches what it's supposed to.

**2026-09-03** — DLT pipelines will be implemented as file-based `.py` Lakeflow pipelines (not notebooks) for production logic; notebooks are used only for exploration.
Why: cleaner git diffs, testable/importable code, closer to real engineering practice — matches the CV-relevant framing of the project.

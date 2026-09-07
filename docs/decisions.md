# Decisions Log

Format: Date — Decision — Why / trade-off

---

**2026-09-07** — Confirmed as expected: 4 of 100 entities receive zero access_grants. These are Fully-autonomous service_accounts/agents in roles (ci-cd, security-scanning) whose entire candidate resource set is high-sensitivity — the autonomy cap correctly excludes all of it. Reflects a deliberate design consequence: autonomy posture can disqualify an entity from all resources its own job function would otherwise require.

**2026-09-07** — access_grants generation locked: every entity gets all role-mapped resources (not a subset), capped by tier for humans (Junior excluded from all high-sensitivity) and by autonomy level for non-humans (Fully-autonomous excluded from all high; Semi-autonomous excluded from admin_credentials_vault, security_audit_logs, legal_case_files specifically). High-sensitivity grants are approved by a Manager-tier entity (same role for humans, any Engineering Manager for non-humans) with a 90-day expiry; low/medium grants are system-issued ("SYSTEM") with no expiry. A safety-net fallback to "SYSTEM" applies if no qualifying Manager exists for a given role — confirmed to fire correctly in practice (7 grants, all Senior-tier Finance/HR, where no Manager existed in that role).

**2026-09-07** — access_grants generator performance: initial implementation ran ~4-5 minutes due to repeated Spark DataFrame `.filter().first()`/`.collect()` calls inside the per-entity loop (one Spark action per resource lookup, ~300+ actions total). Fixed by precomputing all reference lookups (resources, managers-by-role) into plain Python dicts once, outside the loop, reducing total Spark actions to ~3 and runtime to sub-second.
Why: Spark actions carry fixed distributed-job overhead regardless of data size; small static reference tables (16 resources, ~25 managers) should be collected once into Python structures, not re-queried as DataFrames inside a loop. This pattern will matter more, not less, once event generators run at real volume.

**2026-09-05** — Human role naming uses "IT" not "IT/Admin" in code (schema doc originally said IT/Admin) — slash risked future parsing issues. Schema doc updated to match code.

**2026-09-04** — Anomaly and dirty-data rates are no longer fixed (originally 5%/10%). Rates are now randomized hierarchically: a month-level base rate drawn from a Beta distribution (skewed low, occasionally elevated) within range (anomaly 0-10%, dirty 0-20%), with day-level rates jittered around that month's base and clipped to range. Each event independently applies that day's resolved rate. Live streaming reuses the calendar day's rate across all runs that day, rather than adding a third randomization level.
Why: a fixed rate doesn't mirror real-world clustering (bad weeks/months vs. quiet periods); the hierarchical approach produces natural elevated periods without manually scripting them, while staying simple — two levels, not three.

**2026-09-03** — `login_events` retains `source_country` as a direct field from the generator, rather than deriving it via a separate IP-to-country enrichment step in Silver.
Why: whether an auth system logs geolocation directly or only raw IP varies by real-world system maturity (e.g. Okta/Azure AD enrich at capture; simpler in-house systems don't) — both are defensible. Since entity resolution (system_identifier → entity_id) already forces a genuine lookup/join in Silver, an IP-geo enrichment step would duplicate that skill rather than add a new one, so it wasn't worth the added dependency it would create for impossible-travel scoring.

**2026-09-03** — Data generation split into two distinct phases: an 8-month historical backfill (Jan 1 – Aug 31, 2026), generated once as a batch job, used for exploration and calibrating scoring logic; and live streaming generation (Sep 1, 2026 onward) via rate source + AvailableNow trigger, treated as held-out test data to validate the pipeline/model against unseen data — analogous to a train/test split.
Final parameters: 100 entities (68 human / 21 service_account / 11 agent), hierarchical dirty/anomaly rates (see 2026-09-04 entry), JSON landing format.

**2026-09-03** — Bronze→Silver uses a quarantine pattern, not row-dropping. Bronze retains all raw rows unfiltered. Rows that pass structural checks (resolvable entity, valid/correctable timestamp, valid types) move to Silver. Rows that fail move to a `_quarantine` table — preserved, not deleted, for human investigation of root cause. DLT expectations mostly use `warn` (log + keep, after correction) rather than `drop`; a small subset of unrecoverable failures (e.g. entity_id unresolvable against dim_entity) route to quarantine instead of Silver, since an event that can't be attached to an entity can't be scored — but it is never deleted.
Why: reflects real-world constraint that signal must not be lost alongside noise — an anomalous event that's also malformed must still surface, not silently vanish with a dropped row.

**2026-09-03** — Use Structured Streaming with a synthetic rate source for ingestion, feeding a landing zone that Auto Loader reads into Bronze — rather than a plain script writing files directly.
Why: exercises real streaming semantics (watermarks, checkpointing) while keeping Auto Loader in the pipeline story.

**2026-09-03** — Use `Trigger.AvailableNow` instead of continuous/always-on streaming, orchestrated via a scheduled Databricks Job.
Why: Databricks Free Edition is serverless-only with fair-usage quotas; exceeding them shuts down compute for the rest of the day (or month). AvailableNow processes available data then stops, simulating streaming behavior within free-tier limits — also a legitimate cost-driven pattern used in real production pipelines.

**2026-09-03** — `dim_entity` and `access_grants` will be static (Phase 1), with SCD Type 2 added as an explicit Phase 1.5, not built in from day one (both `dim_entity` and `access_grants` get SCD2 treatment in Phase 1.5).
Why: isolates the complexity of point-in-time joins and change-tracking so it's debuggable on its own, after the core pipeline already works end-to-end.

**2026-09-03** — Power BI connects via DirectQuery on a Databricks SQL Warehouse, not Import mode.
Why: live queries against Gold, more realistic to a production BI setup, at the cost of needing SQL Warehouse compute running for report access.

**2026-09-03** — Gold layer stores per-feature score contributions (e.g. `travel_score`, `access_violation_score`, `volume_anomaly_score`) alongside the final aggregated score, not just the final number.
Why: explainability — lets Power BI and the future LangGraph agent (Phase 2) show which feature drove a given risk score.

**2026-09-03** — Ground truth anomalies are injected directly by the synthetic data generator and logged to a separate `ground_truth_anomalies` table, never written into Bronze/Silver/Gold.
Why: gives an objective way to validate detection — otherwise there's no way to confirm the scoring model actually catches what it's supposed to.

**2026-09-03** — DLT pipelines will be implemented as file-based `.py` Lakeflow pipelines (not notebooks) for production logic; notebooks are used only for exploration. The static reference-data generators (entities, resources, access_grants) are an exception — genuinely one-time, notebooks are fine for these. Event generators (backfill + streaming, run repeatedly) should be `.py` modules with importable functions.
Why: cleaner git diffs, testable/importable code, closer to real engineering practice — matches the CV-relevant framing of the project.

**2026-09-03** — Entity resolution deliberately uses the "messy org" model: each system uses its own local identifier for the same entity (email vs. user_id vs. service_account_name), reconciled via `entity_system_identifiers`, rather than a single universal entity_id logged everywhere.
Why: more representative of real organizations with disparate/legacy systems, and keeps entity resolution a genuine Silver-layer problem to solve rather than schema'd away — directly relevant to what the SMBC Insider Risk role described (data landscape spanning many systems).

**2026-09-03** — Seed/reference data (entities, access_grants, resources) is written to a `seed_data` schema first, then loaded into Bronze via a separate ingestion step — even though the load is a straight copy with no cleaning needed — rather than writing directly to Bronze.
Why: keeps the mental model consistent with event tables (data lands somewhere, then Auto Loader/DLT ingests it into Bronze) — seed_data represents "the world as it really is," Bronze represents "what the pipeline has ingested so far."
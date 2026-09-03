# Decisions Log

Format: Date — Decision — Why / trade-off

---

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

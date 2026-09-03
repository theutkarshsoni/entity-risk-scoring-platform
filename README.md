# Entity Risk Scoring Platform

A synthetic, end-to-end data engineering project simulating an insider-risk-style entity risk scoring system, built on Databricks (Azure), covering PySpark, SQL, Delta Live Tables, Databricks Jobs, and Power BI. Phase 2 adds a LangGraph agent for automated anomaly investigation summaries.

## Problem

Organizations need to detect anomalous behavior across human users, service accounts, and AI agents — e.g. impossible travel, unapproved access to sensitive resources, abnormal activity volume — using activity logs from multiple, independently-schemed source systems.

This project builds a pipeline that ingests synthetic multi-source event data, resolves entities across systems, engineers risk features, and produces an explainable daily risk score per entity, surfaced through a Power BI dashboard.

## Architecture

- **Ingestion**: Spark Structured Streaming (synthetic rate source) → landing zone → Auto Loader → Bronze
- **Bronze**: raw, untouched events per source system
- **Silver**: cleaned, normalized, entity-resolved (via `dim_entity`)
- **Gold**: aggregated features + risk scores, with per-feature contribution breakdown
- **Orchestration**: Databricks Jobs (scheduled, `Trigger.AvailableNow` — see `/docs/decisions.md`)
- **Serving**: Power BI via DirectQuery on a Databricks SQL Warehouse
- **Validation**: injected known anomalies compared against pipeline output (`ground_truth_anomalies`)

*(Architecture diagram — TODO)*

## Phases

- **Phase 1**: Core pipeline, static `dim_entity` / `access_grants`, batch + streaming ingestion, scoring, Power BI
- **Phase 1.5**: SCD Type 2 on `dim_entity` and `access_grants`, point-in-time joins
- **Phase 2**: LangGraph agent for plain-English investigation summaries on flagged entities

## Repo structure

See folder layout below. Key decisions and trade-offs are logged in `/docs/decisions.md` as they're made.

## Status

🚧 In progress — Phase 1

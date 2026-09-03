# Entity Risk Scoring Platform — Schema Reference

Locked schema for all synthetic data generator tables. Eight reference/event tables plus the validation table, nine total.

---

## Reference layer

### `dim_entity`
One row per entity. Core identity attributes only — never a per-system identifier (see `entity_system_identifiers`).

| Field | Type | Notes |
|---|---|---|
| entity_id | UUID (PK) | System-generated, never reused |
| entity_type | string | `human` / `service_account` / `agent` |
| role | string | Human: Finance, Engineering, IT/Admin, HR, Sales. Service_account/agent: function (e.g. data-pipeline, backup-automation, monitoring, ci-cd, security-scanning, ai-assistant, integration) |
| tier | string | Human: Junior/Senior/Manager. Non-human: Supervised/Semi-autonomous/Fully-autonomous — acts as a *ceiling* on access grants, not a direct grant driver |
| activity_pattern | string, nullable | Service_account only: scheduled / triggered / always_on. Null for human and agent |
| home_country | string, nullable | Human only. Null for service_account and agent |
| created_at | timestamp | |

### `entity_system_identifiers`
Reconciliation table — one row per (entity, system). This is what makes entity resolution a real Silver-layer problem: each system uses its own local identifier for the same entity.

| Field | Type | Notes |
|---|---|---|
| entity_id | UUID (FK → dim_entity) | |
| system_name | string | auth / file_access / privileged_command / network_access |
| system_identifier | string | The local ID used by that system (email, user_id, service_account_name, etc.) — value varies per system, not just the field name |

### `dim_resource`
Fixed catalog, 16 resources, sensitivity pre-tagged (kept separate from `access_grants` so sensitivity can't desync).

| Field | Type | Notes |
|---|---|---|
| resource_id | string (PK) | |
| resource_name | string | e.g. internal_wiki, payroll_db, source_code_repo |
| resource_sensitivity | string | low / medium / high |

**Catalog:**

| Resource | Sensitivity |
|---|---|
| internal_wiki | low |
| team_calendar | low |
| shared_drive_general | low |
| project_tracker | low |
| customer_support_tickets | medium |
| vendor_contracts | medium |
| analytics_dashboard | medium |
| employee_directory | medium |
| payroll_db | medium |
| source_code_repo | high |
| deployment_pipeline | high |
| customer_pii_store | high |
| financial_reports | high |
| security_audit_logs | high |
| admin_credentials_vault | high |
| legal_case_files | high |

### `access_grants`
What each entity is actually permitted to access. Role determines the candidate resource set; for non-human entities, `tier` (autonomy level) caps that set further (cap thresholds = tunable parameter, decide at generator build time).

| Field | Type | Notes |
|---|---|---|
| grant_id | UUID (PK) | |
| entity_id | UUID (FK → dim_entity) | |
| resource_id | string (FK → dim_resource) | |
| granted_by | UUID (FK → dim_entity, self-referencing) | Auditability — who/what approved it |
| granted_at | timestamp | |
| expires_at | timestamp, nullable | Null = standing/permanent grant. Populated = temporary/test access |

---

## Event layer

Every event table carries `system_identifier` (its own system's local ID) — **never** `entity_id` directly. Resolving identifier → entity is Silver-layer work.

### `login_events`
Auth system.

| Field | Type | Notes |
|---|---|---|
| event_id | UUID (PK) | |
| system_identifier | string | email |
| login_timestamp | timestamp | |
| source_ip | string | |
| source_country | string | Direct field — real auth systems vary on whether they enrich at capture; treated as already-enriched here (see decisions log) |
| vpn_detected | boolean | |
| mfa_used | boolean | |
| login_result | string | success / failure |
| source_device | string | e.g. "Windows/Chrome", "iOS/Safari" |

### `file_access_events`
File/data system.

| Field | Type | Notes |
|---|---|---|
| event_id | UUID (PK) | |
| system_identifier | string | user_id |
| resource_id | string (FK → dim_resource) | |
| access_timestamp | timestamp | |
| action | string | read / write / download |
| data_volume_mb | float | Enables both count-based and volume-based anomaly detection (many-small vs few-large) |

### `privileged_command_events`
Admin/ops system.

| Field | Type | Notes |
|---|---|---|
| event_id | UUID (PK) | |
| system_identifier | string | service_account_name |
| command_timestamp | timestamp | |
| command | string | Exact command text |
| command_category | string | config_change / user_management / data_deletion / service_control / log_management / access_control |
| resource_id | string (FK → dim_resource), nullable | Populated only when target is a catalog resource |
| target_description | string, nullable | Free text, used when target isn't a catalog resource (e.g. "entity:E047 permissions", "deployment_server") |

### `network_access_events`
VPN/network system. Represents external egress — the second link in an exfiltration chain (large internal download → external transfer).

| Field | Type | Notes |
|---|---|---|
| event_id | UUID (PK) | |
| system_identifier | string | |
| access_timestamp | timestamp | |
| source_ip | string | |
| destination_ip | string | |
| destination_system | string | Internal system name, or external label (e.g. "external_cloud_storage", "personal_email", "unknown_external") |
| bytes_transferred | float | |

---

## Validation layer

### `ground_truth_anomalies`
Written only by the generator's anomaly-injection logic. Never touched by Bronze/Silver/Gold pipeline code — this is the private answer key for validating detection recall and scoring sensitivity.

| Field | Type | Notes |
|---|---|---|
| anomaly_id | UUID (PK) | |
| entity_id | UUID (FK → dim_entity) | |
| anomaly_type | string | impossible_travel / unapproved_access / volume_spike / off_hours / dormant_reactivation / peer_group_deviation |
| source_table | string | Which event table the related events came from |
| related_event_ids | array\<UUID\> | Multi-event — most anomaly types are patterns across several rows, not one |
| injected_at | timestamp | |
| injected_severity | value, type varies by anomaly_type | Meaningful *within* a type only (e.g. impossible_travel: country count; volume_spike: multiple of baseline). Scale decided per-type at generator build time |

---

## Anomaly types reference

| # | Anomaly | Baseline style | Applies to | Logic |
|---|---|---|---|---|
| 1 | impossible_travel | Rule-based | Human | 3+ distinct countries in 24hr window (2 = normal) |
| 2 | unapproved_access | Reference check | All | Access event with no matching row in `access_grants` (or past `expires_at`) |
| 3 | volume_spike | Historical-self baseline | Service_account, agent | Systems/resources/volume in an hour exceeds entity's own trailing baseline by a tunable multiple |
| 4 | off_hours | Rule-based / temporal | Human (always); service_account/agent (only if `activity_pattern = scheduled`) | Activity outside expected window. Not computed for triggered/always_on entities — no baseline exists |
| 5 | dormant_reactivation | Historical-self baseline | All | 30+ days zero activity, then sudden activity |
| 6 | peer_group_deviation | Relative/peer baseline | All | Entity's activity N std. deviations above mean for its role + entity_type peer group |

---

## Data quality (dirty-mode) reference

Independent of anomaly injection — same event can be both anomalous and dirty.

| Issue | Tests |
|---|---|
| Null/missing fields | Not-null expectations |
| Malformed timestamps | Type/format expectations |
| Duplicate event_id | Uniqueness expectations |
| Inconsistent casing/whitespace | Silver normalization logic |
| Out-of-order/late-arriving events | Freshness/ordering expectations, streaming watermarks |
| Schema drift (new optional field mid-stream) | Auto Loader schema evolution |

**Bronze → Silver routing:** Bronze retains everything, unfiltered. Silver receives rows that pass structural checks (resolvable entity, valid/correctable timestamp, valid types) — corrected in place where fixable. Rows that fail route to a `_quarantine` table — preserved, never deleted, for root-cause investigation. Most DLT expectations use `warn` rather than `drop`; only truly unresolvable rows (e.g. unmatchable entity) are excluded from Silver, and even those are quarantined, not discarded.

---

## Generation parameters (tunable)

| Parameter | Value |
|---|---|
| Entities | 100 total — 70 human / 20 service_account / 10 agent |
| Backfill period | Jan 1 – Aug 31, 2026 (batch, one-time) — exploration/train set |
| Streaming period | Sep 1, 2026 onward, via rate source + `Trigger.AvailableNow` — held-out test set |
| Dirty-data rate | 10% (tunable) |
| Anomaly rate | 5% (tunable) |
| Landing format | JSON |
| Autonomy access caps | Tunable, decide at generator build time |

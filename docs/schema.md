# Entity Risk Scoring Platform — Schema Reference

Locked schema for all synthetic data generator tables. Nine reference/event tables plus the validation table, ten total.

Table names below are as they exist at the `seed_data` stage (generator output). Names change at later pipeline stages per naming convention — e.g. `entities` becomes `dim_entity` only once it reaches Gold; see decisions log.

---

## Reference layer

### `entities` (seed_data) → `dim_entity` (Gold)
One row per entity. Core identity attributes only — never a per-system identifier (see `entity_system_identifiers`).

| Field | Type | Notes |
|---|---|---|
| entity_id | UUID (PK) | System-generated, never reused |
| entity_type | string | `human` / `service_account` / `agent` |
| role | string | Human: Finance, Engineering, IT, HR, Sales. Non-human: data-pipeline, backup-automation, monitoring, ci-cd, security-scanning, ai-assistant, integration |
| tier | string | Human: Junior/Senior/Manager (pyramid-weighted). Non-human: Supervised/Semi-autonomous/Fully-autonomous — acts as a *ceiling* on access grants, not a direct grant driver |
| activity_pattern | string, nullable | Service_account only: scheduled / triggered / always_on (skewed toward scheduled). Null for human and agent |
| home_country | string, nullable | Human only, within Europe. Null for service_account and agent |
| created_at | timestamp | |

**Volumes:** 100 entities total — 68 human / 21 service_account / 11 agent.
Human role weights: Finance 0.20, Engineering 0.35, IT 0.20, HR 0.10, Sales 0.15. Human tier weights: Junior 0.40, Senior 0.35, Manager 0.25.
Non-human role weights: data-pipeline 0.20, backup-automation 0.10, monitoring 0.10, ci-cd 0.15, security-scanning 0.15, ai-assistant 0.15, integration 0.15. Non-human tier weights: Supervised 0.30, Semi-autonomous 0.30, Fully-autonomous 0.40.

### `entity_system_identifiers`
Reconciliation table — one row per (entity, system) the entity actually participates in. **No row for a given (entity, system) pair means that entity is structurally incapable of generating events there** — event generators must check this table before producing an event, not assume every entity touches every system.

| Field | Type | Notes |
|---|---|---|
| entity_id | UUID (FK → entities) | |
| system_name | string | auth / file_access / privileged_command / network_access |
| system_identifier | string | The local ID used by that system — format varies per system (see below) |

**Identifier formats:**
- `auth` → `firstname.lastname@erspgroup.com`
- `file_access` → `U` + sequential number (e.g. `U00123`)
- `privileged_command` → `adm-<counter>` (privileged humans) or `svc-<function>-<counter>` (service_accounts) / `agt-<function>-<counter>` (agents)
- `network_access` → `WKS-<counter>` (humans) or `HOST-<function>-<counter>` (service_accounts/agents)

Uniqueness is enforced via sequential counters per identifier type, not random ranges (random collided in early testing at this row count).

**Which entities get which systems:**
- `auth`: humans only, always
- `file_access`: all entities, always
- `network_access`: all entities, always
- `privileged_command`:
  - Human: `tier == "Manager"` (any role) **OR** (`role == "IT"` AND `tier == "Senior"`)
  - Non-human: `role in ["ci-cd", "security-scanning", "backup-automation"]`

### `resources`
Fixed catalog, 16 resources, sensitivity pre-tagged (kept separate from `access_grants` so sensitivity can't desync).

| Field | Type | Notes |
|---|---|---|
| resource_id | UUID (PK) | |
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
What each entity is actually permitted to access. Every entity is granted its **full** role-mapped resource set (no random subset) — capped by tier (human) or autonomy level (non-human).

| Field | Type | Notes |
|---|---|---|
| grant_id | UUID (PK) | |
| entity_id | UUID (FK → entities) | |
| resource_id | UUID (FK → resources) | |
| granted_by | UUID (FK → entities, self-referencing) or `"SYSTEM"` | See rule below |
| granted_at | timestamp | |
| expires_at | timestamp, nullable | See rule below |

**Role → resource mapping.**
Human common baseline (every human role, in addition to role-specific): `internal_wiki`, `team_calendar`, `project_tracker`.

| Human role | Additional resources |
|---|---|
| Finance | payroll_db, financial_reports, vendor_contracts |
| Engineering | source_code_repo, deployment_pipeline, shared_drive_general |
| IT | admin_credentials_vault, security_audit_logs, deployment_pipeline, employee_directory |
| HR | employee_directory, payroll_db, legal_case_files |
| Sales | customer_pii_store, customer_support_tickets, vendor_contracts, analytics_dashboard |

| Non-human role | Resources (no common baseline) |
|---|---|
| data-pipeline | analytics_dashboard, customer_pii_store, shared_drive_general |
| backup-automation | shared_drive_general, security_audit_logs |
| monitoring | security_audit_logs, analytics_dashboard |
| ci-cd | source_code_repo, deployment_pipeline |
| security-scanning | security_audit_logs, admin_credentials_vault, source_code_repo |
| ai-assistant | internal_wiki, customer_support_tickets, analytics_dashboard |
| integration | shared_drive_general, analytics_dashboard, customer_pii_store |

**Tier/autonomy cap (applied on top of the role-mapped set):**
- Human `Junior` → excluded from all `high`-sensitivity resources. `Senior`/`Manager` → uncapped.
- Non-human `Fully-autonomous` → excluded from all `high`-sensitivity resources.
- Non-human `Semi-autonomous` → excluded specifically from `admin_credentials_vault`, `security_audit_logs`, `legal_case_files` (not all high-sensitivity resources).
- Non-human `Supervised` → uncapped.
- **Known consequence**: entities with role `ci-cd` or `security-scanning` AND tier `Fully-autonomous` receive **zero grants** — their entire candidate resource set is high-sensitivity. Confirmed intentional, not a bug (see decisions log).

**`granted_by` / `expires_at` rule:**
- Resource is **high**-sensitivity → `granted_by` = a randomly chosen Manager-tier entity (same role as grantee if human; any Engineering-role Manager if non-human), `expires_at` = `granted_at + 90 days`. If no qualifying Manager exists for that role, falls back to `granted_by = "SYSTEM"` (confirmed to occur legitimately — e.g. Senior-tier Finance/HR grants when no Finance/HR Manager exists in the generated population).
- Resource is **low/medium**-sensitivity → `granted_by = "SYSTEM"`, `expires_at = null`.

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
| resource_id | string (FK → resources) | |
| access_timestamp | timestamp | |
| action | string | read / write / download |
| data_volume_mb | float | Enables both count-based and volume-based anomaly detection (many-small vs few-large) |

### `privileged_command_events`
Admin/ops system.

| Field | Type | Notes |
|---|---|---|
| event_id | UUID (PK) | |
| system_identifier | string | service_account_name / adm-name |
| command_timestamp | timestamp | |
| command | string | Exact command text |
| command_category | string | config_change / user_management / data_deletion / service_control / log_management / access_control |
| resource_id | string (FK → resources), nullable | Populated only when target is a catalog resource |
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
| entity_id | UUID (FK → entities) | |
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
| Entities | 100 total — 68 human / 21 service_account / 11 agent |
| Backfill period | Jan 1 – Aug 31, 2026 (batch, one-time) — exploration/train set |
| Streaming period | Sep 1, 2026 onward, via rate source + `Trigger.AvailableNow` — held-out test set |
| Dirty-data rate | Hierarchical (month base rate via Beta distribution 0-20%, day-level jitter) — see decisions log |
| Anomaly rate | Hierarchical (month base rate via Beta distribution 0-10%, day-level jitter) — see decisions log |
| Landing format | JSON |
| Access grant expiry (high-sensitivity) | 90 days from granted_at |

---

## Naming convention across pipeline stages

Table names reflect their pipeline stage, not a fixed identity:
- `seed_data.<name>` — raw generator output (e.g. `entities`, `resources`)
- `bronze.<name>` — ingested as-is
- `silver.<name>` — cleaned/validated/resolved
- `gold.dim_<name>` / `gold.fact_<name>` — dimensional-modeling names apply only at Gold, once the table is genuinely conformed for BI consumption
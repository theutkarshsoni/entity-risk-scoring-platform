import uuid
import datetime
import random
from pyspark.sql.functions import col

# Human common resources
human_common_resources = ["internal_wiki", "team_calendar", "project_tracker"]

# Human role resources mapping
human_role_resources = {
    "Finance": ["payroll_db", "financial_reports", "vendor_contracts"],
    "Engineering": ["source_code_repo", "deployment_pipeline", "shared_drive_general"],
    "IT": ["admin_credentials_vault", "security_audit_logs", "deployment_pipeline", "employee_directory"],
    "HR": ["employee_directory", "payroll_db", "legal_case_files"],
    "Sales": ["customer_pii_store", "customer_support_tickets", "vendor_contracts", "analytics_dashboard"],
}

# Non-human role resources mapping
non_human_role_resources = {
    "data-pipeline": ["analytics_dashboard", "customer_pii_store", "shared_drive_general"],
    "backup-automation": ["shared_drive_general", "security_audit_logs"],
    "monitoring": ["security_audit_logs", "analytics_dashboard"],
    "ci-cd": ["source_code_repo", "deployment_pipeline"],
    "security-scanning": ["security_audit_logs", "admin_credentials_vault", "source_code_repo"],
    "ai-assistant": ["internal_wiki", "customer_support_tickets", "analytics_dashboard"],
    "integration": ["shared_drive_general", "analytics_dashboard", "customer_pii_store"],
}

# Very high risk resources
very_high_risk_resources = ["admin_credentials_vault", "security_audit_logs", "legal_case_files"]


entities_df = spark.read.table("entity_risk_platform.seed_data.entities").select("entity_id", "entity_type", "role", "tier")

resources_df = spark.read.table("entity_risk_platform.seed_data.resources")

# Manager dict
manager_dict = {}
for row in entities_df.filter(col("tier") == "Manager").collect():
    manager_dict.setdefault(row["role"], []).append(row["entity_id"])    

# Resource dict
resource_dict = { row["resource_name"]: (row["resource_id"], row["resource_sensitivity"]) for row in resources_df.collect() }

high_sensitive_resources = [r_name for r_name, (r_id, r_sensitivity) in resource_dict.items() if r_sensitivity == "high"]

very_high_sensitive_resources = [r_name for r_name in resource_dict if r_name in very_high_risk_resources]


new_grant_list = []

def generate_grant(entity_id, resource_id, granter, grant_date, expiry_date):
    grant_id = str(uuid.uuid4())
    return {
        "grant_id": grant_id,
        "entity_id": entity_id,
        "resource_id": resource_id,
        "granted_by": granter, 
        "granted_at": grant_date,
        "expires_at": expiry_date
    } 

def generate_grant_list(resources, role, entity):
    for resource in resources:
      r_id, r_sensitivity = resource_dict[resource]
      now = datetime.datetime.now()
      if r_sensitivity == "high":
        manager_ids = manager_dict.get(role, [])
        granter = random.choice(manager_ids) if manager_ids else "SYSTEM"
        new_grant_list.append(generate_grant(entity, r_id, granter, now, now + datetime.timedelta(days=90)))
      else:
        new_grant_list.append(generate_grant(entity, r_id, "SYSTEM", now, None))

for entity in entities_df.collect():
  row = entity.asDict()
  if row["entity_type"] == "human":
    human_resources = human_common_resources + human_role_resources[row["role"]]
    if row["tier"] == "Junior" :
      human_resources = [hr for hr in human_resources if hr not in high_sensitive_resources]
    generate_grant_list(human_resources, row["role"], row["entity_id"])
  if row["entity_type"] in ("service_account", "agent") :
    non_human_resources = non_human_role_resources[row["role"]]
    if row["tier"] == "Fully-autonomous":
      non_human_resources = [nhr for nhr in non_human_resources if nhr not in high_sensitive_resources]
    if row["tier"] == "Semi-autonomous":
      non_human_resources = [nhr for nhr in non_human_resources if nhr not in very_high_sensitive_resources]
    generate_grant_list(non_human_resources, "Engineering", row["entity_id"])

grant_df = spark.createDataFrame(new_grant_list)
grant_df.show()

# Create catalog and schema if they don't exist
spark.sql("CREATE CATALOG IF NOT EXISTS entity_risk_platform")
spark.sql("CREATE SCHEMA IF NOT EXISTS entity_risk_platform.seed_data")

grant_df.write.format("delta").mode("overwrite").saveAsTable("entity_risk_platform.seed_data.access_grants")
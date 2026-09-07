import uuid

# Resource Catalog
resource_catalog = [
    ("internal_wiki", "low"),
    ("team_calendar", "low"),
    ("shared_drive_general", "low"),
    ("project_tracker", "low"),
    ("customer_support_tickets", "medium"),
    ("vendor_contracts", "medium"),
    ("analytics_dashboard", "medium"),
    ("employee_directory", "medium"),
    ("payroll_db", "medium"),
    ("source_code_repo", "high"),
    ("deployment_pipeline", "high"),
    ("customer_pii_store", "high"),
    ("financial_reports", "high"),
    ("security_audit_logs", "high"),
    ("admin_credentials_vault", "high"),
    ("legal_case_files", "high"),
]

new_resource_list = []

for resource in resource_catalog:
    new_resource_list.append({
        "resource_id": str(uuid.uuid4()),
        "resource_name": resource[0], 
        "resource_sensitivity": resource[1]
    })

resource_df = spark.createDataFrame(new_resource_list)
resource_df.show()

# Create catalog and schema if they don't exist
spark.sql("CREATE CATALOG IF NOT EXISTS entity_risk_platform")
spark.sql("CREATE SCHEMA IF NOT EXISTS entity_risk_platform.seed_data")

resource_df.write.format("delta").mode("overwrite").saveAsTable("entity_risk_platform.seed_data.resources")
%pip install faker

from faker import Faker

# Company domain
email_domain = "erspgroup.com"

# Global Counters
counters = {
    "e_counter": 0,
    "u_counter": 0,
    "a_counter": 0,
    "m_counter": 0
}

fake_person = Faker()

def generate_email():
    counters["e_counter"] += 1
    return fake_person.first_name().lower() + "." + fake_person.last_name().lower() +  "." + str(counters["e_counter"]) + "@" + email_domain

def generate_userid():
    counters["u_counter"] += 1
    return "U00" + str(counters["u_counter"])

def generate_access_name(entity_type, entity_role):
    counters["a_counter"] += 1
    if entity_type == "human":
        return "adm-" + str(counters["a_counter"])
    if entity_type == "service_account": 
        return "svc-" + entity_role + "-" + str(counters["a_counter"])
    if entity_type == "agent": 
        return "agt-" + entity_role + "-" + str(counters["a_counter"])

def generate_machine_name(entity_type, entity_role):
    counters["m_counter"] += 1
    if entity_type == "human":
        return "WKS-" + str(counters["m_counter"])
    if entity_type in ("service_account", "agent"): 
        return "HOST-" + entity_role + "-" + str(counters["m_counter"])

df = spark.read.table("entity_risk_platform.seed_data.entities")
all_entities = df.select("entity_id", "role", "entity_type", "tier")

new_system_identifier_list = []

def generate_identifier(entity_id, system_name, identifier): 
    return {"entity_id": entity_id, "system_name": system_name, "system_identifier": identifier}

def process_entity(entity):
    # Auth Identifier
    if(entity["entity_type"] == "human"):
        new_system_identifier_list.append(generate_identifier(entity["entity_id"], "auth", generate_email()))
    # File Identifier
    new_system_identifier_list.append(generate_identifier(entity["entity_id"], "file_access", generate_userid()))
    # Command Identifier
    if(entity["entity_type"] == "human"):
        if(entity["tier"] == "Manager" or (entity["tier"] == "Senior" and entity["role"] == "IT")):
            new_system_identifier_list.append(generate_identifier(entity["entity_id"], "privileged_command", generate_access_name(entity["entity_type"], entity["role"])))
    if(entity["entity_type"] in ("service_account", "agent")):
        if(entity["role"] in ["ci-cd", "security-scanning", "backup-automation"]):
            new_system_identifier_list.append(generate_identifier(entity["entity_id"], "privileged_command", generate_access_name(entity["entity_type"], entity["role"])))
    # Network Identifier
    new_system_identifier_list.append(generate_identifier(entity["entity_id"], "network_access", generate_machine_name(entity["entity_type"], entity["role"])))

for row in all_entities.collect():
    process_entity(row.asDict())

identifier_df = spark.createDataFrame(new_system_identifier_list)
identifier_df.show()

# Create catalog and schema if they don't exist
spark.sql("CREATE CATALOG IF NOT EXISTS entity_risk_platform")
spark.sql("CREATE SCHEMA IF NOT EXISTS entity_risk_platform.seed_data")

identifier_df.write.format("delta").mode("overwrite").saveAsTable("entity_risk_platform.seed_data.entity_system_identifiers")
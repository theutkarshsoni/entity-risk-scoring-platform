import uuid
import datetime
import random

# List of 44 european countries
europe_countries = [
    "Albania", "Andorra", "Austria", "Belarus", "Belgium", 
    "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus", "Czechia", 
    "Denmark", "Estonia", "Finland", "France", "Germany", 
    "Greece", "Hungary", "Iceland", "Ireland", "Italy", 
    "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta", 
    "Moldova", "Monaco", "Montenegro", "Netherlands", "North Macedonia", 
    "Norway", "Poland", "Portugal", "Romania", "Russia", 
    "San Marino", "Serbia", "Slovakia", "Slovenia", "Spain", 
    "Sweden", "Switzerland", "Ukraine", "United Kingdom"
]

# Specs of activity pattern
activity_patterns  = ["scheduled", "triggered",  "always_on"]
activity_weights = [0.5, 0.3, 0.2]

# Specs of role
human_roles = ["Finance", "Engineering", "IT", "HR", "Sales"]
human_role_weights = [0.20, 0.35, 0.20, 0.10, 0.15]
non_human_roles = ["data-pipeline", "backup-automation", "monitoring", "ci-cd", "security-scanning", "ai-assistant", "integration"]
non_human_role_weights = [0.20, 0.10, 0.10, 0.15, 0.15, 0.15, 0.15]

# Specs of tier
human_tiers = ["Junior", "Senior", "Manager"]
human_tier_weights = [0.40, 0.35, 0.25]
non_human_tiers = ["Supervised", "Semi-autonomous", "Fully-autonomous"]
non_human_tier_weights = [0.30, 0.30, 0.40]


new_entity_list = []

def generate_entities(entity_type, count, roles, role_weights, tiers, tier_weights, patterns, patterns_weights, countiers):
    for i in range (count):
        entity = {}
        entity["entity_id"] = str(uuid.uuid4())
        entity["created_at"] = datetime.datetime.now()
        entity["entity_type"] = entity_type
        role = random.choices(roles, weights=role_weights, k=1)[0] # The "Loaded Dice" Approach
        entity["role"] = role
        tier = random.choices(tiers, weights=tier_weights, k=1)[0]
        entity["tier"] = tier
        pattern = random.choices(patterns, weights=patterns_weights, k=1)[0] if (patterns and patterns_weights) else None
        entity["activity_pattern"] = pattern
        country = random.choice(countiers) if countiers else None
        entity["home_country"] = country
        new_entity_list.append(entity)

# Generate human entities
generate_entities("human", 68, human_roles, human_role_weights, human_tiers, human_tier_weights, None, None, europe_countries)
# Generate service account entities
generate_entities("service_account", 21, non_human_roles, non_human_role_weights, non_human_tiers, non_human_tier_weights, activity_patterns, activity_weights, None)
# Generate agent entities
generate_entities("agent", 11, non_human_roles, non_human_role_weights, non_human_tiers, non_human_tier_weights, None, None, None)

df = spark.createDataFrame(new_entity_list)
df.show()

# Create catalog and schema if they don't exist
spark.sql("CREATE CATALOG IF NOT EXISTS entity_risk_platform")
spark.sql("CREATE SCHEMA IF NOT EXISTS entity_risk_platform.seed_data")

df.write.format("delta").mode("overwrite").saveAsTable("entity_risk_platform.seed_data.entities")
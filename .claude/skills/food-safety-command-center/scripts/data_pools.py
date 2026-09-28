"""Generic (non-customer-specific) name/value pools for demo data generation.

Deliberately brand-neutral: no real chain's addresses, employee names, or
auditor names. Swap or extend these lists per engagement if a colleague
wants a specific region flavor — they're plain data, not templated code.
"""

REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "Mountain"]

# (city, state, region) — region chosen to keep a plausible regional grouping;
# state postal code is used by the workbook's region-map formula.
CITIES = [
    ("Springfield", "IL", "Midwest"),
    ("Riverside", "CA", "West"),
    ("Franklin", "TN", "Southeast"),
    ("Georgetown", "TX", "Southwest"),
    ("Bristol", "CT", "Northeast"),
    ("Fairview", "OH", "Midwest"),
    ("Clayton", "MO", "Midwest"),
    ("Salem", "OR", "West"),
    ("Madison", "WI", "Midwest"),
    ("Greenville", "SC", "Southeast"),
    ("Denton", "TX", "Southwest"),
    ("Boulder", "CO", "Mountain"),
    ("Hamilton", "OH", "Midwest"),
    ("Lakeview", "GA", "Southeast"),
    ("Millbrook", "NY", "Northeast"),
    ("Ashland", "OR", "West"),
    ("Bellevue", "WA", "West"),
    ("Concord", "NH", "Northeast"),
    ("Marion", "IN", "Midwest"),
    ("Auburn", "AL", "Southeast"),
    ("Chandler", "AZ", "Southwest"),
    ("Bozeman", "MT", "Mountain"),
    ("Naperville", "IL", "Midwest"),
    ("Fayetteville", "NC", "Southeast"),
    ("Napa", "CA", "West"),
]

STREET_NAMES = [
    "Main St", "Oak Ave", "Maple Dr", "Elm St", "Park Blvd", "Cedar Ln",
    "Washington Ave", "Sunset Rd", "Highland Dr", "River Rd", "Market St",
    "Church St", "Broadway", "Pine St", "Lincoln Ave",
]

FIRST_NAMES = [
    "Maria", "James", "Aisha", "Wei", "Carlos", "Emily", "David", "Sofia",
    "Michael", "Priya", "John", "Grace", "Daniel", "Olivia", "Marcus",
    "Elena", "Ryan", "Fatima", "Kevin", "Nina", "Andre", "Chloe", "Omar",
    "Lucy", "Tyler", "Amara", "Brian", "Yuki", "Diego", "Hannah",
]

LAST_NAMES = [
    "Alvarez", "Chen", "Patel", "Johnson", "Garcia", "Smith", "Nguyen",
    "Brown", "Kim", "Rodriguez", "Williams", "Lopez", "Davis", "Martin",
    "Hernandez", "Taylor", "Moore", "Jackson", "Thompson", "White",
]

FRANCHISE_OWNERS = [
    "Meridian Restaurant Group", "Coastal Hospitality Partners",
    "Summit Foodservice LLC", "Heritage Dining Group",
    "Crossroads Restaurant Holdings",
]

AUDIT_CATEGORIES = [
    "Temperature Control", "Sanitation", "Food Handling",
    "Documentation", "Pest Control", "Equipment Maintenance",
]

AUDIT_SEVERITIES = ["Low", "Medium", "High", "Critical"]

RISK_TIERS = ["Low", "Medium", "High", "Critical"]

TASK_CATALOG = [
    ("Cooler Temp Check", "Daily", "Temperature Control"),
    ("Freezer Temp Check", "Daily", "Temperature Control"),
    ("Handwashing Station Check", "Daily", "Sanitation"),
    ("Sanitizer Concentration Check", "Daily", "Sanitation"),
    ("Line Cleaning Log", "Daily", "Sanitation"),
    ("Pest Trap Inspection", "Weekly", "Pest Control"),
    ("Equipment Maintenance Check", "Weekly", "Equipment Maintenance"),
    ("Food Rotation / FIFO Check", "Weekly", "Food Handling"),
]

ACTION_ITEM_ISSUES = [
    "Cooler running above target temperature",
    "Missing handwashing signage at prep station",
    "Sanitizer concentration below threshold",
    "Expired product found in walk-in",
    "Pest activity noted near receiving door",
    "Employee food-handler certification expired",
    "Incomplete temperature log for prior shift",
    "Cross-contamination risk at prep line",
    "Freezer door seal damaged",
    "Hand sink obstructed by storage",
]

ACTION_PRIORITIES = ["Low", "Medium", "High"]
ACTION_STATUSES = ["Open", "In Progress", "Complete"]

RESOLUTION_NOTES = [
    "Repaired and re-verified within target range.",
    "Retrained staff on procedure; re-checked next shift.",
    "Replaced faulty part; confirmed fix during follow-up visit.",
    "Escalated to maintenance vendor; resolved same week.",
    "Corrected immediately; no recurrence on follow-up audit.",
]

ROOT_CAUSES = [
    "Equipment wear", "Staff training gap", "Procedure not followed",
    "Vendor supply issue", "Scheduling gap in coverage",
]

EMPLOYEE_ROLES = ["General Manager", "Assistant Manager", "Shift Lead", "Team Member"]

PROMO_SEGMENTS = ["Value Seekers", "Loyalty Members", "Occasional Visitors", "New Customers"]
PROMO_CHANNELS = ["In-App", "Email", "In-Store Signage", "Social"]
PROMO_ITEMS = ["Combo Meal", "Limited-Time Entree", "Side Add-On", "Beverage Bundle"]

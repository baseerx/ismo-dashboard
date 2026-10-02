
EMPLOYEE_CATEGORIES = {
    "jamshoro": {
        "label": "Jamshoro Employees",
        "locations": ["ISMO-Jamshoro"],
    },
    "planning_lahore": {
        "label": "Planning & Lahore Employees",
        "locations": ["ISMO-Lahore"],
    },
    "cppa_mo": {
        "label": "CPPA / MO Employees",
        "locations": ["ISMO-Head Office", "ISMO-Shaheen Plaza"],
    },
}


def category_for_location(location_name):
    for key, cfg in EMPLOYEE_CATEGORIES.items():
        if location_name in cfg["locations"]:
            return key
    return None


def locations_for_category(key):
    cfg = EMPLOYEE_CATEGORIES.get(key)
    return set(cfg["locations"]) if cfg else set()


def category_options():
    return [{"key": "all", "label": "All Employees"}] + [
        {"key": key, "label": cfg["label"]}
        for key, cfg in EMPLOYEE_CATEGORIES.items()
    ]
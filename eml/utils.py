import json


def safe_json_list(value):
    try:
        return json.loads(value) if value else []
    except (TypeError, ValueError):
        return []

import os
import requests  # type: ignore


def check_grafana_connectivity():
    """Check if required Grafana environment variables are set and server is reachable"""
    REQUIRED_ENV_VARS = [
        "GRAFANA_URL",
        "GRAFANA_API_KEY",
    ]

    missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]

    if missing_vars:
        return f"{', '.join(missing_vars)} must be set"

    # Check if Grafana server is reachable
    try:
        GRAFANA_URL = os.environ.get("GRAFANA_URL", "")
        GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY")
        headers = {}
        if GRAFANA_API_KEY:
            headers["Authorization"] = f"Bearer {GRAFANA_API_KEY}"
        response = requests.get(f"{GRAFANA_URL}/ready", headers=headers, timeout=2)
        if response.status_code != 200:
            return f"Grafana server not reachable at {GRAFANA_URL}/ready (status: {response.status_code}). Set GRAFANA_URL and GRAFANA_API_KEY to run Grafana tests"
    except Exception:
        return f"Grafana server not reachable at {GRAFANA_URL}/ready. Set GRAFANA_URL and GRAFANA_API_KEY to run Grafana tests"

    return None

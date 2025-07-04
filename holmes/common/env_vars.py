import os
import json


def load_bool(env_var, default: bool):
    s = os.environ.get(env_var, str(default))
    return json.loads(s.lower())


ENABLED_BY_DEFAULT_TOOLSETS = os.environ.get(
    "ENABLED_BY_DEFAULT_TOOLSETS", "kubernetes/core,kubernetes/logs,robusta,internet"
)
HOLMES_HOST = os.environ.get("HOLMES_HOST", "0.0.0.0")
HOLMES_PORT = int(os.environ.get("HOLMES_PORT", 5050))
ROBUSTA_CONFIG_PATH = os.environ.get(
    "ROBUSTA_CONFIG_PATH", "/etc/robusta/config/active_playbooks.yaml"
)

ROBUSTA_ACCOUNT_ID = os.environ.get("ROBUSTA_ACCOUNT_ID", "")
STORE_URL = os.environ.get("STORE_URL", "")
STORE_API_KEY = os.environ.get("STORE_API_KEY", "")
STORE_EMAIL = os.environ.get("STORE_EMAIL", "")
STORE_PASSWORD = os.environ.get("STORE_PASSWORD", "")
HOLMES_POST_PROCESSING_PROMPT = os.environ.get("HOLMES_POST_PROCESSING_PROMPT", "")
ROBUSTA_AI = load_bool("ROBUSTA_AI", False)
ROBUSTA_API_ENDPOINT = os.environ.get("ROBUSTA_API_ENDPOINT", "https://api.robusta.dev")

LOG_PERFORMANCE = os.environ.get("LOG_PERFORMANCE", None)


ENABLE_TELEMETRY = load_bool("ENABLE_TELEMETRY", False)
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0"))

THINKING = os.environ.get("THINKING", "")
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.00000001"))

STREAM_CHUNKS_PER_PARSE = int(
    os.environ.get("STREAM_CHUNKS_PER_PARSE", 80)
)  # Empirical value with 6~ parsing calls. Consider using larger value if LLM response is long as to reduce markdown to section calls.

USE_LEGACY_KUBERNETES_LOGS = load_bool("USE_LEGACY_KUBERNETES_LOGS", False)
KUBERNETES_LOGS_TIMEOUT_SECONDS = int(
    os.environ.get("KUBERNETES_LOGS_TIMEOUT_SECONDS", 60)
)

import os

ALLOWED_TOOLSETS = os.environ.get('ALLOWED_TOOLSETS', '*')
HOLMES_HOST = os.environ.get('HOLMES_HOST', '0.0.0.0')
HOLMES_PORT = int(os.environ.get('HOLMES_PORT', 5050))
ROBUSTA_CONFIG_PATH = os.environ.get('ROBUSTA_CONFIG_PATH', "/etc/robusta/config/active_playbooks.yaml")

ROBUSTA_ACCOUNT_ID = os.environ.get("ROBUSTA_ACCOUNT_ID", "")
STORE_URL = os.environ.get("STORE_URL", "")
STORE_API_KEY = os.environ.get("STORE_API_KEY", "")
STORE_EMAIL = os.environ.get("STORE_EMAIL", "")
STORE_PASSWORD = os.environ.get("STORE_PASSWORD", "")
HOLMES_POST_PROCESSING_PROMPT = os.environ.get("HOLMES_POST_PROCESSING_PROMPT", "")

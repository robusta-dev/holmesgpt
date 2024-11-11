
import os

from holmes.config import Config
from holmes.core.supabase_dal import SupabaseDal
from pydantic import SecretStr


def load_robusta_api_key(dal:SupabaseDal, config:Config):
    if os.environ.get("ROBUSTA_AI"):
        account_id, token = dal.get_ai_credentials()
        config.api_key = SecretStr(f"{account_id} {token}")

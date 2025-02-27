from holmes.config import Config
from holmes.core.supabase_dal import SupabaseDal
from pydantic import SecretStr
from holmes.common.env_vars import load_bool


def load_robusta_api_key(dal: SupabaseDal, config: Config):
    if load_bool("ROBUSTA_AI", False):
        account_id, token = dal.get_ai_credentials()
        config.api_key = SecretStr(f"{account_id} {token}")

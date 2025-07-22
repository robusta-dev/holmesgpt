from holmes.config import Config, ROBUSTA_AI_MODEL_NAME
from holmes.core.supabase_dal import SupabaseDal
from pydantic import SecretStr


def load_robusta_api_key(dal: SupabaseDal, config: Config):
    if ROBUSTA_AI_MODEL_NAME in config._model_list:
        account_id, token = dal.get_ai_credentials()
        config.api_key = SecretStr(f"{account_id} {token}")

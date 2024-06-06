# from cachetools import cached
from typing import Optional

from holmes.core.supabase_dal import AuthToken, SupabaseDal


class SessionManager:
    def __init__(self, dal: SupabaseDal, token_type: str):
        self.dal = dal
        self.token_type = token_type
        self.cached_token: Optional[AuthToken] = None
        # TODO should this part of initialization be moved to SupabaseDal?
        user_ids = dal.get_user_ids_for_account(dal.account_id)
        if not user_ids:
            raise ValueError(f"No users found for account_id={dal.account_id}")
        if len(user_ids) > 1:
            raise ValueError(f"Multiple users found for account_id={dal.account_id}")
        self.user_id = user_ids[0]

    def get_current_auth_token(self) -> AuthToken:
        if self.cached_token:
            return self.cached_token
        else:
            return self.dal.get_freshest_auth_token(self.token_type)

    def recreate_auth_token(self) -> AuthToken:
        new_token = self.dal.create_auth_token(self.token_type, self.user_id)
        self.cached_token = new_token
        return new_token

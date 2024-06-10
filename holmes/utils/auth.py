# from cachetools import cached
from typing import Optional

from holmes.core.supabase_dal import AuthToken, SupabaseDal


class SessionManager:
    def __init__(self, dal: SupabaseDal, token_type: str):
        self.dal = dal
        self.token_type = token_type
        self.cached_token: Optional[AuthToken] = None

    def get_current_auth_token(self) -> AuthToken:
        if self.cached_token:
            return self.cached_token
        else:
            return self.dal.get_freshest_auth_token(self.token_type)

    def recreate_auth_token(self) -> AuthToken:
        new_token = self.dal.create_auth_token(self.token_type)
        self.cached_token = new_token
        return new_token

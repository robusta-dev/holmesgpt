import logging
import os
from datetime import datetime
from typing import Dict, Optional

from supabase import create_client
from supabase.lib.client_options import ClientOptions
from pydantic import BaseModel

SUPABASE_TIMEOUT_SECONDS = int(os.getenv("SUPABASE_TIMEOUT_SECONDS", 3600))

ISSUES_TABLE = "Issues"
EVIDENCE_TABLE = "Evidence"


class SupabaseDal:
    def __init__(
        self,
        url: str,
        key: str,
        email: str,
        password: str,
    ):
        self.url = url
        self.key = key
        options = ClientOptions(postgrest_client_timeout=SUPABASE_TIMEOUT_SECONDS)
        self.client = create_client(url, key, options)
        self.email = email
        self.password = password
        self.sign_in()

    def sign_in(self):
        logging.info("Supabase DAL login")
        res = self.client.auth.sign_in_with_password({"email": self.email, "password": self.password})
        self.client.auth.set_session(res.session.access_token, res.session.refresh_token)
        self.client.postgrest.auth(res.session.access_token)

    def get_issue_data(self, issue_id: str) -> dict:
        # TODO this could be done in a single atomic SELECT, but there is no
        # foreign key relation between Issues and Evidence.

        try:
            issue_data = (
                self.client
                    .table(ISSUES_TABLE)
                    .select(f"*")
                    .filter("id", "eq", issue_id)
                    .execute()
            ).data[0]
        except:  # e.g. invalid id format
            logging.exception("Supabase error while retrieving issue data")
            return None
        if not issue_data:
            return None
        evidence = (
            self.client
            .table(EVIDENCE_TABLE)
            .select(f"*")
            .filter("issue_id", "eq", issue_id)
            .execute()
        )
        issue_data["evidence"] = evidence.data
        return issue_data

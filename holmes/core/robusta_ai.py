# TODO finish refactor
import logging

import requests
from fastapi import HTTPException

from holmes.core.runbooks import RunbookManager
from holmes.core.tool_calling_llm import BaseIssueInvestigator, BaseToolCallingLLM, LLMResult
from holmes.utils.auth import SessionManager


class RobustaAIToolCallingLLM(BaseToolCallingLLM):
    def __init__(self):
        raise NotImplementedError("Robusta AI tool calling LLM is not supported yet")


class RobustaIssueInvestigator(BaseIssueInvestigator):
    def __init__(self, base_url: str, session_manager: SessionManager, runbook_manager: RunbookManager):
        self.base_url = base_url
        self.session_manager = session_manager
        self.runbook_manager = runbook_manager

    def call(self, system_prompt: str, user_prompt: str) -> LLMResult:
        auth_token = self.session_manager.get_current_token()
        payload = {
            "auth": {"account_id": auth_token.account_id, "token": auth_token.token},
            "system_message": system_prompt,
            "user_message": user_prompt,
# TODO
#            "model": request.model,
        }
        resp = requests.post(self.base_url + "/api/ai", json=payload)
        if resp.status_code == 401:
            self.session_manager.invalidate_token(auth_token)
            # Attempt auth again using a fresh token
            auth_token = self.session_manager.create_token()
            payload["auth"]["account_id"] = auth_token.account_id
            payload["auth"]["token"] = auth_token.token
            resp = requests.post(self.base_url + "/api/ai", json=payload)
            if resp.status_code != 200:
                logging.error(
                    f"Failed to reauth with Robusta AI. Response status {resp.status_code}, content: {resp.text}"
                )
                raise HTTPException(status_code=400, detail="Unable to auth with Robusta AI")
        # TODO LLMResult
        return resp.json()

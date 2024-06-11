# TODO finish refactor
import logging

import jinja2
import requests
from fastapi import HTTPException

from holmes.core.tool_calling_llm import BaseToolCallingLLM, LLMResult
from holmes.plugins.prompts import load_prompt
from holmes.utils.auth import SessionManager
from holmes.core.server_models import InvestigateRequest


class RobustaAIToolCallingLLM(BaseToolCallingLLM):
    def __init__(self, base_url: str, session_manager: SessionManager):
        self.base_url = base_url
        self.session_manager = session_manager

    def call(self, system_prompt: str, user_prompt: str) -> LLMResult:
        pass

    def run_analysis(self, request: InvestigateRequest, issue):
        # TODO refactor
        """Delegate the AI analysis to Robusta AI running as a
        separate service."""
        environment = jinja2.Environment()
        sys_prompt_template = environment.from_string(load_prompt(request.system_prompt))
        # TODO what about runbooks?
        sys_prompt = sys_prompt_template.render(issue=issue, runbooks=[])
        # TODO do we want a new token each time?
        auth_token = self.session_manager.get_current_token()
        payload = {
            "auth": {
                "account_id": auth_token.account_id,
                "token": auth_token.token
            },
            "system_message": sys_prompt,
            "user_message": str(request.model_dump()),
            "model": request.model,
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
                logging.error(f"Failed to reauth with Robusta AI. Response status {resp.status_code}, content: {resp.text}")
                raise HTTPException(status_code=400, detail="Unable to auth with Robusta AI")
        # TODO reformat Robusta AI response to conform to the expected Holmes response
        # format.
        return resp.json()

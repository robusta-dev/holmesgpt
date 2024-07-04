import datetime
import json
import logging
import textwrap
import os
from typing import Dict, Generator, List, Optional
import requests 
import litellm
import jinja2
from openai import BadRequestError
from openai._types import NOT_GIVEN
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from pydantic import BaseModel
from rich.console import Console

from holmes.core.issue import Issue
from holmes.core.runbooks import RunbookManager
from holmes.core.tools import YAMLToolExecutor
from gen_ai_hub.proxy.gen_ai_hub_proxy import GenAIHubProxyClient
from ai_core_sdk.ai_core_v2_client import AICoreV2Client

# Please replace the configurations below.
# config_id: The target configuration to create the deployment. Please create the configuration first.
with open("../config.json") as f:
    config = json.load(f)

with open("./env.json") as f:
    env = json.load(f)

deployment_id = env["deployment_id"]
resource_group = config.get("resource_group", "default")
print("deployment id: ", deployment_id, " resource group: ", resource_group)
ai_core_sk = config["ai_core_service_key"]
base_url = ai_core_sk.get("serviceurls").get("AI_API_URL") + "/v2/lm"
ai_core_client = AICoreV2Client(base_url=ai_core_sk.get("serviceurls").get("AI_API_URL")+"/v2",
                        auth_url=ai_core_sk.get("url")+"/oauth/token",
                        client_id=ai_core_sk.get("clientid"),
                        client_secret=ai_core_sk.get("clientsecret"),
                        resource_group=resource_group)
token = ai_core_client.rest_client.get_token()
headers = {
        "Authorization": token,
        'ai-resource-group': resource_group,
        "Content-Type": "application/json"}

# Check deployment status before inference request
deployment_url = f"{base_url}/deployments/{deployment_id}"
response = requests.get(url=deployment_url, headers=headers)
resp = response.json()    
status = resp['status']

deployment_log_url = f"{base_url}/deployments/{deployment_id}/logs"
if status == "RUNNING":
        print(f"Deployment-{deployment_id} is running. Ready for inference request")
else:
        print(f"Deployment-{deployment_id} status: {status}. Not yet ready for inference request")
        #retrieve deployment logs
        #{{apiurl}}/v2/lm/deployments/{{deploymentid}}/logs.

        response = requests.get(deployment_log_url, headers=headers)
        print('Deployment Logs:\n', response.text)


model = "phi3:14b"
deployment = ai_core_client.deployment.get(deployment_id)
inference_base_url = f"{deployment.deployment_url}/v1"

# pull the model from ollama model repository
endpoint = f"{inference_base_url}/api/pull"
print(endpoint)

#let's pull the target model from ollama
json_data = {  "name": model}

response = requests.post(endpoint, headers=headers, json=json_data)
print('Result:', response.text)

# Check the model list 
endpoint = f"{inference_base_url}/api/tags"
print(endpoint)

response = requests.get(endpoint, headers=headers)
print('Result:', response.text)


from gen_ai_hub.proxy.gen_ai_hub_proxy import GenAIHubProxyClient

GenAIHubProxyClient.add_foundation_model_scenario(
    scenario_id="byom-ollama-server",
    config_names="ollama*",
    prediction_url_suffix="/v1/chat/completions",
)

proxy_client = GenAIHubProxyClient(ai_core_client = ai_core_client)


from gen_ai_hub.proxy.native.openai import OpenAI


openai = OpenAI(proxy_client=proxy_client)
messages = [{"role": "user", "content": "Tell me a joke"}]
# kwargs = dict(deployment_id='xxxxxxx', model=model,messages = messages)
result = openai.chat.completions.create(
    # **kwargs
    deployment_id=deployment_id,
    model=model,
    messages=messages
)

print("Option 1: Proxy with OpenAI-like interface\n", result.choices[0].message.content)




class ToolCallResult(BaseModel):
    tool_name: str
    description: str
    result: str

class LLMResult(BaseModel):
    tool_calls: Optional[List[ToolCallResult]] = None
    result: Optional[str] = None

    # TODO: clean up these two
    prompt: Optional[str] = None
    messages: Optional[List[dict]] = None

    def get_tool_usage_summary(self):
        return "AI used info from issue and " + ",".join(
            [f"`{tool_call.description}`" for tool_call in self.tool_calls]
        )

class ToolCallingLLM:

    def __init__(
        self,
        model: Optional[str],
        api_key: Optional[str],
        tool_executor: YAMLToolExecutor,
        max_steps: int,
    ):
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.model = model
        self.api_key = api_key

        self.check_llm(self.model, self.api_key)

    def check_llm(self, model, api_key):
        return True
    
    def call(self, system_prompt, user_prompt) -> LLMResult:
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
        tool_calls = []
        tools = self.tool_executor.get_all_tools_openai_format()
        
        for i in range(self.max_steps):
            logging.debug(f"running iteration {i}")
            # on the last step we don't allow tools - we want to force a reply, not a request to run another tool
            tools = NOT_GIVEN if i == self.max_steps - 1 else tools
            tool_choice = NOT_GIVEN if tools == NOT_GIVEN else "auto"
            logging.debug(f"sending messages {messages}")
            try:
                full_response = openai.chat.completions.create(
                    deployment_id=deployment_id,
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=0.00000001
                )
                logging.debug(f"got response {full_response}")
            # catch a known error that occurs with Azure and replace the error message with something more obvious to the user
            except BadRequestError as e:
                if "Unrecognized request arguments supplied: tool_choice, tools" in str(e):
                    raise Exception(
                        "The Azure model you chose is not supported. Model version 1106 and higher required."
                    )
                else:
                    raise
            response = full_response.choices[0]
            response_message = response.message
            messages.append(
                response_message.model_dump(
                    exclude_defaults=True, exclude_unset=True, exclude_none=True
                )
            )

            tools_to_call = getattr(response_message, "tool_calls", None)
            if not tools_to_call:
                return LLMResult(
                    result=response_message.content,
                    tool_calls=tool_calls,
                    prompt=json.dumps(messages, indent=2),
                )

            # when asked to run tools, we expect no response other than the request to run tools
            if response_message.content:
                logging.warning(f"got unexpected response when tools were given: {response_message.content}")

            for t in tools_to_call:
                tool_name = t.function.name
                tool_params = json.loads(t.function.arguments)
                tool = self.tool_executor.get_tool_by_name(tool_name)
                tool_response = tool.invoke(tool_params)
                MAX_CHARS = 100_000 # an arbitrary limit - we will do something smarter in the future
                if len(tool_response) > MAX_CHARS:
                    logging.warning(f"tool {tool_name} returned a very long response ({len(tool_response)} chars) - truncating to last 10000 chars")
                    tool_response = tool_response[-MAX_CHARS:]
                messages.append(
                    {
                        "tool_call_id": t.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_response,
                    }
                )
                tool_calls.append(
                    ToolCallResult(
                        tool_name=tool_name,
                        description=tool.get_parameterized_one_liner(tool_params),
                        result=tool_response,
                    )
                )

# TODO: consider getting rid of this entirely and moving templating into the cmds in holmes.py 
class IssueInvestigator(ToolCallingLLM):
    """
    Thin wrapper around ToolCallingLLM which:
    1) Provides a default prompt for RCA
    2) Accepts Issue objects
    3) Looks up and attaches runbooks
    """

    def __init__(
        self,
        model: Optional[str],
        api_key: Optional[str],
        tool_executor: YAMLToolExecutor,
        runbook_manager: RunbookManager,
        max_steps: int,
    ):
        super().__init__(model, api_key, tool_executor, max_steps)
        self.runbook_manager = runbook_manager

    def investigate(
        self, issue: Issue, prompt: str, console: Console
    ) -> LLMResult:
        environment = jinja2.Environment()
        system_prompt_template = environment.from_string(prompt)
        runbooks = self.runbook_manager.get_instructions_for_issue(issue)
        if runbooks:
            console.print(
                f"[bold]Analyzing with {len(runbooks)} runbooks: {runbooks}[/bold]"
            )
        else:
            console.print(
                f"[bold]No runbooks found for this issue. Using default behaviour. (Add runbooks to guide the investigation.)[/bold]"
            )
        system_prompt = system_prompt_template.render(issue=issue, runbooks=runbooks)
        user_prompt = f"{issue.raw}"
        logging.debug(
            "Rendered system prompt:\n%s", textwrap.indent(system_prompt, "    ")
        )
        logging.debug(
            "Rendered user prompt:\n%s", textwrap.indent(user_prompt, "    ")
        )
        return self.call(system_prompt, user_prompt)

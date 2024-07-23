import datetime
import json
import logging
import re
import textwrap
from typing import Dict, Generator, List, Optional, Union, Any

import jinja2
from langchain.memory import ChatMessageHistory

from langchain.agents.output_parsers import ReActJsonSingleInputOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, \
    MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableConfig, \
    RunnableSerializable, RunnableWithMessageHistory
from langchain_core.runnables.utils import Input, Output
from langchain_core.tools import render_text_description_and_args
from openai import BadRequestError, OpenAI
from openai._types import NOT_GIVEN
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from pydantic import BaseModel
from rich.console import Console

from holmes.core.issue import Issue
from holmes.core.runbooks import RunbookManager
from holmes.core.tools_langchain import LCYAMLTool, LangchainYamlTool
from langchain_core.language_models import BaseLLM, BaseLanguageModel

from langchain.agents import AgentExecutor, create_react_agent, \
    AgentOutputParser, create_structured_chat_agent, create_json_chat_agent

import langchain

langchain.debug = True

class ToolCallResult(BaseModel):
    tool_name: str
    description: str
    result: str

class LLMResult(BaseModel):
    tool_calls: Optional[List[ToolCallResult]] = None
    # result: Optional[str] = None
    result: Any = None
    prompt: Optional[str] = None
    messages: Optional[List[dict]] = None

    def get_tool_usage_summary(self):
        return "AI used info from issue and " + ",".join(
            [f"`{tool_call.description}`" for tool_call in self.tool_calls]
        )

class LCToolCallingLLM:

    def __init__(
        self,
        client: BaseLLM,
        model: str,
        tools: List[LangchainYamlTool],
        max_steps: int,
    ):
        self.client = client
        self.tools = tools
        self.max_steps = max_steps
        self.model = model

    def call(self, system_prompt, user_prompt, prompt_tmpl) -> LLMResult:
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
        tools = self.tools
        template = '''Answer the following questions as best you can. You have access to the following tools:

                    {tools}

                    Use the following format:

                    Question: the input question you must answer
                    Thought: you should always think about what to do
                    Action: the action to take, should be one of [{tool_names}]
                    Action Input: the input to the action
                    Observation: the result of the action
                    ... (this Thought/Action/Action Input/Observation can repeat N times)
                    Thought: I now know the final answer
                    Final Answer: the final answer to the original input question

                    Begin!

                    Question: {input}
                    Thought:{agent_scratchpad}'''

        # prompt = PromptTemplate.from_template(system_prompt)
        #
        # agent = create_react_agent(
        #     self.client, tools, prompt,
        #     tools_renderer=render_text_description_and_args,
        #     output_parser=ReActSingleInputOutputJsonOrDictParser())
        agent = self.build_agent(system_prompt, prompt_tmpl)
        translator = ChineseAnswerTranslator.create_from_llm(self.client)
        # agent = agent | translator
        # agent = create_structured_chat_agent(self.client, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True,
                                       handle_parsing_errors=True)

        demo_ephemeral_chat_history_for_chain = ChatMessageHistory()
        chain_with_message_history = RunnableWithMessageHistory(
            agent_executor,
            lambda session_id: demo_ephemeral_chat_history_for_chain,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        result = chain_with_message_history.invoke(
            {"input": user_prompt},
            {"configurable": {"session_id": "session_id_123"}}
        )
        trans_result = translator.invoke(result['output'])
        logging.info(f"Translated result: {trans_result}")
        return LLMResult(
            result=result['output'],
            tool_calls=tool_calls,
            prompt=json.dumps(messages, indent=2),
        )

    def build_agent(self, system_prompt, prompt_tmpl: str) -> Runnable:
        filename = prompt_tmpl.split(".")[0]
        if filename.endswith("_react"):
            prompt = PromptTemplate.from_template(system_prompt)
            agent = create_react_agent(
                self.client, self.tools, prompt,
                tools_renderer=render_text_description_and_args,
                output_parser=ReActSingleInputOutputJsonOrDictParser())
            return agent

        if filename.endswith("_react-json"):
            return self.get_recat_json_agent(system_prompt)

    def get_recat_json_agent(self, system_prompt) -> Runnable:
        human = '''TOOLS
        ------
        Assistant can ask the user to use tools to look up information that may be helpful in \
        answering the users original question. The tools the human can use are:

        {tools}

        RESPONSE FORMAT INSTRUCTIONS
        ----------------------------

        When responding to me, please output a response in one of two formats:

        **Option 1:**
        Use this if you want the human to use a tool.
        Markdown code snippet formatted in the following schema:

        ```json
        {{
            "action": string, \\ The action to take. Must be one of {tool_names}
            "action_input": string \\ The input to the action
        }}
        ```

        **Option #2:**
        Use this if you want to respond directly to the human. Markdown code snippet formatted \
        in the following schema:

        ```json
        {{
            "action": "Final Answer",
            "action_input": string \\ You should put what you want to return to use here
        }}
        ```

        USER'S INPUT
        --------------------
        Here is the user's input (remember to respond with a markdown code snippet of a json \
        blob with a single action, and NOTHING else):

        {input}'''
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", human),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_json_chat_agent(
            self.client, self.tools, prompt,
            tools_renderer=render_text_description_and_args,
        )
        # demo_ephemeral_chat_history_for_chain = ChatMessageHistory()
        # chain_with_message_history = RunnableWithMessageHistory(
        #     agent,
        #     lambda session_id: demo_ephemeral_chat_history_for_chain,
        #     input_messages_key="input",
        #     history_messages_key="chat_history",
        # )
        # return chain_with_message_history
        return agent

# TODO: consider getting rid of this entirely and moving templating into the cmds in holmes.py
class LCIssueInvestigator(LCToolCallingLLM):
    """
    Thin wrapper around ToolCallingLLM which:
    1) Provides a default prompt for RCA
    2) Accepts Issue objects
    3) Looks up and attaches runbooks
    """

    def __init__(
        self,
        client: BaseLLM,
        model: str,
        tools: List[LangchainYamlTool],
        runbook_manager: RunbookManager,
        max_steps: int,
    ):
        super().__init__(client, model, tools, max_steps)
        self.runbook_manager = runbook_manager

    def investigate(
        self, issue: Issue, prompt: str, console: Console, prompt_tmpl: str
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
        # system_prompt = prompt
        user_prompt = f"{issue.user_input}"
        logging.debug(
            "Rendered system prompt:\n%s", textwrap.indent(system_prompt, "    ")
        )
        logging.debug(
            "Rendered user prompt:\n%s", textwrap.indent(user_prompt, "    ")
        )
        return self.call(system_prompt, user_prompt, prompt_tmpl)


class ReActSingleInputOutputJsonOrDictParser(AgentOutputParser):
    FINAL_ANSWER_ACTION = "Final Answer:"
    MISSING_ACTION_AFTER_THOUGHT_ERROR_MESSAGE = (
        "Invalid Format: Missing 'Action:' after 'Thought:"
    )
    MISSING_ACTION_INPUT_AFTER_ACTION_ERROR_MESSAGE = (
        "Invalid Format: Missing 'Action Input:' after 'Action:'"
    )
    MULTI_ACTION_ERROR_MESSAGE = (
        "Invalid Format: Only respond with one 'Action' and one 'Action Input' at a time:"
    )
    FINAL_ANSWER_AND_PARSABLE_ACTION_ERROR_MESSAGE = (
        "Parsing LLM output produced both a final answer and a parse-able action:"
    )

    """Parses ReAct-style LLM calls that have a single tool input.

    Expects output to be in one of two formats.

    If the output signals that an action should be taken,
    should be in the below format. This will result in an AgentAction
    being returned.

    ```
    Thought: agent thought here
    Action: search
    Action Input: what is the temperature in SF?
    ```

    If the output signals that a final answer should be given,
    should be in the below format. This will result in an AgentFinish
    being returned.

    ```
    Thought: agent thought here
    Final Answer: The temperature is 100 degrees
    ```

    """

    def get_format_instructions(self) -> str:
        return self.FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        includes_answer = self.FINAL_ANSWER_ACTION in text
        regex = (
            # r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
            r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(\{.*?\})"
        )
        # matches = re.findall(regex, text, re.DOTALL)
        # match_count = len(matches)
        # if match_count > 1:
        #     raise OutputParserException(
        #         f"{self.MULTI_ACTION_ERROR_MESSAGE}: {text}"
        #     )
        action_match = re.search(regex, text, re.DOTALL)
        if action_match:
            # if includes_answer:
            #     raise OutputParserException(
            #         f"{self.FINAL_ANSWER_AND_PARSABLE_ACTION_ERROR_MESSAGE}: {text}"
            #     )
            action = action_match.group(1).strip()
            action_input = action_match.group(2)

            action_match_in_input = re.search(regex, action_input, re.DOTALL)
            if action_match_in_input:
                raise OutputParserException(
                    f"{self.MULTI_ACTION_ERROR_MESSAGE}: {text}"
                )
            tool_input = action_input.strip(" ")
            tool_input = tool_input.strip('"')

            markdown_json = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
            match = markdown_json.search(tool_input)
            if match:
                logging.debug(f"LLM input markdown json found: {tool_input}")
                tool_input = match.group(1)

            try:
                tool_input_dict = json.loads(tool_input)
                return AgentAction(action, tool_input_dict, text)
            except Exception:
                logging.debug(f"Could not load LLM input string: {tool_input},"
                              f"fallback to eval method")
            try:
                tool_input_dict = eval(tool_input)
            except Exception:
                raise OutputParserException(
                    f"Could not eval LLM input string: {text}")

            return AgentAction(action, tool_input_dict, text)

        elif includes_answer:
            return AgentFinish(
                {"output": text.split(self.FINAL_ANSWER_ACTION)[-1].strip()}, text
            )

        if not re.search(r"Action\s*\d*\s*:[\s]*(.*?)", text, re.DOTALL):
            raise OutputParserException(
                f"Could not parse LLM output: `{text}`",
                observation=self.MISSING_ACTION_AFTER_THOUGHT_ERROR_MESSAGE,
                llm_output=text,
                send_to_llm=True,
            )
        elif not re.search(
            r"[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)", text, re.DOTALL
        ):
            raise OutputParserException(
                f"Could not parse LLM output: `{text}`",
                observation=self.MISSING_ACTION_INPUT_AFTER_ACTION_ERROR_MESSAGE,
                llm_output=text,
                send_to_llm=True,
            )
        else:
            raise OutputParserException(f"Could not parse LLM output: `{text}`")

    @property
    def _type(self) -> str:
        return "react-single-input-json"


class ChineseAnswerTranslator(RunnableSerializable[Dict, Dict]):
    llm: BaseLanguageModel = None
    template: str = """Translate the following english content into Chinese.
    {content}
    
    """

    def __init__(self, llm, *args, **kwargs):
        super().__init__(**kwargs)
        self.llm = llm

    def _translate(self, content) -> Dict:
        result = {"english_result": content}
        prompt = PromptTemplate.from_template(self.template)
        message = prompt.invoke({"content": content}).to_messages()
        chinese = self.llm.invoke(message)
        result["chinese_result"] = chinese
        return result

    @classmethod
    def create_from_llm(cls, llm: BaseLanguageModel):
        return cls(llm)

    def invoke(self, input: Dict,
               config: Optional[RunnableConfig] = None) -> Dict:
        return self._call_with_config(
            self._translate,
            input,
            config,
            run_type="prompt",
        )



def chinese_answer_translator():
    pass


if __name__ == "__main__":
    regex = r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(\{.*?\})"
    res_str = "Action: kubectl_logs\nAction Input: {\"name\": \"w1new-5859c45467-4mssj\", \"namespace\": \"app\"}\nObservation: [LOGS CONTENT]\nThought:  I now know the final answer\nFinal Answer: The pod 'w1new-5859c45467-4mssj' in namespace 'app' has a memory limit of 250Mi and requests the same. The exit code 143 indicates an issue. Reviewing the logs might provide more insights into the specific problem causing the OOMKilled state. "

    json_str = "{'name': 'webapp-pod-name', 'namespace': 'default'}\n"
    d = eval(json_str)
    # d = json.loads(json_str)
    print(type(d))
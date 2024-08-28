from concurrent.futures import ThreadPoolExecutor, as_completed
from holmes.core.models import ConversationRequest, ToolCallConversationResult
from holmes.utils.cache_utils import SummarizationsCache
from holmes.core.tool_calling_llm import ToolCallingLLM
from typing import List, Dict
from jinja2.environment import Template


def conversation_message_exceeds_context_window(ai: ToolCallingLLM, 
                                            template_context: dict,
                                            system_prompt_template: Template,
                                            user_prompt) -> bool:
    system_prompt = system_prompt_template.render(
            **template_context
            )
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
    context_window_size = ai.get_context_window_size()
    message_size = ai.count_tokens_for_message(messages)

    return message_size > context_window_size


def summarize_tool_calls_for_conversation_history(conversation_request: ConversationRequest, 
                                          tools_cache: SummarizationsCache,
                                          ai: ToolCallingLLM) -> List[Dict]:
    summarized_conversation_history = [{"ask": history_entry.ask,
                                        "answer": {
                                            "analysis": history_entry.answer.analysis,
                                            "tool_calls": []
                                        }} for history_entry in conversation_request.context.conversation_history]
    
    futures_to_idx = {}
    with ThreadPoolExecutor(max_workers=16) as executor:
        for idx, history_entry in enumerate(conversation_request.context.conversation_history):
            for tool_call in history_entry.answer.tools:
                future = executor.submit(tools_cache.get_tool_call_summarization_from_cache, 
                                         tool_call, 
                                         ai)
                futures_to_idx[future] = idx 
    
        for future in as_completed(futures_to_idx):
            idx = futures_to_idx[future]
            tool_call = future.result()
            summarized_conversation_history[idx]["answer"]["tool_calls"].append(tool_call)
    
    return summarized_conversation_history


def summarize_tool_calls_for_investigation_result(conversation_request: ConversationRequest, 
                                          tools_cache: SummarizationsCache,
                                          ai: ToolCallingLLM) -> List[ToolCallConversationResult]:
    summarized_investigation_tool_calls = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for tool_call in conversation_request.context.investigation_result.tools:
            futures.append(executor.submit(tools_cache.get_tool_call_summarization_from_cache, 
                                           tool_call, 
                                           ai))

        for future in as_completed(futures):
            tool_call_result = future.result()
            summarized_investigation_tool_calls.append(tool_call_result)
    
    return summarized_investigation_tool_calls
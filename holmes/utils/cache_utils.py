from cachetools import TTLCache
import hashlib
from holmes.core.models import ToolCallConversationResult
from holmes.core.tool_calling_llm import ToolCallingLLM
import logging


SESSION_TOKEN_CACHE_SIZE = 100
SESSION_TOKEN_CACHE_TIMEOUT = 3600 


class SummarizationsCache:
    def __init__(self) -> None:
        self.tool_call_cache = TTLCache(
            maxsize=SESSION_TOKEN_CACHE_SIZE, ttl=SESSION_TOKEN_CACHE_TIMEOUT
        )
    
    def get_tool_call_summarization_from_cache(self, 
                                               tool_call: ToolCallConversationResult, 
                                               ai: ToolCallingLLM
                                               ):
        cache_key = hashlib.sha256(tool_call.result.encode()).hexdigest()
        try:
            if cache_key in self.tool_call_cache:
                return self.tool_call_cache[cache_key]
            summarization = ai._post_processing_call(user_prompt="builtin://summarize_tool_call.jinja2",
                template_context={"tool_call": tool_call}
            )
            tool_call_result = ToolCallConversationResult(
                tool_name=tool_call.tool_name,
                description=tool_call.description,
                result=summarization
            ).model_dump_json()
            self.tool_call_cache[cache_key] = tool_call_result
            return tool_call_result
        
        except Exception as e:
            logging.exception(f"Unable to summarize tool call: {tool_call}", exc_info=True)
            return tool_call


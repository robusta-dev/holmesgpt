# Agent Engines

HolmesGPT's agent loop (call the model, run the tools it asks for, repeat until it answers)
can run on one of several engines. All engines share the same prompts, toolsets, LLM routing
(LiteLLM, the Robusta AI proxy, Azure and Bedrock credentials), streaming events and
conversation history, so switching the engine changes nothing for clients.

| Engine | Implementation | Install |
| --- | --- | --- |
| `legacy` | HolmesGPT's own loop (default) | always available |
| `openai_agents` | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | `poetry install --with engine-openai-agents` |
| `pydantic_ai` | [Pydantic AI](https://github.com/pydantic/pydantic-ai) | `poetry install --with engine-pydantic-ai` |
| `langgraph` | [LangChain `create_agent`](https://docs.langchain.com/oss/python/langchain/agents) on LangGraph | `poetry install --with engine-langgraph` |

The official container image includes all engines.

## Selecting an engine

Resolution order: per-request value, then the configured default, then `legacy`.

```yaml
# ~/.holmes/config.yaml
agent_engine: pydantic_ai
```

```bash
AGENT_ENGINE=langgraph holmes ask "why is my pod crashing?"
```

```bash
# Per request on the HTTP API; omit "engine" to use the server default.
curl -X POST localhost:5050/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"ask": "why is my pod crashing?", "engine": "openai_agents", "stream": true}'
```

`GET /api/info` reports the configured default (`agent_engine`) and the installed engines.
Every answer carries the engine that produced it in `metadata.engine`.

## What every engine supports

Tool approvals (including the signed "don't ask again" bash prefixes), OAuth connect pauses,
frontend tools in `pause` and `noop` mode, resuming from `tool_decisions` and
`frontend_tool_results`, and conversation-history compaction behave the same on every engine;
the parity test suite in `tests/core/engines/` asserts identical events and history against the
legacy loop.

## Comparing engines with the eval suite

The eval suite reads `AGENT_ENGINE` when it builds the agent, so `ENV_CONFIGS` runs every
test once per engine and reports them side by side:

```bash
ENV_CONFIGS='legacy:AGENT_ENGINE=legacy|openai:AGENT_ENGINE=openai_agents|pydantic:AGENT_ENGINE=pydantic_ai|langgraph:AGENT_ENGINE=langgraph' \
MODEL=gpt-4.1-mini CLASSIFIER_MODEL=gpt-4.1 \
poetry run pytest tests/llm/test_ask_holmes.py -m "llm and regression" -n 4 --no-cov
```

The terminal "ENV CONFIG COMPARISON RESULTS" table shows pass rate, average and P90 time,
average tokens and average cost per engine; `evals_report.md` lists every run with its
engine and env config. In CI, add `engines: legacy,pydantic_ai` to an `/eval` comment.

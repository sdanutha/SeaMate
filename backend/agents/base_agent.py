from langchain_ollama import ChatOllama
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from typing import AsyncGenerator
import os

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_DEFAULT_MODEL   = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")


class BaseAgent:
    def __init__(self, agent_id: str, name: str, system_prompt: str, model: str | None = None):
        self.agent_id = agent_id
        self.name = name
        self.system_prompt = system_prompt
        self.model_name = model or _DEFAULT_MODEL

        llm = ChatOllama(model=self.model_name, base_url=_OLLAMA_BASE_URL)
        self._checkpointer = MemorySaver()
        self._graph = create_deep_agent(
            model=llm,
            system_prompt=system_prompt,
            checkpointer=self._checkpointer,
        )

    async def stream_response(self, user_message: str, thread_id: str = "default") -> AsyncGenerator[str, None]:
        config = {"configurable": {"thread_id": thread_id}}

        async for msg, _metadata in self._graph.astream(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
            stream_mode="messages",
        ):
            # yield only AI text tokens, skip tool calls / tool results
            if (
                hasattr(msg, "type")
                and msg.type == "AIMessageChunk"
                and msg.content
                and not getattr(msg, "tool_call_chunks", None)
            ):
                yield msg.content

    def clear_history(self, thread_id: str = "default"):
        # recreate a fresh checkpointer (MemorySaver has no per-thread delete)
        self._checkpointer = MemorySaver()
        llm = ChatOllama(model=self.model_name, base_url=_OLLAMA_BASE_URL)
        self._graph = create_deep_agent(
            model=llm,
            system_prompt=self.system_prompt,
            checkpointer=self._checkpointer,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.agent_id,
            "name": self.name,
            "model": self.model_name,
        }

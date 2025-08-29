from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Union, Literal, Callable
from pydantic import Field, PrivateAttr

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from .protocols import LLMClient
from .hf_client import HFClient
from .load_hf_model import ModelLoader

class ChatLLM(BaseChatModel):
    model: str = Field(default="mistralai/Mixtral-8x7B-Instruct-v0.1")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None
    stop: Optional[List[str]] = None
    max_retries: int = 2

    _client: LLMClient = PrivateAttr()
    _loader: ModelLoader = PrivateAttr() # can be used for debugging if needed

    def __init__(self, model: str ="mistralai/Mixtral-8x7B-Instruct-v0.1", fourbit=True, atebit=False, **data: Any):
        super().__init__(model=model, **data)
        # original loader
        loader = ModelLoader(base_model_id=self.model, fourbit=fourbit, atebit=atebit)
        # converted to a client - sphere of influence ends at this level. after this it is all langchain chat model
        self._client: LLMClient = HFClient(loader)

        # If you passed temperature/max_tokens to this class, bind them:
        bind_kwargs: Dict[str, Any] = {}
        if self.temperature is not None:
            bind_kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            bind_kwargs["max_new_tokens"] = self.max_tokens
        if bind_kwargs:
            # bind is updating default params of the HF model
            self._client = self._client.bind(**bind_kwargs)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Convert LangChain BaseMessage -> list[(role, content)]
        mc: List[tuple[str, str]] = []
        for m in messages:
            role = getattr(m, "type", "user")  # BaseMessage has .type ("human","ai","system")
            # normalize roles
            role = "user" if role == "human" else ("assistant" if role == "ai" else role)
            mc.append((role, m.content))

        # Allow per-call overrides via kwargs (e.g., temperature=..., top_p=...)
        client = self._client.bind(**kwargs) if kwargs else self._client
        out = client.invoke(mc)  # {'content': '...'}
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=out["content"]))])

    def bind_tools(
        self,
        tools: Sequence[Union[dict[str, Any], type, Callable, BaseTool]],
        *,
        tool_choice: Optional[Union[dict, str, Literal["auto", "none", "required"], bool]] = None,
        **kwargs: Any,
    ):
        formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
        if tool_choice is not None and tool_choice:
            if len(formatted_tools) != 1:
                raise ValueError("When specifying `tool_choice`, you must provide exactly one tool.")
            if isinstance(tool_choice, str):
                if tool_choice not in ("auto", "none", "required"):
                    tool_choice = {"type": "function", "function": {"name": tool_choice}}
            elif isinstance(tool_choice, bool):
                tool_choice = formatted_tools[0]
            elif isinstance(tool_choice, dict):
                if formatted_tools[0]["function"]["name"] != tool_choice["function"]["name"]:
                    raise ValueError("Tool choice does not match the provided tool.")
            else:
                raise ValueError("Unrecognized tool_choice type.")
            kwargs["tool_choice"] = tool_choice
        return super().bind(tools=formatted_tools, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "agentic model using mixtral 8x7B as base"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_name": self.model}

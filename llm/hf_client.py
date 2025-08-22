from __future__ import annotations
from typing import Any, Dict, List, Tuple

from .protocols import LLMClient
from .load_hf_model import ModelLoader

def _messages_to_prompt(messages: List[Tuple[str, str]]) -> str:
    for role, content in reversed(messages):
        if role.lower() == "user":
            return content
    return "\n".join(content for _, content in messages)

class HFClient(LLMClient):
    
    ALLOWED_GEN_KWARGS = {
    "max_new_tokens", "min_new_tokens",
    "temperature", "top_p", "top_k",
    "repetition_penalty", "do_sample",
    "num_beams", "length_penalty",
    # add any other HF generate params you intend to support
    }
    
    """Make a HF-ModelLoader look like an LLMClient."""
    def __init__(self, loader: ModelLoader, **gen_kwargs: Any):
        self._loader = loader # share one loaded model
        self._gen_kwargs: Dict[str, Any] = dict(**gen_kwargs)

    def bind(self, **gen_kwargs: Any) -> "HFClient":
        merged = {**self._gen_kwargs, **gen_kwargs}
        return HFClient(self._loader, **merged)

    def invoke(self, messages: List[Tuple[str, str]]) -> Dict[str, Any]:
        prompt = _messages_to_prompt(messages)
        text = self._loader.invoke(prompt, **self._gen_kwargs)
        # You can also add token usage here if you compute it.
        return {"content": text}
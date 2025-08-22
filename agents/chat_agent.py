from .baseagent import BaseAgent
from ..state import MobiLLMState
from ..utils import *

class ChatAgent(BaseAgent):
    def run(self, state: MobiLLMState) -> MobiLLMState:
        query = state["query"]
        if not query or query.strip() == "":
            return state
        res = self.invoke(query)
        content = res["messages"][-1].content
        state["chat_response"] = content
        state.setdefault("tools_called", []).extend(self.collect_tool_calls(res))
        return state
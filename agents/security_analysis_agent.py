from .baseagent import BaseAgent
from ..state import MobiLLMState
from ..utils import *

class SecurityAnalysisAgent(BaseAgent):
    def run(self, state: MobiLLMState) -> MobiLLMState:
        query = state["query"]
        if not query or query.strip() == "":
            return state
        res = self.invoke(query)
        content = res["messages"][-1].content
        state["threat_summary"] = content
        state.setdefault("tools_called", []).extend(self.collect_tool_calls(res))
        return state
from .baseagent import BaseAgent
from ..state import MobiLLMState
from ..utils import *

class ResponseAgent(BaseAgent):
    def run(self, state: MobiLLMState) -> MobiLLMState:
        threat_summary = state.get("threat_summary", "")
        mitre_technique = state.get("mitre_technique", "")

        if not threat_summary or not mitre_technique:
            return state

        prompt = f"Threat summary:\n{threat_summary}\nRelevant MiTRE FiGHT Techniques:\n{mitre_technique}"

        res = self.invoke(prompt)
        content = res["messages"][-1].content or ""
        parsed = extract_json_from_string(content.replace("\n",""))

        if parsed:
            state["actionable"] = parsed.get("actionable", "no")
            state["action_plan"] = parsed.get("action_plan", "")
            state["action_strategy"] = parsed.get("action_strategy", "none")
            state["countermeasures"] = parsed
        else:
            state["actionable"] = "no"
            state["action_plan"] = ""
            state["action_strategy"] = "none"

        state.setdefault("tools_called", []).extend(self.collect_tool_calls(res))
        return state

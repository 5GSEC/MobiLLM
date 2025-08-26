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
        raw_response = res["messages"][-1].content or ""

        try:
            if raw_response.strip() == "" and call_result["messages"][-1].response_metadata.get("finish_reason") == "MALFORMED_FUNCTION_CALL":
                print("MALFORMED_FUNCTION_CALL detected, retrying...")
                call_result = self.response_planning_agent.invoke({"messages": [("user", prompt)]})
                raw_response = call_result["messages"][-1].content
        except:
            print("raw_response", raw_response)
            

        parsed = extract_json_from_string(raw_response.replace("\n",""))

        if parsed:
            state["actionable"] = parsed.get("actionable", "no")
            state["action_plan"] = parsed.get("action_plan", "")
            state["action_strategy"] = parsed.get("action_strategy", "none")
        else:
            state["actionable"] = "no"
            state["action_plan"] = ""
            state["action_strategy"] = "none"
        
        state["countermeasures"] = parsed
        state = self.collect_tool_calls(res, state)
        return state

from .baseagent import BaseAgent
from ..state import MobiLLMState
from ..utils import *

class ConfigTuningAgent(BaseAgent):
    def run(self, state: MobiLLMState) -> MobiLLMState:
        actionable = state["actionable"]
        action_plan = state["action_plan"]
        action_strategy = state["action_strategy"]

        if actionable.lower() != "yes" or action_strategy != "config tuning" or not action_plan:
            print("No actionable plan provided.")
            return state
        
        prompt = f"Action plan:\n{action_plan}"

        call_result = self.invoke(prompt)
        res = call_result["messages"][-1].content

        response = extract_json_from_string(res.strip().replace("\n", ""))

        if response:
            state["actionable"] = response["actionable"]
            state["outcome"] = response["outcome"]
            state["updated_config"] = response["updated_config"]

        state.setdefault("tools_called", []).extend(self.collect_tool_calls(res))
        return state

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

        res = self.invoke(prompt)
        content = res["messages"][-1].content

        # ensure content is a valid string
        if not content or content.strip() == "":
            return state

        response = extract_json_from_string(content.strip().replace("\n", ""))

        if response:
            state["actionable"] = response["actionable"]
            state["outcome"] = response["outcome"]
            state["updated_config"] = response["updated_config"]

        state = self.collect_tool_calls(res, state)
        return state

from ..state import MobiLLMState

def supervisor(state: MobiLLMState) -> MobiLLMState:
    q = state.get("query", "")
    if "[chat]" in q:
        state["task"] = "chat"
    elif "[security analysis]" in q:
        state["task"] = "security_analysis"
    else:
        raise ValueError("Router received empty or untagged input.")
    return state

def route_after_response(state: MobiLLMState) -> str:
    if state.get("actionable") == "yes" and state.get("action_strategy") == "config tuning":
        return "config_tuning"
    return "end"

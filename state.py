from typing import TypedDict, List, Literal, Optional

class MobiLLMState(TypedDict, total=False):
    thread_id: str
    query: str
    event: str
    network_data: str
    threat_summary: str
    mitre_technique: str
    countermeasures: str
    actionable: Literal["yes", "no"]
    action_strategy: Literal["config tuning", "reboot", "none"]
    action_plan: str
    chat_response: str
    task: Literal["chat", "security_analysis"]
    updated_config: str
    outcome: str
    tools_called: List[str]

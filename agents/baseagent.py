from langgraph.prebuilt import create_react_agent
from ..state import MobiLLMState

class BaseAgent:
    def __init__(self, llm, tools, prompt, name: str):
        self._agent = create_react_agent(model=llm, tools=tools, prompt=prompt, name=name)

    def invoke(self, user_text: str) -> dict:
        return self._agent.invoke({"messages": [("user", user_text)]})

    @staticmethod
    def collect_tool_calls(call_result, state: MobiLLMState):
        try:
            from langchain_core.messages import AIMessage, ToolMessage
        except Exception:
            AIMessage = ToolMessage = None

        tools = state.get("tools_called", []) or []

        if not call_result or "messages" not in call_result:
            state["tools_called"] = tools
            return state

        for m in call_result["messages"]:
            # 1) AI messages with pending tool calls
            tc = getattr(m, "tool_calls", None)
            if tc:
                for t in tc:
                    # t may be dict-like or object-like depending on LC version
                    name = (t.get("name") if isinstance(t, dict) else getattr(t, "name", None)) or "UNKNOWN_TOOL"
                    tools.append(name)

            # 2) Executed tool messages (observations)
            if ToolMessage and isinstance(m, ToolMessage):
                name = getattr(m, "name", None) or getattr(m, "tool", None) or "UNKNOWN_TOOL"
                tools.append(name)

            # 3) Some backends stuff the tool name in 'additional_kwargs'
            ak = getattr(m, "additional_kwargs", None)
            if isinstance(ak, dict) and "tool_name" in ak:
                tools.append(ak["tool_name"])

            # 4) Fallback: role == 'tool'
            role = getattr(m, "role", None)
            if role == "tool":
                name = getattr(m, "name", None) or getattr(m, "tool", None) or "UNKNOWN_TOOL"
                tools.append(name)

        state["tools_called"] = tools
        return state

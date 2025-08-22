from langgraph.prebuilt import create_react_agent

class BaseAgent:
    def __init__(self, llm, tools, prompt, name: str):
        self._agent = create_react_agent(model=llm, tools=tools, prompt=prompt, name=name)

    def invoke(self, user_text: str) -> dict:
        return self._agent.invoke({"messages": [("user", user_text)]})

    @staticmethod
    def collect_tool_calls(call_result: dict) -> list[str]:
        tools = []
        for m in call_result.get("messages", []):
            tc = getattr(m, "tool_calls", None)
            if tc:
                for t in tc:
                    name = (t.get("name") if isinstance(t, dict) else getattr(t, "name", None)) or "UNKNOWN_TOOL"
                    tools.append(name)
        return tools

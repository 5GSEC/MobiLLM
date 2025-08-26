from uuid import uuid4
from langgraph.checkpoint.memory import InMemorySaver
from .settings import Settings
from .llm.chatmodel_factory import instantiate_llm
from .tools.tools_registry import *
from MobiLLM import prompts
from .agents.chat_agent import ChatAgent
from .agents.security_classification_agent import SecurityClassificationAgent
from .agents.security_analysis_agent import SecurityAnalysisAgent
from .agents.security_response_agent import ResponseAgent
from .agents.configuration_tuning_agent import ConfigTuningAgent
from .graph.builder import build_graph

class MobiLLMService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.llm = instantiate_llm(self.settings)
        self.checkpointer = InMemorySaver()

        self.nodes = {
            "chat": ChatAgent(self.llm, mobillm_chat_tools(), prompts.DEFAULT_CHAT_TASK_BACKGROUND, "mobillm_chat_agent"),
            
            "security_analysis": SecurityAnalysisAgent(self.llm, mobillm_security_analysis_tools(), prompts.DEFAULT_SECURITY_ANLYSIS_TASK_BACKGROUND, "mobillm_security_analysis_agent"),
            
            "classification": SecurityClassificationAgent(self.llm, mobillm_security_classification_tools(), prompts.DEFAULT_SECURITY_CLASSIFICATION_TASK_BACKGROUND, "mobillm_security_classification_agent"),
            
            "response": ResponseAgent(self.llm, mobillm_security_response_tools(), prompts.DEFAULT_SECURITY_RESPONSE_TASK_BACKGROUND, "mobillm_security_response_agent"),
            
            "config_tuning": ConfigTuningAgent(self.llm, mobillm_config_tuning_tools(), prompts.DEFAULT_CONFIG_TUNING_TASK_BACKGROUND, "mobillm_config_tuning_agent"),
        }

        self.graph = build_graph(self.nodes, self.checkpointer)

    def invoke(self, query: str) -> dict:
        tid = str(uuid4())
        input_state = {"thread_id": tid, "query": query, "tools_called": []}
        config = {"configurable": {"thread_id": tid}, "run_id": tid, "run_name": "mobillm_refactored", "tags": ["mobillm"]}
        return self.graph.invoke(input_state, config=config)

    def resume(self, command: dict, thread_id: str) -> dict:
        from langgraph.types import Command
        resume_cmd = Command(resume=command)
        config = {"configurable": {"thread_id": thread_id}}
        return self.graph.invoke(resume_cmd, config=config)
    
    def chat(self, query: str) -> str:
        result = self.invoke(f"[chat] {query}")
        if "chat_response" in result:
            return {"output": result["chat_response"], "thread_id": result["thread_id"]}
        else:
            return {"output": "No chat response available.", "thread_id": result["thread_id"]}

    def security_analysis(self, query: str) -> str:
        result = self.invoke(f"[security analysis] {query}")

        response_message = ""
        response_payload = {}

        if "threat_summary" in result:
            response_message = response_message + f"{result['threat_summary']}"
        if "countermeasures" in result and result["countermeasures"] != "":
            actionable = result['actionable']
            actionable_strategy = result["action_strategy"]
            action_plan = result['action_plan']

            if actionable.lower() == "yes":
                # if actionable, provide the LLM's action plan to user to review
                if actionable_strategy == "config tuning":
                    # if an interrupt has triggered, show the interrupt message to human for review
                    if "__interrupt__" in result.keys():
                        interrupt_value = result["__interrupt__"][0].value
                        # extract modified config data
                        updated_config = interrupt_value.split("```")[1]
                        response_payload["interrupted"] = True  
                        response_payload["action_strategy"] = actionable_strategy
                        response_payload["updated_config"] = updated_config
                        response_payload["interrupt_prompt"] = interrupt_value.split("```")[0]
                        response_message = response_message + f"\n\n**Proposed Response**:\n\nMobiLLM has identified an actionable response to mitigate the event through RAN configuration tuning. Please read following action plan:\n\n{action_plan}\n\n**Would you like to review and approve MobiLLM's actions?**"
            else:
                # if not actionable, output the suggested response
                response_message = response_message + f"""\n\n**Suggested Response**:\n\n{action_plan}\n\n"""

        response_payload["output"] = response_message
        response_payload["thread_id"] = result["thread_id"]

        return response_payload

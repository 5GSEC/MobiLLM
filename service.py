# mobillm/runtime/service.py
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

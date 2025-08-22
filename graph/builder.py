from langgraph.graph import StateGraph, START, END
from ..state import MobiLLMState
from .router import supervisor, route_after_response

def build_graph(nodes: dict, checkpointer) -> any:
    """
    nodes = {
      "chat": ChatAgentNode(...),
      "security_analysis": SecurityAnalysisAgentNode(...),
      "classification": ClassificationAgentNode(...),
      "response": ResponseAgentNode(...),
      "config_tuning": ConfigTuningAgentNode(...),
    }
    """
    g = StateGraph(MobiLLMState)
    
    # register nodes
    g.add_node("supervisor", supervisor)
    g.add_node("mobillm_chat_agent", nodes["chat"].run)
    g.add_node("mobillm_security_analysis_agent", nodes["security_analysis"].run)
    g.add_node("mobillm_security_classification_agent", nodes["classification"].run)
    g.add_node("mobillm_security_response_agent", nodes["response"].run)
    g.add_node("mobillm_config_tuning_agent", nodes["config_tuning"].run)

    # edges
    g.add_edge(START, "supervisor")
    g.add_edge("mobillm_security_analysis_agent", "mobillm_security_classification_agent")
    g.add_edge("mobillm_security_classification_agent", "mobillm_security_response_agent")

    g.add_conditional_edges(
        "supervisor",
        lambda s: s["task"],
        {"chat": "mobillm_chat_agent", "security_analysis": "mobillm_security_analysis_agent"},
    )

    g.add_conditional_edges(
        "mobillm_security_response_agent",
        route_after_response,
        {"config_tuning": "mobillm_config_tuning_agent", "end": END},
    )

    return g.compile(checkpointer=checkpointer)

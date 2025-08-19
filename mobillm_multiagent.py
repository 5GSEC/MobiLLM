import os
import operator
import json
import time
from uuid import uuid4
from typing import TypedDict, Annotated, List, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from IPython.display import display, Image

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, START, MessagesState, END
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import InMemorySaver

from .tools.sdl_apis import *
from .tools.mitre_apis import *
from .tools.control_apis import *
from .prompts import *
from .utils import *

# Define the Langgraph state
class MobiLLMState(TypedDict):
    """
    Represents the state of our graph.
    """
    # generic parameters
    thread_id: str
    tools_called: List[str]
    # task-specific parameters
    task: str
    query: str
    event: str
    network_data: str
    threat_summary: str #Annotated[str, operator.setitem]
    mitre_technique: str #Annotated[str, operator.setitem]
    countermeasures: str #Annotated[str, operator.setitem]
    actionable: Literal["yes", "no"]
    action_strategy: Literal["config tuning", "reboot", "none"]
    action_plan: str
    chat_response: str
    outcome: str

    # config tuning related
    updated_config: str
    original_config: str


class MobiLLM_Multiagent:
    def __init__(self, google_api_key: str=None, gemini_llm_model: str="gemini-2.5-flash"):
        self.init_completed = False
        self.gemini_llm_model = gemini_llm_model
        self.thread_id_list = []
        self.checkpointer = InMemorySaver()

        # --- Configuration ---
        # IMPORTANT: Set your GOOGLE_API_KEY as an environment variable.
        # LangChain's Google Generative AI integration will automatically pick it up.
        # If you don't use dotenv, ensure the environment variable is set in your system.
        # Alternatively, you can pass api_key directly to ChatGoogleGenerativeAI, but env var is preferred.
        if not os.getenv("GOOGLE_API_KEY") and google_api_key == None:
            print("Warning: GOOGLE_API_KEY not found in environment variables.")
            print("Please set it for the LangChain Gemini LLM to work.")
            return
        elif google_api_key is not None:
            os.environ["GOOGLE_API_KEY"] = google_api_key
            # You could set it here as a fallback, but it's not recommended for production:
            # os.environ["GOOGLE_API_KEY"] = "YOUR_ACTUAL_API_KEY"

        # --- LLM Initialization ---
        # Initialize the Gemini LLM through LangChain
        try:
            self.llm = ChatGoogleGenerativeAI(model=self.gemini_llm_model, temperature=0.3)
            # You can adjust temperature and other parameters as needed.
            # temperature=0 makes the model more deterministic, higher values make it more creative.
        except Exception as e:
            print(f"Error initializing Gemini LLM: {e}")
            print("Ensure your GOOGLE_API_KEY is set correctly and you have internet access.")
            return

        self._build_agents()
        self.graph = self._build_graph()
        self.init_completed = True
    
    def _build_agents(self):
        # MobiLLM Chat Agent
        mobillm_chat_tools = [
            # get_ue_mobiflow_data_all_tool,
            fetch_sdl_data_osc_tool,
            get_ue_mobiflow_data_by_index_tool,
            get_ue_mobiflow_description_tool,
            get_bs_mobiflow_data_all_tool,
            get_bs_mobiflow_data_by_index_tool,
            get_bs_mobiflow_description_tool,
            fetch_sdl_event_data_all_tool,
            fetch_sdl_event_data_by_ue_id_tool,
            fetch_sdl_event_data_by_cell_id_tool,
            get_event_description_tool,
            fetch_service_status_tool,
            build_xapp_tool,
            deploy_xapp_tool,
            unDeploy_xapp_tool,
        ]
        self.chat_agent = create_react_agent(model=self.llm, tools=mobillm_chat_tools, prompt=DEFAULT_CHAT_TASK_BACKGROUND, name="mobillm_chat_agent")

        # MobiLLM Security Analysis Agent
        mobillm_security_analysis_tools = [
            get_ue_mobiflow_data_all_tool,
            get_ue_mobiflow_data_by_index_tool,
            get_ue_mobiflow_description_tool,
            get_bs_mobiflow_data_all_tool,
            get_bs_mobiflow_data_by_index_tool,
            get_bs_mobiflow_description_tool,
            fetch_sdl_event_data_all_tool,
            fetch_sdl_event_data_by_ue_id_tool,
            fetch_sdl_event_data_by_cell_id_tool,
            get_event_description_tool,
        ]
        self.security_analysis_agent = create_react_agent(model=self.llm, tools=mobillm_security_analysis_tools, prompt=DEFAULT_SECURITY_ANLYSIS_TASK_BACKGROUND, name="mobillm_security_analysis_agent")
        
        # MobiLLM Security Classification Agent
        mobillm_security_classification_tools = [
            get_all_mitre_fight_techniques,
            get_mitre_fight_technique_by_id,
            search_mitre_fight_techniques,
        ]
        self.classification_agent = create_react_agent(model=self.llm, tools=mobillm_security_classification_tools, prompt=DEFAULT_SECURITY_CLASSIFICATION_TASK_BACKGROUND, name="mobillm_security_classification_agent")
        
        # MobiLLM Response Planning Agent
        mobillm_response_planning_tools = [
            get_all_mitre_fight_techniques,
            get_mitre_fight_technique_by_id,
            get_ran_cu_config_tool
        ]
        self.response_planning_agent = create_react_agent(model=self.llm, tools=mobillm_response_planning_tools, prompt=DEFAULT_RESPONSE_PLANNING_TASK_BACKGROUND, name="mobillm_response_planning_agent")
        
        # MobiLLM Config Tuning Agent
        mobillm_config_tuning_tools = [
            get_all_mitre_fight_techniques,
            get_mitre_fight_technique_by_id,
            get_ran_cu_config_tool,
            update_ran_cu_config_tool,
            reboot_ran_cu_tool,
        ]
        self.config_tuning_agent = create_react_agent(model=self.llm, tools=mobillm_config_tuning_tools, prompt=DEFAULT_CONFIG_TUNING_TASK_BACKGROUND, name="mobillm_config_tuning_agent")

    def _build_graph(self):
        builder = StateGraph(MobiLLMState)

        builder.add_node("supervisor", self.supervisor)
        builder.add_node("mobillm_chat_agent", self.mobillm_chat_agent_node)
        builder.add_node("mobillm_security_analysis_agent", self.mobillm_security_analysis_agent_node)
        builder.add_node("mobillm_security_classification_agent", self.mobillm_security_classification_agent_node)
        builder.add_node("mobillm_response_planning_agent", self.mobillm_response_planning_agent_node)
        builder.add_node("mobillm_config_tuning_agent", self.mobillm_config_tuning_agent_node)

        builder.add_edge(START, "supervisor")
        builder.add_edge("mobillm_security_analysis_agent", "mobillm_security_classification_agent")
        builder.add_edge("mobillm_security_classification_agent", "mobillm_response_planning_agent")

        builder.add_conditional_edges(
            "supervisor",
            lambda state: state["task"],
            {
                "chat": "mobillm_chat_agent",
                "security_analysis": "mobillm_security_analysis_agent"
            }
        )

        builder.add_conditional_edges(
            "mobillm_response_planning_agent",
            self.route_after_response_agent,
            {
                "config_tuning": "mobillm_config_tuning_agent",
                "end": END
            }
        )

        return builder.compile(checkpointer=self.checkpointer)

    # ---------------- Node Functions ----------------

    def supervisor(self, state: MobiLLMState) -> MobiLLMState:
        query = state["query"]
        if "[chat]" in query:
            state["task"] = "chat"
        elif "[security analysis]" in query:
            state["task"] = "security_analysis"
        else:
            raise ValueError("Router received empty input.")
        return state

    def mobillm_chat_agent_node(self, state: MobiLLMState) -> MobiLLMState:
        query = state["query"]
        if not query or query.strip() == "":
            return state
        call_result = self.chat_agent.invoke({"messages": [("user", query)]})
        response = call_result["messages"][-1].content
        state["chat_response"] = response
        state = self.collect_tool_calls(call_result, state)
        return state

    def mobillm_security_analysis_agent_node(self, state: MobiLLMState) -> MobiLLMState:
        start_time = time.time()

        query = state["query"]
        if not query or query.strip() == "":
            return state
        call_result = self.security_analysis_agent.invoke({"messages": [("user", query)]})
        response = call_result["messages"][-1].content
        state["threat_summary"] = response
        state = self.collect_tool_calls(call_result, state)

        end_time = time.time()
        print(f"mobillm_security_analysis_agent_node Time taken: {end_time - start_time} seconds")
        return state

    def mobillm_security_classification_agent_node(self, state: MobiLLMState) -> MobiLLMState:
        start_time = time.time()

        threat_summary = state["threat_summary"]
        if not threat_summary or threat_summary.strip() == "":
            return state

        # call_result = self.classification_agent.invoke({"messages": [("user", threat_summary)]})
        # response = call_result["messages"][-1].content
        # state["mitre_technique"] = response
        # state = self.collect_tool_calls(call_result, state)
        
        techs = {}
        mitre_tech_ids = search_mitre_fight_techniques.invoke({"threat_summary": threat_summary, "top_k": 3})
        for tech_id in mitre_tech_ids:
            tech = get_mitre_fight_technique_by_id.invoke(tech_id)
            techs[tech_id] = {
                "Name": tech.get("Name", ""),
                "Description": tech.get("Description", ""),
                "Mitigations": tech.get("Mitigations", ""),
            }

        state["mitre_technique"] = json.dumps(techs, indent=4)

        end_time = time.time()
        print(f"mobillm_security_classification_agent_node Time taken: {end_time - start_time} seconds")
        return state

    def mobillm_response_planning_agent_node(self, state: MobiLLMState) -> MobiLLMState:
        start_time = time.time()

        threat_summary = state["threat_summary"]
        mitre_technique = state["mitre_technique"]
        if not threat_summary or not mitre_technique:
            return state

        prompt = f"Threat summary:\n{threat_summary}\nRelevant MiTRE FiGHT Techniques:\n{mitre_technique}"
        call_result = self.response_planning_agent.invoke({"messages": [("user", prompt)]})
        raw_response = call_result["messages"][-1].content

        try:
            if raw_response.strip() == "" and call_result["messages"][-1].response_metadata.get("finish_reason") == "MALFORMED_FUNCTION_CALL":
                print("MALFORMED_FUNCTION_CALL detected, retrying...")
                call_result = self.response_planning_agent.invoke({"messages": [("user", prompt)]})
                raw_response = call_result["messages"][-1].content
        except:
            print("raw_response", raw_response)

        response = extract_json_from_string(raw_response.strip().replace("\n", ""))

        if response:
            state["actionable"] = response["actionable"]
            state["action_plan"] = response["action_plan"]
            state["action_strategy"] = response["action_strategy"]
            if state["action_strategy"] == "config tuning":
                state["original_config"] = get_ran_cu_config_tool.invoke("") # store original RAN config before changes
        else:
            state["actionable"] = "no"
            state["action_plan"] = ""
            state["action_strategy"] = "none"

        state["countermeasures"] = response
        state = self.collect_tool_calls(call_result, state)

        end_time = time.time()
        print(f"mobillm_response_planning_agent_node Time taken: {end_time - start_time} seconds")
        return state

    def mobillm_config_tuning_agent_node(self, state: MobiLLMState) -> MobiLLMState:
        actionable = state["actionable"]
        action_plan = state["action_plan"]
        action_strategy = state["action_strategy"]

        if actionable.lower() != "yes" or action_strategy != "config tuning" or not action_plan:
            print("No actionable plan provided.")
            return state

        call_result = self.config_tuning_agent.invoke({"messages": [("user", f"Action plan:\n{action_plan}")]})
        raw_response = call_result["messages"][-1].content

        response = extract_json_from_string(raw_response.strip().replace("\n", ""))

        if response:
            state["actionable"] = response["actionable"]
            state["outcome"] = response["outcome"]
            state["updated_config"] = response["updated_config"]

        state = self.collect_tool_calls(call_result, state)
        return state

    def route_after_response_agent(self, state: MobiLLMState) -> str:
        if state["actionable"].strip() == "yes" and state["action_strategy"].strip() == "config tuning":
            return "config_tuning"
        return "end"

    # ---------------- Public Interface ----------------

    def invoke(self, query: str) -> MobiLLMState:
        """
        Start graph execution.
        """
        thread_id = str(uuid4()) # create a random UUID
        self.thread_id_list.append(thread_id)
        config = {"configurable": {"thread_id": thread_id}}
        input_state = {"thread_id": thread_id, "query": query, "tools_called": []}
        return self.graph.invoke(input_state, config=config)

    def resume(self, command: dict, thread_id: str) -> MobiLLMState:
        """
        Resume graph execution from interrupt.
        """
        if thread_id is None:
            print("Error: A valid thread ID must be provided to resume graph execution")
            return None 
        resume_cmd = Command(resume=command)
        resume_config = {"configurable": {"thread_id": thread_id}}
        return self.graph.invoke(resume_cmd, config=resume_config)

    def draw_graph(self, path="mobillm_langgraph.png"):
        image_data = self.graph.get_graph().draw_mermaid_png()
        with open(path, "wb") as f:
            f.write(image_data)

    def collect_tool_calls(self, call_result, state: MobiLLMState):
        if not call_result or "messages" not in call_result.keys():
            return state
        for msg in call_result["messages"]:
            if "tool_calls" in dir(msg):
                state["tools_called"] += msg.tool_calls
        return state

    def chat(self, query: str) -> str:
        result = self.invoke(f"[chat] {query}")
        if "chat_response" in result:
            return {"output": result["chat_response"], "thread_id": result["thread_id"]}
        else:
            return {"output": "No chat response available.", "thread_id": result["thread_id"]}

    def security_analysis(self, query: str) -> str:
        # return {"output": 'Threat Analysis Report: RRC Null Cipher Event', "interrupted": True, "updated_config": "Example config"} # for testing
        result = self.invoke(f"[security analysis] {query}")

        response_message = ""
        response_payload = {}

        if "threat_summary" in result:
            response_message = response_message + f"{result['threat_summary']}"
        # if "mitre_technique" in result:
        #     print("MITRE Technique:", result["mitre_technique"])
        #     response_message = response_message + f"\n\n**Related MITRE Technique**:\n\n{result['mitre_technique']}\n\n"
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
                        response_payload["original_config"] = result["original_config"] if "original_config" in result else ""
                        response_payload["interrupt_prompt"] = interrupt_value.split("```")[0]
                        response_message = response_message + f"\n\n**Proposed Response**:\n\nMobiLLM has identified an actionable response to mitigate the event through RAN configuration tuning. Please read following action plan:\n\n{action_plan}\n\n**Would you like to review and approve MobiLLM's actions?**"
            else:
                # if not actionable, output the suggested response
                response_message = response_message + f"""\n\n**Suggested Response**:\n\n{action_plan}\n\n"""

        response_payload["output"] = response_message
        response_payload["thread_id"] = result["thread_id"]

        return response_payload

# --- Test Running the Agent ---
if __name__ == "__main__":

    agent = MobiLLM_Multiagent()
    # result = agent.invoke("[chat] How many services are currently in Running state and how long they have been running?")
    # result = agent.invoke("[chat] How many cells are currently deployed in the network?")
    # result = agent.invoke("[chat] How many UEs are connected to the network?")
    # result = agent.invoke("[chat] What are the IMSIs of the UEs connected to the network?")
    # result = agent.invoke("[security analysis] Conduct a thorough security analysis for event ID 4")
    # result = agent.invoke("""[security analysis]
    # Event Details:
    # - Source: MobieXpert
    # - Name: RRC Null Cipher
    # - Cell ID: 20000
    # - UE ID: 54649
    # - Time: Mon Jun 09 2025 11:28:00 GMT-0400 (Eastern Daylight Time)
    # - Severity: Critical
    # - Description: The UE uses null cipher mode in its RRC session, its RRC traffic data is subject to sniffing attack.
    # """)

    result = agent.invoke("""[security analysis] 
    Event Details:
    - Source: MobieXpert
    - Name: Blind DoS
    - Cell ID: 20000
    - UE ID: 39592
    - Time: Mon Jun 09 2025 11:29:14 GMT-0400 (Eastern Daylight Time)
    - Severity: Critical
    - Description: A UE initiated an RRC connection using the same S-TMSI as another connected UE. The previously connected UE's session could have been released by the gNB.
    """)

    while True:
        # Check if an interrupt occurred in the result
        if "__interrupt__" in result.keys():
            interrupt_value = result["__interrupt__"][0].value
            # Ask the user for input to handle the interrupt
            user_input = input(f'Approve the tool call?\n{interrupt_value}\nYour option (yes/edit/no): ')

            if user_input.lower() == "yes":
                resume_command = {"type": "accept"}
            elif user_input.lower() == "no":
                resume_command = {"type": "deny"}
            elif user_input.lower() == "edit":
                new_value = input("Enter your edited value: ")
                resume_command = {
                    "type": "edit",
                    "config_data": new_value
                }
            else:
                print("Invalid input. Please enter 'yes', 'no', or 'edit'.")
                continue  # re-prompt

            # Resume the graph with the chosen command
            thread_id = result["thread_id"]
            result = agent.resume(resume_command, thread_id)
            
        else:
            break  # No interrupt means the flow is complete; exit the loop


    if "chat_response" in result:
        print("Chat Response:", result["chat_response"])
        print("\n\n")
    if "threat_summary" in result:
        print("Threat Summary:", result["threat_summary"])
        print("\n\n")
    if "mitre_technique" in result:
        print("MITRE Technique:", result["mitre_technique"])
        print("\n\n")
    if "countermeasures" in result:
        print("Countermeasures:", result["countermeasures"])
        print("\n\n")
    if "outcome" in result:
        print("Outcome:", result["outcome"])
        print("\n\n")
    if "tools_called" in result:
        print("Tools Called:")
        for tool in result["tools_called"]:
            print(tool)
        print("\n\n")



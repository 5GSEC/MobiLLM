import os
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, START, MessagesState, END
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import InMemorySaver

from ..tools.sdl_apis import *
from ..tools.mitre_apis import *
from ..tools.control_apis import *
from ..prompts import *
from ..utils import *

# Remember to set the env variable using export OAI_RAN_CU_CONFIG_PATH and export GOOGLE_API_KEY before running the script
# export LANGSMITH_TRACING=true
# export LANGSMITH_API_KEY="<your-langchain-api-key>"
# export LANGCHAIN_PROJECT="MobiLLM-Baseline"


gemini_model = "gemini-2.5-flash"
google_api_key = None

# Baseline 1: query the LLM directly without any tools
if not os.getenv("GOOGLE_API_KEY") and google_api_key == None:
    print("Warning: GOOGLE_API_KEY not found in environment variables.")
    print("Please set it for the LangChain Gemini LLM to work.")
elif google_api_key is not None:
    os.environ["GOOGLE_API_KEY"] = google_api_key

llm = ChatGoogleGenerativeAI(model=gemini_model, temperature=0.3)

prompt = '''
You are a 5G cybersecurity analysis assistant. You are familiar with terms in the cellular network domain and 3GPP. Your mission is to help network operators analyze an identified threats or network anomaly. Please generate the following: (1) A short summary of the event, (2) The top 3 most relevant MiTRE FiGHT techniques associated with the event, (3) Come up with 3 effective countermeasures to mitigate the threat.

'''

event = '''

Below is the network event you will analyze:

The MobieXpert xApp has detected a null ciphering or integrity attack. The victim UE uses null cipher or integrity mode in its RRC or NAS session, its  traffic data is subject to sniffing attack over the air. Below is the UE Mobiflow data:
UE;39;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;RRCSetupRequest; ;0;0;0;3;0;0
UE;40;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;RRCSetup; ;2;0;0;0;0;0
UE;41;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;RRCSetupComplete;Registrationrequest;2;1;0;1;0;0
UE;42;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;DLInformationTransfer;Authenticationrequest;2;1;0;0;0;0
UE;43;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;ULInformationTransfer;Authenticationresponse;2;1;0;0;0;0
UE;44;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;DLInformationTransfer;Securitymodecommand;2;1;0;0;0;0
UE;45;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;ULInformationTransfer;Securitymodecomplete;2;1;0;0;0;0
UE;46;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;SecurityModeCommand; ;2;1;0;0;0;0
UE;47;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;SecurityModeComplete; ;2;1;1;0;0;0
UE;48;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;RRCReconfiguration; ;2;1;1;0;0;0
UE;49;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;RRCReconfigurationComplete; ;2;1;1;0;0;0
UE;50;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;UECapabilityEnquiry; ;2;1;1;0;0;0
UE;51;v2.1;SECSM;1749482880;20000;1;54649;54649;0;2089900004719;0;2;0;2;UECapabilityInformation; ;2;1;1;0;0;0
UE;52;v2.1;SECSM;1749482881;20000;1;54649;54649;0;2089900004719;0;2;0;2;ULInformationTransfer;Registrationcomplete;2;2;1;0;0;0
UE;53;v2.1;SECSM;1749482881;20000;1;54649;54649;0;2089900004719;0;2;0;2;ULInformationTransfer;ULNAStransport;2;2;1;0;0;0
UE;54;v2.1;SECSM;1749482881;20000;1;54649;54649;0;2089900004719;0;2;0;2;RRCReconfiguration; ;2;2;1;0;0;0
UE;55;v2.1;SECSM;1749482881;20000;1;54649;54649;0;2089900004719;0;2;0;2;RRCReconfigurationComplete; ;2;2;1;0;0;0
'''

res = llm.invoke(prompt + event)
print(res)


# Baseline 2: A signle Agent design will all available tools

from langchain.agents import AgentExecutor, Tool

# Compose a more structured prompt using the provided templates
tools_prompt = """
You have access to the following tools to help you analyze the event and answer the user's question. 
Use the tools as needed to gather information, perform analysis, and generate your response.
"""

# Use the security analysis and classification backgrounds for a more complete prompt
full_prompt = (
    prompt
    + "\n"
    + tools_prompt
)

tools = [
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
    get_all_mitre_fight_techniques,
    get_mitre_fight_technique_by_id,
    get_ran_cu_config_tool,
    update_ran_cu_config_tool,
    reboot_ran_cu_tool,
]

# Use the prompt as a string, not as a PromptTemplate object
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=full_prompt
)


# Example usage: invoke the agent with the event
result = agent.invoke({"messages": [("user", event)]})
print(result)

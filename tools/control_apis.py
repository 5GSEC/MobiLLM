import subprocess
import os
import time
from ..utils import *
from langchain.tools import tool
from langgraph.types import interrupt

@tool
def get_ran_cu_config_tool() -> str:
    '''
    Get the configuration of the currently running CU. The available configuration include:
    - security: The preferred ciphering and integrity algorithms
    - network: The network configurations including IP addresses, ports, and identities like gNB ID, tracking area code, etc.
    - physical parameters: pdcch_ConfigSIB1
    Return:
        str: The configuration of the currently running CU.
    '''
    # load OAI RAN path from env variable
    oai_ran_cu_config_path = os.getenv('OAI_RAN_CU_CONFIG_PATH', "")
    if oai_ran_cu_config_path is None or oai_ran_cu_config_path == "":
        return "OAI RAN CU configuration path is not set in environment variables."

    return get_oai_ran_cu_config(oai_ran_cu_config_path)

def get_oai_ran_cu_config(oai_ran_cu_config_path: str) -> str:
    '''
    Get the OAI RAN CU configuration 
    '''
    # read the configuration file
    if os.path.exists(oai_ran_cu_config_path):
        try:
            with open(oai_ran_cu_config_path, 'r') as config_file:
                config_data = config_file.read()
            return config_data
        except Exception as e:
            print(f"Error reading OAI RAN CU configuration: {e}")
            return f"Error reading configuration from path {oai_ran_cu_config_path}"

@tool
def update_ran_cu_config_tool(config_data: str) -> str:
    '''
    Update the configuration of the currently running CU. The invocation will be sent to the human in the loop for approval or edits.
    Return:
        str: A message indicating whether the configuration was successfully updated or not.
    Args:
        config_data (str): The new configuration data to be written to the CU.
    '''
    # load OAI RAN path from env variable
    oai_ran_cu_config_path = os.getenv('OAI_RAN_CU_CONFIG_PATH', '')
    if oai_ran_cu_config_path is None or oai_ran_cu_config_path == "":
        return "OAI RAN CU configuration path is not set in environment variables."

    response = interrupt(  
        f"Trying to call `update_ran_cu_config_tool` to update config at {oai_ran_cu_config_path} with the following content \n\n```{config_data}```\n\n**Please approve or deny this action.**"
    )
    if response["type"] == "accept":
        pass
    elif response["type"] == "edit":
        config_data = response["config_data"]
    elif response["type"] == "deny":
        return "update_ran_cu_config_tool operation denied by the user."
    else:
        raise ValueError(f"Unknown response type: {response['type']}")

    return update_oai_ran_cu_config(config_data, oai_ran_cu_config_path)

def update_oai_ran_cu_config(config_data: str, oai_ran_cu_config_path: str) -> str:
    '''
    Update the OAI RAN CU configuration 
    '''
    # return f"OAI RAN CU configuration updated successfully at path {oai_ran_cu_config_path}." # TODO: for testing
    
    # write the configuration data to the file
    try:
        with open(oai_ran_cu_config_path, 'w') as config_file:
            config_file.write(config_data) 
        return f"OAI RAN CU configuration updated successfully at path {oai_ran_cu_config_path}."
    except Exception as e:
        return f"Error updating OAI RAN CU configuration: {e}"

@tool
def reboot_ran_cu_tool() -> str:
    '''
    Reboot the RAN CU. The invocation will be sent to the human in the loop for approval or edits.
    '''
    response = interrupt(  
        f"Trying to call `reboot_ran_cu_tool` (no argument provided)."
        "Please approve or suggest edits."
    )
    if response["type"] == "accept":
        return reboot_oai_ran()
    elif response["type"] == "deny":
        return "reboot_ran_cu_tool operation denied by the user."
    else:
        return f"Unknown response type: {response['type']}"

def reboot_oai_ran() -> str:
    '''
    Reboot the OAI RAN CU.
    '''
    # return "OAI RAN Containers restarted successfully." # TODO: for testing 

    # load OAI RAN path from env variable
    oai_ran_cu_config_path = os.getenv('OAI_RAN_CU_CONFIG_PATH', '')
    if oai_ran_cu_config_path is None or oai_ran_cu_config_path == "":
        return "OAI RAN CU configuration path is not set in environment variables."

    oai_ran_cu_path = os.path.dirname(oai_ran_cu_config_path)

    # Step into that directory
    try:
        # print(f"Changing directory to: {oai_ran_cu_path}")
        # shutdown all containers
        res = subprocess.run(["docker-compose", "down", "mobiflow-agent-1"], cwd=oai_ran_cu_path, check=True)
        if res.returncode != 0:
            return "Error while shutting down mobiflow-agent-1 containers"
        res = subprocess.run(["./kill_gnb_1_demo.sh"], cwd=oai_ran_cu_path, check=True)
        if res.returncode != 0:
            return "Error while shutting down RAN containers"
        time.sleep(15)
        # Run docker-compose commands in that directory
        res = subprocess.run(["./run_gnb_1_demo.sh"], cwd=oai_ran_cu_path, check=True)
        if res.returncode != 0:
            return "Error while shutting down mobiflow-agent-1 containers"

        # res = subprocess.run(["docker-compose", "restart", "oai-cu-1", "oai-du-1"], cwd=oai_ran_cu_path, check=True)
        # if res.returncode != 0:
        #     return "Error while restarting oai-cu-1 oai-du-1 containers"
        # time.sleep(5)
        # res = subprocess.run(["./run_mobiflow_agent_1.sh"], cwd=oai_ran_cu_path, check=True)
        # if res.returncode != 0:
        #     return "Error while restarting mobiflow-agent-1 containers"
        # time.sleep(5)
        # res = subprocess.run(["docker-compose", "restart", "oai-nr-ue-4"], cwd=oai_ran_cu_path, check=True)
        # if res.returncode != 0:
        #     return "Error while restarting oai-nr-ue-4 container"
        # time.sleep(5)
        # res = subprocess.run(["docker-compose", "restart", "oai-nr-ue-5"], cwd=oai_ran_cu_path, check=True)
        # if res.returncode != 0:
        #     return "Error while restarting oai-nr-ue-5 container"
        return "OAI RAN Containers restarted successfully."
    except subprocess.CalledProcessError as e:
        return f"Error while restarting OAI containers: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"

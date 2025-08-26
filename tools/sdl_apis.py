import subprocess
import os
import json
from langchain.tools import tool
from ..utils import *
from .global_vars import *

def get_sample_data_path(filename: str) -> str:
    """
    Get the absolute path to a file in the 5G-Sample-Data directory.
    This ensures the file can be found regardless of where the script is executed from.
    """
    current_dir = os.path.dirname(__file__)
    return os.path.join(current_dir, "5G-Sample-Data", filename)

def get_xapp_root_path() -> str:
    """
    Get the xApp root directory path from environment variable XAPP_ROOT_PATH.
    If not set, falls back to 'xApp' subdirectory of current working directory.
    """
    xapp_root = os.getenv("XAPP_ROOT_PATH")
    if xapp_root:
        return xapp_root
    else:
        return os.path.join(os.getcwd(), "xApp")

# gloabal mappings
xapp_names = {
    "MobieXpert xApp": "MobieXpert",
    "MobiWatch xApp" : "MobiWatch",
    "MobiFlow Auditor xApp": "mobiflow-auditor",
}

branch_map = {
    "mobiflow-auditor": "main",
    "MobiWatch": "main",
    "MobieXpert": "main"
    # add more if needed
}

sdl_namespaces = ["ue_mobiflow", "bs_mobiflow", "mobiexpert-event", "mobiwatch-event"]
pod_names = ["ricplt-e2mgr", "mobiflow-auditor", "mobiexpert-xapp", "mobiwatch-xapp"]
display_names = ["E2 Manager", "MobiFlow Auditor xApp", "MobieXpert xApp", "MobiWatch xApp"]

active_ue_data_time_series = {}
active_bs_data_time_series = {}
critical_event_time_series = {}
total_event_time_series = {}
current_active_ue_ids = []
max_time_series_length = 90 # update once every 10 seconds, 15 minutes = 900 seconds = 90 data points

def fetch_service_status_osc() -> dict:
    ''' 
        Fetch the status of the network control-plane services, including xApps deployed at OSC near-RT RIC.
        An empty string will return if the specified service is inactive.
        Returns:
            dict: A dictionary containing the status of each service
    '''
    services = {}

    # if simulation mode is enabled, read from the sample data file
    if simulation_mode is True:
        with open(get_sample_data_path("5G-Sample-Data - Service.csv"), "r") as f:
            lines = f.readlines()
            for line in lines:
                tokens = line.split(":")
                if tokens[0].strip() not in pod_names:
                    services[tokens[0].strip()] = tokens[1].strip()
                else:
                    pod_index = pod_names.index(tokens[0].strip())
                    display_name = display_names[pod_index]
                    services[display_name] = tokens[1].strip()
        return services

    command = "kubectl get pods -A | awk {'print $2\";\"$3\";\"$4\";\"$5\";\"$6'}"
    output = execute_command(command)
    lines = output.split("\n")

    for pod in pod_names:
        pod_index = pod_names.index(pod)
        display_name = display_names[pod_index]
        services[display_name] = ""

    for line in lines:
        for pod in pod_names:
            if pod in line:
                pod_index = pod_names.index(pod)
                display_name = display_names[pod_index]
                services[display_name] = line.replace("(", "") # tmp soluton to solve getting (4d20h ago) as the age
                break

    # MobiFlow Agent
    display_name = "MobiFlow Agent"
    program_name = "mobiflow-agent"
    
    command_ps = "docker ps --format {{.ID}}\\\\t{{.Names}}\\\\t{{.Status}} --filter name=mobiflow-agent"
    process_ps = execute_command(command_ps)
    lines = process_ps.strip().split('\n')
    services[display_name] = ""  # Default to empty string if not found

    if lines and lines != ['']:
        parts = lines[-1].split('\t')
        if len(parts) >= 3:
            # Skip malformed lines
            container_id = parts[0]
            container_name = parts[1]
            raw_status = parts[2] # e.g., "Up 2 hours", "Exited (0) 5 minutes ago"

            status_parts = raw_status.split(' ')
            status = "Unknown"
            up_time = "N/A"

            # Determine status and uptime
            if status_parts[0] == "Up":
                status = "Running"
                # Extract uptime from "Up X (minutes/hours/days)"
                if len(status_parts) >= 3:
                    up_time = status_parts[1] + status_parts[2][0] # e.g., "95m", "2h", "1d"
            elif status_parts[0] == "Exited":
                status = "Inactive"
                if len(status_parts) >= 4:
                    up_time = status_parts[2] + status_parts[3][0] # e.g., "5m", "1h"
            else:
                status = raw_status # Fallback if format is unexpected

            # Get restart count using docker inspect
            restart_count = 0
            try:
                command_inspect = "docker inspect -f '{{.RestartCount}}' %s" % program_name
                process_inspect = execute_command(command_inspect)
                restart_count = int(process_inspect.strip())
            except subprocess.CalledProcessError as e_inspect:
                print(f"Error inspecting container {container_id}: {e_inspect}")
            except ValueError:
                print(f"Could not parse restart count for {container_name}")


            # Format and print the output
            # The '1/1' part is assumed to be a static string as per your example.
            formatted_output = f"{display_name};1/1;{status};{restart_count};{up_time}"
            services[display_name] = formatted_output
    

    # command = f"pgrep -x {program_name}" # need to makes sure pgrep is available
    # output = execute_command(command)
    # if output:
    #     services["MobiFlow Agent"] = " ; ;Running; ;" # TODO get the age of the process
    # else:
    #     services["MobiFlow Agent"] = ""
    
    # print(json.dumps(services, indent=4))
    return services

@tool
def fetch_service_status_tool() -> dict:
    ''' 
    Fetch the status of the network control-plane services, including xApps deployed at OSC near-RT RIC.
        An empty string will return if the specified service is inactive.
    Returns:
        dict: A dictionary containing the status of each service. Each service's state is represented as a string in the format "pod_name;pod_status;pod_restart_count;pod_age".
    '''
    return fetch_service_status_osc()

def fetch_sdl_data_osc() -> dict:
    ''' 
    Fetch network data from SDL
        Returns:
            dict: A dictionary containing the network data
    '''
    # get namespaces from SDL
    get_ns_command = 'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get namespaces'
    ns_output = execute_command(get_ns_command)

    # Parse namespaces (split by newlines)
    namespaces = [ns.strip() for ns in ns_output.split("\n") if ns.strip()]
    # print(namespaces)

    # Iterate over the desired namespaces to get all keys
    ns_target = sdl_namespaces
    key_len_by_namespace = {}

    for namespace in ns_target:
        if namespace in namespaces:
            get_key_command = f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get keys {namespace}'
            keys_output = execute_command(get_key_command)

            # Parse keys (split by newlines)
            keys = [key.strip() for key in keys_output.split("\n") if key.strip()]

            # Store the keys by namespace
            key_len_by_namespace[namespace] = len(keys)
        else:
            print(f"Namespace '{namespace}' not found in the available namespaces.")
            key_len_by_namespace[namespace] = -1


    max_batch_get_value = 20  # max number of keys to fetch in a single batch
    get_val_command = lambda ns, key: f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get {ns} {key}'  # template get value command
    network = {}


    # get all BS mobiflow
    bs_mobiflow_key = ns_target[1]
    bs_meta = "DataType,Index,Timestamp,Version,Generator,nr_cell_id,mcc,mnc,tac,report_period,status".split(",")
    values = get_bs_mobiflow_data_all_tool.invoke("")
    for val in values:
        bs_mf_item = val.split(";")
        nr_cell_id = bs_mf_item[bs_meta.index("nr_cell_id")]
        timestamp = bs_mf_item[bs_meta.index("Timestamp")]
        mcc = bs_mf_item[bs_meta.index("mcc")]
        mnc = bs_mf_item[bs_meta.index("mnc")]
        tac = bs_mf_item[bs_meta.index("tac")]
        report_period = bs_mf_item[bs_meta.index("report_period")]
        status = bs_mf_item[bs_meta.index("status")]
        network[nr_cell_id] = {
            "mcc": mcc,
            "mnc": mnc,
            "tac": tac,
            "report_period": report_period,
            "status": status,
            "timestamp": timestamp,
            "ue": {}
        }

    # get all UE mobiflow
    ue_mobiflow_key = ns_target[0]
    ue_meta = "DataType,Index,Version,Generator,Timestamp,nr_cell_id,gnb_cu_ue_f1ap_id,gnb_du_ue_f1ap_id,rnti,s_tmsi,mobile_id,rrc_cipher_alg,rrc_integrity_alg,nas_cipher_alg,nas_integrity_alg,rrc_msg,nas_msg,rrc_state,nas_state,rrc_sec_state,reserved_field_1,reserved_field_2,reserved_field_3".split(",")
    values = get_ue_mobiflow_data_all_tool.invoke("")
    for val in values:
        ue_mf_item = val.split(";")
        ue_id = ue_mf_item[ue_meta.index("gnb_du_ue_f1ap_id")]
        nr_cell_id = ue_mf_item[ue_meta.index("nr_cell_id")]
        if nr_cell_id in network:
            ue_timestamp = ue_mf_item[ue_meta.index('Timestamp')]
            bs_timestamp = network[nr_cell_id]["timestamp"]
            # don't report UE if the UE's timestamp is older than the BS's timestamp, which means the UE is not connected to the BS
            if ue_timestamp < bs_timestamp:
                continue
            if ue_id not in network[nr_cell_id]["ue"]:
                # add UE
                network[nr_cell_id]["ue"][ue_id] = {
                    "gnb_cu_ue_f1ap_id": ue_mf_item[ue_meta.index("gnb_cu_ue_f1ap_id")],
                    "rnti": ue_mf_item[ue_meta.index("rnti")],
                    "s_tmsi": ue_mf_item[ue_meta.index("s_tmsi")],
                    "mobile_id": ue_mf_item[ue_meta.index("mobile_id")],
                    "rrc_cipher_alg": ue_mf_item[ue_meta.index("rrc_cipher_alg")],
                    "rrc_integrity_alg": ue_mf_item[ue_meta.index("rrc_integrity_alg")],
                    "nas_cipher_alg": ue_mf_item[ue_meta.index("nas_cipher_alg")],
                    "nas_integrity_alg": ue_mf_item[ue_meta.index("nas_integrity_alg")],
                    "timestamp": ue_mf_item[ue_meta.index('Timestamp')],
                    "mobiflow": [{
                        "msg_id": int(ue_mf_item[ue_meta.index("Index")]),
                        "abnormal": {
                            "value": False,
                            "source": "None"
                        },
                        "rrc_msg": ue_mf_item[ue_meta.index("rrc_msg")],
                        "nas_msg": ue_mf_item[ue_meta.index("nas_msg")],
                        "rrc_state": ue_mf_item[ue_meta.index("rrc_state")],
                        "nas_state": ue_mf_item[ue_meta.index("nas_state")],
                        "rrc_sec_state": ue_mf_item[ue_meta.index("rrc_sec_state")],
                        "reserved_field_1": ue_mf_item[ue_meta.index("reserved_field_1")],
                        "reserved_field_2": ue_mf_item[ue_meta.index("reserved_field_2")],
                        "reserved_field_3": ue_mf_item[ue_meta.index("reserved_field_3")],
                        "timestamp": ue_mf_item[ue_meta.index('Timestamp')],
                    }],
                    "event": {}
                }
            else:
                # update UE
                network[nr_cell_id]["ue"][ue_id]["gnb_cu_ue_f1ap_id"] = ue_mf_item[ue_meta.index("gnb_cu_ue_f1ap_id")]
                network[nr_cell_id]["ue"][ue_id]["rnti"] = ue_mf_item[ue_meta.index("rnti")]
                network[nr_cell_id]["ue"][ue_id]["s_tmsi"] = ue_mf_item[ue_meta.index("s_tmsi")]
                network[nr_cell_id]["ue"][ue_id]["mobile_id"] = ue_mf_item[ue_meta.index("mobile_id")]
                network[nr_cell_id]["ue"][ue_id]["rrc_cipher_alg"] = ue_mf_item[ue_meta.index("rrc_cipher_alg")]
                network[nr_cell_id]["ue"][ue_id]["rrc_integrity_alg"] = ue_mf_item[ue_meta.index("rrc_integrity_alg")]
                network[nr_cell_id]["ue"][ue_id]["nas_cipher_alg"] = ue_mf_item[ue_meta.index("nas_cipher_alg")]
                network[nr_cell_id]["ue"][ue_id]["nas_integrity_alg"] = ue_mf_item[ue_meta.index("nas_integrity_alg")]
                network[nr_cell_id]["ue"][ue_id]["Timestamp"] = ue_mf_item[ue_meta.index("Timestamp")]
                network[nr_cell_id]["ue"][ue_id]["mobiflow"].append({
                    "msg_id": int(ue_mf_item[ue_meta.index("Index")]),
                    "abnormal": {
                        "value": False,
                        "source": "None"
                    },
                    "rrc_msg": ue_mf_item[ue_meta.index("rrc_msg")],
                    "nas_msg": ue_mf_item[ue_meta.index("nas_msg")],
                    "rrc_state": ue_mf_item[ue_meta.index("rrc_state")],
                    "nas_state": ue_mf_item[ue_meta.index("nas_state")],
                    "rrc_sec_state": ue_mf_item[ue_meta.index("rrc_sec_state")],
                    "reserved_field_1": ue_mf_item[ue_meta.index("reserved_field_1")],
                    "reserved_field_2": ue_mf_item[ue_meta.index("reserved_field_2")],
                    "reserved_field_3": ue_mf_item[ue_meta.index("reserved_field_3")],
                    "timestamp": ue_mf_item[ue_meta.index('Timestamp')],
                })
        else:
            print("nr_cell_id not found")

    # print(json.dumps(network, indent=4))

    # update time series data
    update_network_time_series(network)

    return network

def update_network_time_series(network: dict):
    '''
    Update the time series data for the network data. Invoked when fetch_sdl_data_osc is called.
    '''
    current_active_ue = 0
    current_active_bs = 0
    global current_active_ue_ids
    current_active_ue_ids = []
    for nr_cell_id in network.keys():
        if int(network[nr_cell_id]["status"]) == 1:
            current_active_bs += 1
            if "ue" in network[nr_cell_id].keys():
                current_active_ue += len(network[nr_cell_id]["ue"].keys())
                current_active_ue_ids.extend([int(ue_id) for ue_id in network[nr_cell_id]["ue"].keys()])
    
    # get current timestamp (integer)
    current_ts = int(time.time())
    active_bs_data_time_series[current_ts] = current_active_bs
    active_ue_data_time_series[current_ts] = current_active_ue

    # remove the oldest timestamp
    if len(active_bs_data_time_series) > max_time_series_length:
        active_bs_data_time_series.pop(min(active_bs_data_time_series.keys()))
    if len(active_ue_data_time_series) > max_time_series_length:
        active_ue_data_time_series.pop(min(active_ue_data_time_series.keys()))

def update_event_time_series(event: dict):
    '''
    Update the time series data for the event data. Invoked when fetch_sdl_event_data_osc is called.
    '''
    current_critical_event = 0
    current_total_event = 0
    for event_id in event.keys():
        if event[event_id]["active"] is False:
            continue # skip inactive events
        if event[event_id]["severity"] == "Critical":
            current_critical_event += 1
        current_total_event += 1
    
    current_ts = int(time.time())
    critical_event_time_series[current_ts] = current_critical_event
    total_event_time_series[current_ts] = current_total_event

    # remove the oldest timestamp
    if len(critical_event_time_series) > max_time_series_length:
        critical_event_time_series.pop(min(critical_event_time_series.keys()))
    if len(total_event_time_series) > max_time_series_length:
        total_event_time_series.pop(min(total_event_time_series.keys()))

def get_time_series_data() -> dict:
    global active_bs_data_time_series, active_ue_data_time_series
    global critical_event_time_series, total_event_time_series
    ts = {}
    # active_bs_data_time_series_example = {
    #     1721731200: 0,
    #     1721731210: 0,
    #     1721731220: 0,
    #     1721731230: 4,
    #     1721731240: 5,
    #     1721731250: 5,
    #     1721731260: 5,
    #     1721731270: 5,
    #     1721731280: 8,
    #     1721731290: 8,
    # }
    ts["active_bs"] = active_bs_data_time_series
    ts["active_ue"] = active_ue_data_time_series
    ts["critical_event"] = critical_event_time_series
    ts["total_event"] = total_event_time_series
    return ts

@tool
def fetch_sdl_data_osc_tool() -> dict:
    ''' 
    Fetch network data from SDL, including the MobiFlow data reflecting the UE and base station status and activities.
        Returns:
            dict: A dictionary containing the network data
    '''
    return fetch_sdl_data_osc()

def fetch_sdl_event_data_osc() -> dict:
    ''' 
    Fetch network event data generated by MobieXpert and MobiWatch from SDL
    Returns:
        dict: A dictionary containing the network event data.
    '''
    event = {}
    event_id_counter = 1
    # if simulation mode is enabled, read from the sample data file
    if simulation_mode is True:
        # read MobieXpert events
        with open(get_sample_data_path("5G-Sample-Data - Event - MobieXpert.csv"), "r") as f:
            event_meta = "Event ID,Event Name,Affected base station ID,Time,Affected UE ID,Description,Level".split(",")
            lines = f.readlines()
            for line in lines:
                event_item = line.strip().split(";")
                event[event_id_counter] = {
                    "id": event_id_counter,
                    "source": "MobieXpert",
                    "name": event_item[event_meta.index("Event Name")],
                    "cellID": event_item[event_meta.index("Affected base station ID")],
                    "ueID": event_item[event_meta.index("Affected UE ID")],
                    "timestamp": event_item[event_meta.index("Time")],
                    "severity": event_item[event_meta.index("Level")],
                    "description": event_item[event_meta.index("Description")],
                    "active": True
                }
                event_id_counter += 1

        # read MobiWatch events
        with open(get_sample_data_path("5G-Sample-Data - Event - MobiWatch.csv"), "r") as f:
            event_meta = "id,source,name,cellID,ueID,timestamp,severity,mobiflow_index,description".split(",")
            lines = f.readlines()
            for line in lines:
                event_item = line.strip().split(";")
                model_name = event_item[0]
                # f"{model_name};{event['event_name']};{event['nr_cell_id']};{event['ue_id']};{event['timestamp']};{index_str};{event_desc}"
                event[event_id_counter] = {
                    "id": event_id_counter,
                    "source": f"MobiWatch_{model_name}",
                    "name": event_item[1],
                    "cellID": event_item[2],
                    "ueID": event_item[3],
                    "timestamp": event_item[4],
                    "severity": "Warning",
                    "mobiflow_index": event_item[5],
                    "description": event_item[6],
                    "active": True
                }
                event_id_counter += 1

        return event

    # get namespaces from SDL
    get_ns_command = 'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get namespaces'
    ns_output = execute_command(get_ns_command)

    # Parse namespaces (split by newlines)
    namespaces = [ns.strip() for ns in ns_output.split("\n") if ns.strip()]

    # Iterate over the desired namespaces to get all keys
    ns_target = ["mobiexpert-event", "mobiwatch-event"]
    key_len_by_namespace = {}

    for namespace in ns_target:
        if namespace in namespaces:
            get_key_command = f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get keys {namespace}'
            keys_output = execute_command(get_key_command)

            # Parse keys (split by newlines)
            keys = [key.strip() for key in keys_output.split("\n") if key.strip()]

            # Store the keys by namespace
            key_len_by_namespace[namespace] = len(keys)
        else:
            print(f"Namespace '{namespace}' not found in the available namespaces.")
            key_len_by_namespace[namespace] = -1

    # variable to hold sdl event data
    max_batch_get_value = 20  # max number of keys to fetch in a single batch
    get_val_command = lambda ns, key: f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get {ns} {key}'  # template get value command
    
    # get all mobiexpert-event
    event_key = ns_target[0]
    event_meta = "Event ID,Event Name,Affected base station ID,Time,Affected UE ID,Description,Level".split(",")
    for i in range(1, key_len_by_namespace[event_key] + 1, max_batch_get_value):  # event index starts from 1
        # Create a batch of keys
        batch_keys = [str(j) for j in range(i, min(i + max_batch_get_value, key_len_by_namespace[event_key] + 1))]

        # Create the command for the batch
        command = get_val_command(event_key, " ".join(batch_keys))
        value = execute_command(command)

        # Process each value in the batch
        values = [val.strip() for val in value.split("\n") if val.strip()]

        for val in values:
            val = ''.join([c for c in val if 32 <= ord(c) <= 126])[2:]  # Remove non-ASCII characters
            event_item = val.split(";")
                        
            # create and insert attack event
            event[event_id_counter] = {
                "id": event_id_counter,
                "source": "MobieXpert",
                "name": event_item[event_meta.index("Event Name")],
                "cellID": event_item[event_meta.index("Affected base station ID")],
                "ueID": event_item[event_meta.index("Affected UE ID")],
                "timestamp": event_item[event_meta.index("Time")],
                "severity": event_item[event_meta.index("Level")],
                "description": event_item[event_meta.index("Description")],
                "active": True
            }

            if int(event_item[event_meta.index("Affected UE ID")]) not in current_active_ue_ids:
                event[event_id_counter]["active"] = False # indicate the event is not related to active UEs

            event_id_counter += 1

    # get all mobiwatch-event
    event_key = ns_target[1]
    for i in range(1, key_len_by_namespace[event_key] + 1, max_batch_get_value):  # event index starts from 1
        # Create a batch of keys
        batch_keys = [str(j) for j in range(i, min(i + max_batch_get_value, key_len_by_namespace[event_key] + 1))]

        # Create the command for the batch
        command = get_val_command(event_key, " ".join(batch_keys))
        value = execute_command(command)
        
        # Process each value in the batch
        values = [val.strip() for val in value.split("\n") if val.strip()]

        for val in values:
            val = ''.join([c for c in val if 32 <= ord(c) <= 126])[2:]  # Remove non-ASCII characters
            event_item = val.split(";")
            model_name = event_item[0]
            if model_name == "autoencoder_v2":
                # f"{model_name};{event['event_name']};{event['nr_cell_id']};{event['ue_id']};{event['timestamp']};{index_str};{event_desc}"
                event[event_id_counter] = {
                    "id": event_id_counter,
                    "source": f"MobiWatch_{model_name}",
                    "name": event_item[1],
                    "cellID": event_item[2],
                    "ueID": event_item[3],
                    "timestamp": event_item[4],
                    "severity": "Warning", # TODO: this should be populated from the xApp data
                    "mobiflow_index": event_item[5],
                    "description": event_item[6],
                    "active": True
                }
                if int(event_item[3]) not in current_active_ue_ids:
                    event[event_id_counter]["active"] = False # indicate the event is not related to active UEs
                event_id_counter += 1

            elif model_name == "lstm_v2":
                # f"{model_name};{event['event_name']};{event['nr_cell_id']};{event['ue_id']};{event['timestamp']};{str(merged_sequence_list)};{event_desc}"
                event[event_id_counter] = {
                    "id": event_id_counter,
                    "source": f"MobiWatch_{model_name}",
                    "name": event_item[1],
                    "cellID": event_item[2],
                    "ueID": event_item[3],
                    "timestamp": event_item[4],
                    "severity": "Warning", # TODO: this should be populated from the xApp data
                    "mobiflow_index": event_item[5],
                    "description": event_item[6],
                    "active": True
                }
                if int(event_item[3]) not in current_active_ue_ids:
                    event[event_id_counter]["active"] = False # indicate the event is not related to active UEs
                event_id_counter += 1
    # update event time series data
    update_event_time_series(event)

    return event

@tool
def fetch_sdl_event_data_all_tool() -> dict:
    ''' 
    Fetch all network event data generated by MobieXpert and MobiWatch from SDL
    Returns:
        dict: A dictionary containing the network event data. Each dict object contains the following keys: ['id', 'source', 'name', 'cellID', 'ueID', 'timestamp', 'severity', 'description']
        Example event: {'id': 1, 'source': 'MobieXpert', 'name': 'RRC Null Cipher', 'cellID': '12345678', 'ueID': '38940', 'timestamp': '1745783800', 'severity': 'Critical', 'description': 'The UE uses null cipher mode in its RRC session, its RRC traffic data is subject to sniffing attack.'}
    '''
    return fetch_sdl_event_data_osc()

@tool
def fetch_sdl_event_data_by_ue_id_tool(ue_id: str) -> dict:
    ''' 
    Fetch network event data generated by MobieXpert and MobiWatch from SDL by UE ID
    Args:
        ue_id (str): The UE ID to filter the events.
    Returns:
        dict: A dictionary containing the network event data filtered by UE ID. Each dict object contains the following keys: ['id', 'source', 'name', 'cellID', 'ueID', 'timestamp', 'severity', 'description']
        Example event: {'id': 1, 'source': 'MobieXpert', 'name': 'RRC Null Cipher', 'cellID': '12345678', 'ueID': '38940', 'timestamp': '1745783800', 'severity': 'Critical', 'description': 'The UE uses null cipher mode in its RRC session, its RRC traffic data is subject to sniffing attack.'}
    '''
    all_events = fetch_sdl_event_data_osc()
    filtered_events = {k: v for k, v in all_events.items() if v.get("ueID") == ue_id}
    return filtered_events

@tool
def fetch_sdl_event_data_by_cell_id_tool(cell_id: str) -> dict:
    ''' 
    Fetch network event data generated by MobieXpert and MobiWatch from SDL by Cell ID
    Args:
        cell_id (str): The Cell ID to filter the events.
    Returns:
        dict: A dictionary containing the network event data filtered by Cell ID. Each dict object contains the following keys: ['id', 'source', 'name', 'cellID', 'ueID', 'timestamp', 'severity', 'description']
        Example event: {'id': 1, 'source': 'MobieXpert', 'name': 'RRC Null Cipher', 'cellID': '12345678', 'ueID': '38940', 'timestamp': '1745783800', 'severity': 'Critical', 'description': 'The UE uses null cipher mode in its RRC session, its RRC traffic data is subject to sniffing attack.'}
    '''
    all_events = fetch_sdl_event_data_osc()
    filtered_events = {k: v for k, v in all_events.items() if v.get("cellID") == cell_id}
    return filtered_events

def build_xapp_osc(xapp_name: str):
    """
    Build the xApp from the given xapp_name.
    Steps:
        step 1: get xapp_name
        step 2: go into xApp dir (if it doesn't exist, create it)
        step 3: git clone the xApp repo
        step 4: run Docker registry
        step 5: cd [xapp_name] and then ./build.sh
        step 6: check if build is successful
    Args:
        xapp_name (str): The name of the xApp to build.
    Returns:
        dict: A dictionary containing the status of the build process.
    """

    # if simulation mode is enabled, return sample message
    if simulation_mode is True:
        return {"message": "Build finished", "logs": []}, 200

    original_cwd = os.getcwd()
    logs = []  # We'll accumulate logs here

    try:
        if xapp_name in xapp_names:
            xapp_name = xapp_names[xapp_name]
            logs.append(f"[buildXapp] Using {xapp_name} repo for {xapp_name}")
        else:
            logs.append(f"[buildXapp] Using {xapp_name} repo for {xapp_name}")
            return {"error": "Invalid xapp_name"}, 400

        logs.append(f"[buildXapp] Start building xApp: {xapp_name}")

        # Step 1: create xApp folder if it doesn't exist
        xapp_root = get_xapp_root_path()
        if not os.path.exists(xapp_root):
            try:
                os.makedirs(xapp_root)
                logs.append(f"Created directory: {xapp_root}")
            except FileExistsError:
                # If the folder is already there, just continue
                logs.append(f"Directory {xapp_root} already exists.")

        os.chdir(xapp_root)
        logs.append(f"Changed directory to: {os.getcwd()}")


        # Step 2: clone the repo    
        # If the xapp_name folder doesn't exist, clone it.
        if not os.path.exists(xapp_name):
            
            git_url = f"https://github.com/5GSEC/{xapp_name}.git"
            clone_output = execute_command(f"git clone {git_url}")
            logs.append(f"git clone output: {clone_output}")

            # Check if xApp folder is there
            if not os.path.exists(xapp_name):
                logs.append(f"Failed to clone {git_url}")
                return {"error": f"Failed to clone {git_url}", "logs": logs}, 500

            os.chdir(xapp_name)
            logs.append(f"Now in xApp folder (newly cloned): {os.getcwd()}")

        else:
            # If folder already exists, just cd in and do a checkout + pull
            logs.append(f"{xapp_name} folder already exists. Will attempt to update it.")
            os.chdir(xapp_name)
            logs.append(f"Now in existing xApp folder: {os.getcwd()}")
            # We won't remove; we'll checkout branch & pull


        # Step 3: Optionally checkout a branch depending on xapp_name
        # You can customize this dict with more xApp->branch mappings
        branch_to_checkout = branch_map.get(xapp_name)
        if branch_to_checkout:
            checkout_output = execute_command(f"git checkout {branch_to_checkout}")
            logs.append(f"Checked out branch '{branch_to_checkout}': {checkout_output}")
            # Then pull the latest changes
            pull_output = execute_command("git pull")
            logs.append(f"Pulled latest code: {pull_output}")
        else:
            logs.append(f"No custom branch specified for {xapp_name}.")

        # Step 4: check Docker registry
        registry_check = execute_command("docker ps | grep registry")
        logs.append(f"registry_check: {registry_check}")

        if not registry_check:
            start_registry_output = execute_command("docker run -d -p 5000:5000 --restart=always --name registry registry:2")
            logs.append(f"Started docker registry: {start_registry_output}")
        else:
            logs.append("Docker registry is already running.")

        # Step 5: run build.sh
        # os.chdir(xapp_name) # This is already done above

        logs.append(f"Now in xApp folder: {os.getcwd()}")
        
        if not os.path.exists("build.sh"):
            logs.append(f"No build.sh found in {xapp_name}")
            return {"error": f"No build.sh found in {xapp_name} directory", "logs": logs}, 500

        execute_command("chmod +x build.sh")
        build_output = execute_command("./build.sh")
        logs.append(f"build.sh output:\n{build_output}")

        # Step 6: check if build is successful
        logs.append("Build finished successfully.")
        return {"message": "Build finished", "logs": logs}, 200

    except Exception as e:
        # Return any error and the logs collected so far
        return {"error": str(e), "logs": logs}, 500
    finally:
        # Always switch back to the original directory
        os.chdir(original_cwd)

@tool
def build_xapp_tool(xapp_name: str):
    """
    Build the xApp from the given xapp_name.
    Steps:
        step 1: get xapp_name
        step 2: go into xApp dir (if it doesn't exist, create it)
        step 3: git clone the xApp repo
        step 4: run Docker registry
        step 5: cd [xapp_name] and then ./build.sh
        step 6: check if build is successful
    Args:
        xapp_name (str): The name of the xApp to build.
        Please match the user input to nearest valid xApp name listed in the following
        ["MobieXpert xApp", "MobiWatch xApp", "MobiFlow Auditor xApp"]
    Returns:
        dict: A dictionary containing the status of the build process.
    """
    return build_xapp_osc(xapp_name)

def deploy_xapp_osc(xapp_name: str):
    '''
    Deploy the xApp from the given xapp_name.
    '''
    # if simulation mode is enabled, return sample message
    if simulation_mode is True:
        return {"message": f"{xapp_name} is deployed successfully", "logs": []}, 200

    original_cwd = os.getcwd()  # Remember our original directory
    logs = []  # We'll collect log messages in this list

    try:
        # 0) Make sure non-root user can use kubectl
        # kube_config_cmd = (
        #     "sudo swap off -a && "
        #     "sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config && "
        #     "sudo chmod +r $HOME/.kube/config"
        # )
        # kube_config_output = execute_command(kube_config_cmd)
        # logs.append(f"Kubernetes config setup: {kube_config_output or 'done'}")

        helm_check = execute_command("docker ps | grep chartmuseum")
        logs.append(f"helm_check output: {helm_check}")

        # Make sure CHART_REPO_URL is set in Python's process environment (for logging/debugging)
        os.environ["CHART_REPO_URL"] = "http://0.0.0.0:8090"
        logs.append(f"CHART_REPO_URL set to {os.environ['CHART_REPO_URL']}")

        chartmuseum_cmd = (
                "docker run --rm -u 0 -d "
                "-p 8090:8080 "
                "-e DEBUG=1 "
                "-e STORAGE=local "
                "-e STORAGE_LOCAL_ROOTDIR=/charts "
                "-v $(pwd)/charts:/charts "
                "chartmuseum/chartmuseum:latest"
        )
        chartmuseum_output = execute_command(chartmuseum_cmd)
        logs.append(f"ChartMuseum started: {chartmuseum_output}")

        # Set environment variable in this Python process only
        os.environ["CHART_REPO_URL"] = "http://0.0.0.0:8090"
        logs.append(f"CHART_REPO_URL set to {os.environ['CHART_REPO_URL']}")

        if xapp_name in xapp_names:
            xapp_name = xapp_names[xapp_name]
            logs.append(f"[buildXapp] Using {xapp_name} repo for {xapp_name}")
        else:
            logs.append(f"[buildXapp] Using {xapp_name} repo for {xapp_name}")
            return {"error": "Invalid xapp_name"}, 400

        # 3) Verify xApp folder
        xapp_root = get_xapp_root_path()
        xapp_dir = os.path.join(xapp_root, xapp_name)
        if not os.path.exists(xapp_dir):
            return {
                "error": f"xApp folder '{xapp_dir}' does not exist. Please build first.",
                "logs": logs
            }, 400

        # Change directory to xApp
        os.chdir(xapp_dir)

        # 4) Onboard step
        init_dir = os.path.join(xapp_dir, "init")
        if os.path.exists(init_dir):
            onboard_cmd = (
                # "sudo -E env CHART_REPO_URL=http://0.0.0.0:8090 "
                "CHART_REPO_URL=http://0.0.0.0:8090 dms_cli onboard --config_file_path=config-file.json --shcema_file_path=schema.json"
            )
            os.chdir(init_dir)
            onboard_output = execute_command(onboard_cmd)
            logs.append(f"Onboard output: {onboard_output}")
            os.chdir(xapp_dir)
        else:
            logs.append("No 'init' folder found. Skipping onboard step.")

        # 5) Deploy step
        deploy_script = os.path.join(xapp_dir, "deploy.sh")
        if not os.path.exists(deploy_script):
            return {
                "error": f"No deploy.sh found in '{xapp_dir}'",
                "logs": logs
            }, 500

        execute_command("chmod +x deploy.sh")
        deploy_output = execute_command("./deploy.sh")
        logs.append(f"deploy.sh output: {deploy_output}")

        # 6) Check if the xApp is deployed
        check_output = execute_command(f"kubectl get pods -A | grep {xapp_name}")
        if not check_output:
            msg = f"xApp '{xapp_name}' deployed, but no running pod found via 'kubectl get pods'."
            logs.append(msg)
            return {
                "message": msg,
                "logs": logs
            }, 200
        else:
            msg = f"xApp '{xapp_name}' deployment success: {check_output}"
            logs.append(msg)
            return {
                "message": msg,
                "logs": logs
            }, 200

    except Exception as e:
        # If an error occurs, return the error along with any logs we've collected
        return {"error": str(e), "logs": logs}, 500
    finally:
        # Always return to the original directory
        os.chdir(original_cwd)

@tool
def deploy_xapp_tool(xapp_name: str):
    '''
    Deploy the xApp from the given xapp_name.
    Args:
        xapp_name (str): The name of the xApp to build.
        Please match the user input to nearest valid xApp name listed in the following
        ["MobieXpert xApp", "MobiWatch xApp", "MobiFlow Auditor xApp"]
    '''
    return deploy_xapp_osc(xapp_name)

def unDeploy_xapp_osc(xapp_name: str):
    ''' 
    Undeploy the xApp from the given xapp_name.
    Steps:
        step 1: find xapp_name corresponding directory
        step 2: check if xapp is deployed (kubectl get pods -A | grep)
        step 3: run ./undeploy.sh
        step 4: check undeployment is successful or not
    '''
    # if simulation mode is enabled, return sample message
    if simulation_mode is True:
        return {"message": f"{xapp_name} is undeployed successfully", "logs": []}, 200
    
    original_cwd = os.getcwd()
    try:
        if xapp_name in xapp_names:
            xapp_name = xapp_names[xapp_name]
        else:
            return {"error": "Invalid xapp_name"}, 400

        print(f"[unDeployXapp] unDeploy xApp: {xapp_name}")

        # step 1
        xapp_root = get_xapp_root_path()
        xapp_dir = os.path.join(xapp_root, xapp_name)
        if not os.path.exists(xapp_dir):
            return {"error": f"xApp folder {xapp_dir} does not exist."}, 400

        # step 2: check if xapp is deployed
        check_output = execute_command(f"kubectl get pods -A | grep {xapp_name}")
        if not check_output:
            print(f"No running pods found for {xapp_name}. Possibly already undeployed.")
            # we can continue to undeploy.sh，but we can also return a message
            # return {"message": f"No running pods for {xapp_name}. Maybe it's already undeployed."}, 200

        # step 3: ./undeploy.sh
        os.chdir(xapp_dir)
        undeploy_script = os.path.join(xapp_dir, "undeploy.sh")
        if not os.path.exists(undeploy_script):
            return {"error": f"No undeploy.sh found in {xapp_dir}"}, 500

        execute_command("chmod +x undeploy.sh")
        undeploy_output = execute_command("./undeploy.sh")
        print(undeploy_output)

        # step 4: check undeployment is successful or not
        check_output2 = execute_command(f"kubectl get pods -A | grep {xapp_name}")
        if check_output2:
            msg = f"Attempted to undeploy {xapp_name}, but pods may still be present: {check_output2}"
            print(msg)
            return {"message": msg}, 200
        else:
            msg = f"xApp {xapp_name} is successfully undeployed."
            print(msg)
            return {"message": msg}, 200

    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        os.chdir(original_cwd)

@tool
def unDeploy_xapp_tool(xapp_name: str):
    ''' 
    Undeploy the xApp from the given xapp_name.
    Args:
        xapp_name (str): The name of the xApp to build.
        Please match the user input to nearest valid xApp name listed in the following
        ["MobieXpert xApp", "MobiWatch xApp", "MobiFlow Auditor xApp"]
    Steps:
        step 1: find xapp_name corresponding directory
        step 2: check if xapp is deployed (kubectl get pods -A | grep)
        step 3: run ./undeploy.sh
        step 4: check undeployment is successful or not
    '''
    return unDeploy_xapp_osc(xapp_name)

@tool
def get_ue_mobiflow_data_all_tool() -> list:
    '''
    Get all UE MobiFlow telemetry from SDL. UE MobiFlow telemetry records UE meta data, identifiers, connection status, RRC/NAS security algorithms, and RRC/NAS messages.
    Before analyzing the MobiFlow telemetry, ensure you have called get_ue_mobiflow_description_tool() to obtain the semantics associated with the data for better understanding.
    Returns:
        list: a list of UE MobiFlow telemetry in raw format (separated by ; delimiter)
    '''
    keys = []
    # if simulation mode is enabled, grab the data keys from the sample data file
    if simulation_mode is True:
        with open(get_sample_data_path("5G-Sample-Data - UE.csv"), "r") as file:
            for line in file.readlines():
                index = int(line.split(";")[1])
                keys.append(index)
    else:
        # get all keys for ue_mobiflow namespace in the actual SDL
        namespace = sdl_namespaces[0]
        get_key_command = f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get keys {namespace}'
        keys_output = execute_command(get_key_command)

        # Parse keys (split by newlines)
        keys = [int(key.strip()) for key in keys_output.split("\n") if key.strip()]
    
    keys = sorted(keys)
    return get_ue_mobiflow_data_by_index(keys)

@tool
def get_ue_mobiflow_data_by_index_tool(index_list_str: str) -> list:
    '''
    Get UE MobiFlow telemetry from SDL using a specified index list. UE MobiFlow telemetry records UE meta data, identifiers, and RRC/NAS security algorithms, as well as RRC/NAS messages.
    Before analyzing the MobiFlow telemetry, ensure you have called get_ue_mobiflow_description_tool() to obtain the semantics associated with the data for better understanding.
    Args:
        index_list_str (str): a string containing the MobiFlow indexes separated by comma, e.g., 1,2,3,4,5,6
    Returns:
        list: a list of UE MobiFlow telemetry in raw format (separated by ; delimiter) 
    '''
    if index_list_str is None or len(index_list_str) == 0:
        return []
    index_list = []
    for i in index_list_str.split(","):
        index_list.append(int(i))
    return get_ue_mobiflow_data_by_index(index_list)

def get_ue_mobiflow_data_by_index(index_list: list) -> list:
    '''
    Get UE MobiFlow telemetry from SDL using a specified index list
    Args:
        index_list (list): a list of MobiFlow indexes (integers)
    Returns:
        list: a list of UE MobiFlow telemetry in raw format (separated by ; delimiter) 
    '''
    if index_list is None or len(index_list) == 0:
        return []

    # if simulation mode is enabled, read from the sample data file
    if simulation_mode is True:
        mf_list = []
        with open(get_sample_data_path("5G-Sample-Data - UE.csv"), "r") as file:
            for line in file.readlines():
                index = int(line.split(";")[1])
                if index in index_list:
                    mf_list.append(line)
        return mf_list

    max_batch_get_value = 20  # max number of keys to fetch in a single batch
    get_val_command = lambda ns, key: f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get {ns} {key}'  # template get value command

    # get all UE mobiflow
    mf_data = {}
    ue_mobiflow_key = sdl_namespaces[0]
    for i in range(0, len(index_list), max_batch_get_value):
        # Create a batch of keys
        batch_keys = [str(index_list[j]) for j in range(i, min(i + max_batch_get_value, len(index_list)))]

        # Create the command for the batch
        command = get_val_command(ue_mobiflow_key, " ".join(batch_keys))
        value = execute_command(command)

        # Process each value in the batch
        for line in [val.strip() for val in value.split("\n") if val.strip()]:
            k = int(line.split(":")[0])
            v = line.split(":")[1]
            start_index = v.index("UE;")
            mf_data[k] = v[start_index:] # remove prefix
        mf_data = dict(sorted(mf_data.items())) # sort values based on Index

    return list(mf_data.values())

@tool
def get_bs_mobiflow_data_all_tool() -> list:
    '''
    Get all Base Station (BS) MobiFlow telemetry from SDL. BS MobiFlow telemetry records Base Station / gNodeB / Cell meta data such as cell ID, state, MCC, MNC, etc.
    Before analyzing the MobiFlow telemetry, ensure you have called get_bs_mobiflow_description_tool() to obtain the semantics associated with the data for better understanding.
    Returns:
        list: a list of BS MobiFlow telemetry in raw format (separated by ; delimiter)
    '''
    keys = []
    # if simulation mode is enabled, grab the data keys from the sample data file
    if simulation_mode is True:
        with open(get_sample_data_path("5G-Sample-Data - BS.csv"), "r") as file:
            for line in file.readlines():
                index = int(line.split(";")[1])
                keys.append(index)
    else:
        # get all keys for bs_mobiflow namespace in the actual SDL
        namespace = sdl_namespaces[1]
        get_key_command = f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get keys {namespace}'
        keys_output = execute_command(get_key_command)

        # Parse keys (split by newlines)
        keys = [int(key.strip()) for key in keys_output.split("\n") if key.strip()]
        
    keys = sorted(keys)
    return get_bs_mobiflow_data_by_index(keys)

@tool
def get_bs_mobiflow_data_by_index_tool(index_list_str: str) -> list:
    '''
    Get Base Station (BS) MobiFlow telemetry from SDL using a specified index list. BS MobiFlow telemetry records Base Station / gNodeB / Cell meta data such as cell ID, MCC, MNC, etc.
    Before analyzing the MobiFlow telemetry, ensure you have called get_bs_mobiflow_description_tool() to obtain the semantics associated with the data for better understanding.
    Args:
        index_list_str (str): a string containing the MobiFlow indexes separated by comma, e.g., 1,2,3,4,5,6
    Returns:
        list: a list of UE MobiFlow telemetry in raw format (separated by ; delimiter) 
    '''
    if index_list_str is None or len(index_list_str) == 0:
        return []
    index_list = []
    for i in index_list_str.split(","):
        index_list.append(int(i))
    return get_bs_mobiflow_data_by_index(index_list)

def get_bs_mobiflow_data_by_index(index_list: list) -> list:
    '''
    Get BS MobiFlow telemetry from SDL using a specified index list
    Args:
        index_list (list): a list of MobiFlow indexes (integers)
    Returns:
        list: a list of BS MobiFlow telemetry in raw format (separated by ; delimiter) 
    '''
    if index_list is None or len(index_list) == 0:
        return []
    
    # if simulation mode is enabled, read from the sample data file
    if simulation_mode is True:
        mf_list = []
        with open(get_sample_data_path("5G-Sample-Data - BS.csv"), "r") as file:
            for line in file.readlines():
                index = int(line.split(";")[1])
                if index in index_list:
                    mf_list.append(line)
        return mf_list

    max_batch_get_value = 20  # max number of keys to fetch in a single batch
    get_val_command = lambda ns, key: f'kubectl exec -it statefulset-ricplt-dbaas-server-0 -n ricplt -- sdlcli get {ns} {key}'  # template get value command

    # get all BS mobiflow
    mf_data = {}
    bs_mobiflow_key = sdl_namespaces[1]
    for i in range(0, len(index_list), max_batch_get_value):
        # Create a batch of keys
        batch_keys = [str(index_list[j]) for j in range(i, min(i + max_batch_get_value, len(index_list)))]

        # Create the command for the batch
        command = get_val_command(bs_mobiflow_key, " ".join(batch_keys))
        value = execute_command(command)

        # Process each value in the batch
        for line in [val.strip() for val in value.split("\n") if val.strip()]:
            k = int(line.split(":")[0])
            v = line.split(":")[1]
            start_index = v.index("BS;")
            mf_data[k] = v[start_index:] # remove prefix
        mf_data = dict(sorted(mf_data.items())) # sort values based on Index

    return list(mf_data.values())

@tool
def get_ue_mobiflow_description_tool() -> str:
    '''
    API to retreve the description of UE MobiFlow data fields. Each field is defined with its default value, description, and value range if applicable.
    '''
    return '''
    msg_type = "UE"                        # Msg hdr  - mobiflow type [UE, BS]
    msg_id = 0                             # Msg hdr  - unique mobiflow event ID
    mobiflow_ver = MOBIFLOW_VERSION        # Msg hdr  - version of Mobiflow
    generator_name = GENERATOR_NAME        # Msg hdr  - generator name (e.g., SECSM)
    #####################################################################
    timestamp = 0              # UE meta  - timestamp (ms)
    nr_cell_id = 0             # UE meta  - NR (5G) basestation id
    gnb_cu_ue_f1ap_id = 0      # UE meta  - UE id identified by gNB CU F1AP
    gnb_du_ue_f1ap_id = 0      # UE meta  - UE id identified by gNB DU F1AP
    rnti = 0                   # UE meta  - ue rnti
    s_tmsi = 0                 # UE meta  - ue s-tmsi
    mobile_id = 0              # UE meta  - mobile device id (e.g., SUPI, SUCI, IMEI)
    rrc_cipher_alg = 0         # UE packet telemetry  - rrc cipher algorithm
    rrc_integrity_alg = 0      # UE packet telemetry  - rrc integrity algorithm
    nas_cipher_alg = 0         # UE packet telemetry  - nas cipher algorithm
    nas_integrity_alg = 0      # UE packet telemetry  - nas integrity algorithm
    #####################################################################
    rrc_msg = ""               # UE packet-agnostic telemetry  - RRC message
    nas_msg = ""               # UE packet-agnostic telemetry  - NAS message (an empty nas_msg could indicate an encrypted NAS message since MobiFlow cannot decode encrypted NAS messages)
    rrc_state = 0              # UE packet-agnostic telemetry  - RRC state       [INACTIVE, RRC_IDLE, RRC_CONNECTED, RRC_RECONFIGURED]
    nas_state = 0              # UE packet-agnostic telemetry  - NAS state (EMM) [EMM_DEREGISTERED, EMM_REGISTER_INIT, EMM_REGISTERED]
    rrc_sec_state = 0          # UE packet-agnostic telemetry  - security state  [SEC_CONTEXT_NOT_EXIST, SEC_CONTEXT_EXIST]
    #####################################################################
    reserved_field_1 = 0       # UE packet-specific telemetry
    reserved_field_2 = 0       # UE packet-specific telemetry
    reserved_field_3 = 0       # UE packet-specific telemetry
    '''

@tool
def get_bs_mobiflow_description_tool() -> str:
    '''
    API to retreve the description of BS MobiFlow data fields. Each field is defined with its default value, description, and value range if applicable.
    '''
    return '''
    msg_type = "BS"            # Msg hdr  - mobiflow type [UE, BS]
    msg_id = 0                 # Msg hdr  - unique mobiflow event ID
    timestamp = get_time_sec()             # Msg hdr  - timestamp (s)
    mobiflow_ver = MOBIFLOW_VERSION        # Msg hdr  - version of Mobiflow
    generator_name = GENERATOR_NAME        # Msg hdr  - generator name (e.g., SECSM)
    ################################################################
    nr_cell_id = 0             # BS meta  - basestation id
    mcc = ""                   # BS meta  - mobile country code
    mnc = ""                   # BS meta  - mobile network code
    tac = ""                   # BS meta  - tracking area code
    report_period = 0          # BS meta  - report period (ms)
    status = 0                 # BS meta  - status (1: connected, 2: disconnected)
    '''

@tool
def get_event_description_tool() -> str:
    '''
    API to retreve the description of event data fields
    '''
    return '''
        Each event consists of the following fields with their descriptions:
        id: Unique ID of the event,
        source: The source that generates the event, i.e., the xApp name, 
        name: The name describing the event,
        cellID: The involved base station ID in this event,
        ueID: The involved user equipment's (UE) ID in this event,
        timestamp: The event timestamp,
        severity: The severity of event,
        mobiflow_index (if available): the MobiFlow telemetry index associated with the event, matching the msg_id field in each MobiFlow telemetry,
        description: The event description
    '''
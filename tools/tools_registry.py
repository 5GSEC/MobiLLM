from .sdl_apis import *
from .mitre_apis import *
from .control_apis import *


def mobillm_chat_tools():
    return [
            # get_ue_mobiflow_data_all_tool,
            fetch_sdl_data_osc_tool,
            get_ue_mobiflow_data_by_index_tool,
            get_ue_mobiflow_description_tool,
            get_ue_mobiflow_data_all_tool,
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

def mobillm_security_analysis_tools():
    return [
            # get_ue_mobiflow_data_all_tool,
            get_ue_mobiflow_data_by_index_tool,
            get_ue_mobiflow_data_by_ue_id_tool,
            get_ue_mobiflow_description_tool,
            get_bs_mobiflow_data_all_tool,
            get_bs_mobiflow_data_by_index_tool,
            get_bs_mobiflow_description_tool,
            fetch_sdl_event_data_all_tool,
            fetch_sdl_event_data_by_ue_id_tool,
            fetch_sdl_event_data_by_cell_id_tool,
            get_event_description_tool,
        ]

def mobillm_security_classification_tools():
    return [
            get_all_mitre_fight_techniques,
            get_mitre_fight_technique_by_id,
            search_mitre_fight_techniques,
        ]

def mobillm_security_response_tools():
    return [
            get_all_mitre_fight_techniques,
            get_mitre_fight_technique_by_id,
            get_ran_cu_config_tool,
            update_ran_cu_config_tool,
            reboot_ran_cu_tool,
        ]

def mobillm_config_tuning_tools():
    return [
            get_all_mitre_fight_techniques,
            get_mitre_fight_technique_by_id,
            get_ran_cu_config_tool,
            update_ran_cu_config_tool,
            reboot_ran_cu_tool,
        ]
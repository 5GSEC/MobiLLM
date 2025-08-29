from .baseagent import BaseAgent
from ..state import MobiLLMState
from ..tools.mitre_apis import *

class SecurityClassificationAgent(BaseAgent):
    def run(self, state: MobiLLMState) -> MobiLLMState:
        threat_summary = state["threat_summary"]
        if not threat_summary or threat_summary.strip() == "":
            return state
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
        
        # TODO possibly have a utils.compact_mitre here
        
        return state
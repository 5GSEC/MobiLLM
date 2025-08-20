import os
import csv
import yaml # pip install pyyaml
import json

# Tatics Techniques - SubTechniques

mitre_fight_root = "./FiGHT"  # Change this to your local path of the mitre-fight repository

# parse tactics
fight_tactics = []
# tactic_csv = os.path.join(mitre_fight_root, "fight-data/data/tactics.yaml")
# with open(tactic_csv) as stream:
#     try:
#         fight_tactics = yaml.safe_load(stream)
#     except yaml.YAMLError as exc:
#         print(exc)

# for tactics in fight_tactics:
#     print(tactics['name'])

tactic_csv = os.path.join(mitre_fight_root, "fight-data/threat_models/CSV/FiGHT_Tactics_for_human_edits.csv")
with open(tactic_csv, newline='') as csvfile:
    fight_tactics = csv.reader(csvfile, delimiter=',', quotechar='"')
    # for row in fight_tactics:
        # print(', '.join(row))


def technique_prefix_normalize(tech_id):
    """
    Normalize the technique ID prefix to a standard format. TODO: does it make sense? 
    sometimes MiTRE FIGHT will use FGTXXX and TXXX interchangebly, so add both to the index list for searching...
    """
    if tech_id.startswith("T"):
        return tech_id.replace("T", "FGT")
    else:
        return tech_id

# parse techniques
fight_techniques = {}
technique_ids = []
for d in os.listdir(os.path.join(mitre_fight_root, "techniques")):
    if d.startswith("index.html"):
        continue
    tech_id = technique_prefix_normalize(d.strip())
    technique_ids.append(tech_id)        
    fight_techniques[tech_id] = {}


# parse metadata
metadata_csv_file = os.path.join(mitre_fight_root, "fight-data/threat_models/CSV/FIGHT_releases.csv")
with open(metadata_csv_file, newline='') as csvfile:
    fight_metadata = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_metadata:
        # print(row)
        # TempID,Domain,Platform/Architecture,Tactics,New FGTID,Technique Name,BLUF
        TempID = row[0].strip()
        domain = row[1].strip()
        platform = row[2].strip()
        tactics = row[3].strip()
        tech_id = technique_prefix_normalize(row[4].strip())
        technique_name = row[5].strip()
        technique_desc = row[6].strip()
        if tech_id in technique_ids:
            if "Name" not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id]["Name"] = technique_name # init technique name
            if "Description" not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id]["Description"] = technique_desc # init technique description
            if "Platform" not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id]["Platform"] = platform
            if "Tactics" not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id]["Tactics"] = tactics
    
# build technique - subtechniques hierarchy
for tech_id in fight_techniques.keys():
    if tech_id.__contains__("."):
        # is subtechnique
        parent_tech_id = tech_id.split(".")[0]
        if parent_tech_id in technique_ids:
            if fight_techniques[parent_tech_id] != {}:
                fight_techniques[tech_id]["Parent"] = parent_tech_id
                fight_techniques[tech_id]["Name"] = f"{fight_techniques[parent_tech_id]['Name']}: {fight_techniques[tech_id]['Name']}"
            else:
                print(f"Warning: Parent technique {parent_tech_id} not found for subtechnique {tech_id}")
        else:
            print(f"Warning: Parent technique {parent_tech_id} not found for subtechnique {tech_id}")

# parse detection
detection_csv_file = os.path.join(mitre_fight_root, "fight_matrix/Detection.csv")
fight_detections = []
key_name = "Detection"
with open(detection_csv_file, newline='') as csvfile:
    fight_detections = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_detections:
        # print(row)
        tech_id = technique_prefix_normalize(row[0].strip())
        detection_id = row[2].strip()
        detection_desc = row[3].strip()
        if tech_id in technique_ids:
            if key_name not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id][key_name] = []
            fight_techniques[tech_id][key_name].append({
                'id': detection_id,
                'description': detection_desc
            })


# parse pre-Conditions
pre_conditions_csv_file = os.path.join(mitre_fight_root, "fight_matrix/Pre-Conditions.csv")
fight_pre_conditions = []
key_name = "Pre-Conditions"
with open(pre_conditions_csv_file, newline='') as csvfile:
    # Read the CSV file
    fight_pre_conditions = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_pre_conditions:
        # print(row)
        tech_id = technique_prefix_normalize(row[0].strip())
        pre_condition_name = row[2].strip()
        pre_condition_desc = row[3].strip()
        if tech_id in technique_ids:    
            if key_name not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id][key_name] = []
            fight_techniques[tech_id][key_name].append({
                'name': pre_condition_name,
                'description': pre_condition_desc
            })

# parse Post_Conditons
post_conditions_csv_file = os.path.join(mitre_fight_root, "fight_matrix/Post-Conditions.csv")
fight_post_conditions = []
key_name = "Post-Conditions"
with open(post_conditions_csv_file, newline='') as csvfile:
    # Read the CSV file
    fight_post_conditions = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_post_conditions:
        # print(row)
        tech_id = technique_prefix_normalize(row[0].strip())
        post_condition_name = row[2].strip()
        post_condition_desc = row[3].strip()
        if tech_id in technique_ids:    
            if key_name not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id][key_name] = []
            fight_techniques[tech_id][key_name].append({
                'name': post_condition_name,
                'description': post_condition_desc
            })

# parse procedure examples
procedure_examples_csv_file = os.path.join(mitre_fight_root, "fight_matrix/Procedure Examples.csv")
fight_procedure_examples = []
key_name = "Procedure Examples"
with open(procedure_examples_csv_file, newline='') as csvfile:
    # Read the CSV file
    fight_procedure_examples = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_procedure_examples:
        # print(row)
        tech_id = technique_prefix_normalize(row[0].strip())
        procedure_example_name = row[2].strip()
        procedure_example_desc = row[3].strip()
        if tech_id in technique_ids:    
            if key_name not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id][key_name] = []
            fight_techniques[tech_id][key_name].append({
                'name': procedure_example_name,
                'description': procedure_example_desc
            })

# parse critical assets
critical_assets_csv_file = os.path.join(mitre_fight_root, "fight_matrix/Critical Assets.csv")
fight_critical_assets = []
key_name = "Critical Assets"
with open(critical_assets_csv_file, newline='') as csvfile:
    # Read the CSV file
    fight_critical_assets = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_critical_assets:
        # print(row)
        tech_id = technique_prefix_normalize(row[0].strip())
        critical_asset_name = row[2].strip()
        critical_asset_desc = row[3].strip()
        if tech_id in technique_ids:    
            if key_name not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id][key_name] = []
            fight_techniques[tech_id][key_name].append({
                'name': critical_asset_name,
                'description': critical_asset_desc
            })

# parse references
references_csv_file = os.path.join(mitre_fight_root, "fight_matrix/References.csv")
fight_references = []
key_name = "References"
with open(references_csv_file, newline='') as csvfile:
    # Read the CSV file
    fight_references = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_references:
        # print(row)
        tech_id = technique_prefix_normalize(row[0].strip())
        reference_name = row[2].strip()
        reference_link = row[3].strip()
        if tech_id in technique_ids:    
            if key_name not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id][key_name] = []
            fight_techniques[tech_id][key_name].append({
                'name': reference_name,
                'description': reference_link
            })

# parse mitigations
mitigations_csv_file = os.path.join(mitre_fight_root, "fight_matrix/Mitigations.csv")
fight_mitigations = []
key_name = "Mitigations"
with open(mitigations_csv_file, newline='') as csvfile:
    # Read the CSV file
    fight_mitigations = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in fight_mitigations:
        tech_id = technique_prefix_normalize(row[0].strip())
        mitigation_id = row[2].strip()
        mitigation_desc = row[3].strip()
        if tech_id in technique_ids:    
            if key_name not in fight_techniques[tech_id].keys():
                fight_techniques[tech_id][key_name] = []
            fight_techniques[tech_id][key_name].append({
                'name': mitigation_id,
                'description': mitigation_desc
            })

out_file_name = "mitre_fight_techniques.json"
with open(out_file_name, 'w') as outfile:
    json.dump(fight_techniques, outfile, indent=4)
print(f"Output written to {out_file_name}")
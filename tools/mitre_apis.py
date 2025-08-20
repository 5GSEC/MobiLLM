import os
import json
import faiss # faiss-cpu
import numpy as np
from langchain.tools import tool
from sentence_transformers import SentenceTransformer # sentence_transformers
from .. import global_vars

@tool
def get_all_mitre_fight_techniques(fight_json_path: str=None) -> dict:
    ''' 
    This function will read all the MiTRE Fight techniques from a local json file that is created from the official MiTRE Fight Git Repo (https://github.com/mitre/FiGHT/)
    Input:
    - fight_json_path (str) - the path to the MiTRE Fight techniques JSON file. If None, will use the default file in the same directory as this script.
    Returns:
        dict: A dictionary containing all the MiTRE Fight techniques. Each dict object is a specific technique encoded as (key, value) pairs. Each technique will contain fields like Name, Descriptions, and Mitigations.
    '''
    if fight_json_path is None:
        fight_json_path = os.path.join(os.path.dirname(__file__), "mitre_fight_techniques-3.0.1.json")
    
    with open(fight_json_path, 'r') as f:
        techniques = json.load(f)

    return techniques


@tool
def get_mitre_fight_technique_by_id(tech_id: str, fight_json_path: str=None) -> dict:
    '''
    This function will read a specific MiTRE Fight technique's descriptions. A speficied technique ID needs to be provided.
    Input: 
    - tech_id (str) - the ID of a MiTRE Fight technique (e.g., "FGT1199.501")
    - fight_json_path (str) - the path to the MiTRE Fight techniques JSON file. If None, will use the default file in the same directory as this script.
    Returns:
        dict: A dictionary containing the specified MiTRE Fight technique. Each dict object is a specific technique encoded as (key, value) pairs. Each technique will contain fields like Name, Descriptions, and Mitigations. If the technique ID is not found, an empty dict will be returned.
    '''
    if tech_id == None or len(tech_id) == 0:
        return {}
    
    if fight_json_path is None:
        fight_json_path = os.path.join(os.path.dirname(__file__), "mitre_fight_techniques-3.0.1.json")
    
    tech = {}
    with open(fight_json_path, 'r') as f:
        techniques = json.load(f)
        if tech_id in techniques.keys():
            tech = techniques[tech_id]

    return tech


@tool
def search_mitre_fight_techniques(threat_summary: str, top_k: int=5, fight_json_path: str=None, embedding_model_name="all-MiniLM-L6-v2") -> list:
    '''
    This function will perform a similarity search through the MiTRE FiGHT technique descriptions to find the top most relevant MiTRE FiGHT technique associated with the given event. The search is performed via FAISS (Facebook AI Similarity Search) using sentence embeddings.
    Input:
    - threat summary (str): A summary report of the threat event
    - top_k (int): Top K most relevant MiTRE FiGHT technique to retrieve (default value: 5)
    - fight_json_path (str) - the path to the MiTRE Fight techniques JSON file. If None, will use the default file in the same directory as this script.
    - embedding_model_name (str): The name of the sentence embedding model to use (default value: "all-MiniLM-L6-v2")
    Returns:
        list: A list of most relevant MiTRE Fight technique IDs based on the top_k argument
    '''
    if fight_json_path is None:
        fight_json_path = os.path.join(os.path.dirname(__file__), "mitre_fight_techniques-3.0.1.json")
    
    embedding_model = SentenceTransformer(embedding_model_name)

    query_embedding = embedding_model.encode([threat_summary], convert_to_tensor=False)
    query_embedding_faiss = np.array(query_embedding, dtype='float32')
    faiss.normalize_L2(query_embedding_faiss)

    if global_vars.mitre_faiss_db is not None:
        # if the db has been loaded from global variable, use it directly
        index = global_vars.mitre_faiss_db
    else:
        # load the db from file
        index = load_or_create_mitre_fight_faiss_index(fight_json_file_name=fight_json_path)

    if index is None:
        print("Error: FAISS index could not be loaded or created. Please check the data file.")
        return []
    distances, indices = index.search(query_embedding_faiss, top_k)

    structured_techniques_data = load_and_process_fight_data(fight_json_path)

    # print(f"\nTop {top_k} most similar techniques found:")
    retrieved_tech_list = []
    for i in range(top_k):
        retrieved_index = indices[0][i]
        distance = distances[0][i]
        cosine_similarity = (2 - distance**2) / 2 # For L2 normalized vectors

        # Retrieve the structured data for this technique
        retrieved_technique_data = structured_techniques_data[retrieved_index]
        technique_id = retrieved_technique_data['id']
        retrieved_tech_list.append(technique_id)
        
        # print(f"\nRank {i+1}:")
        # print(f"  Technique ID: {retrieved_technique_data['id']}")
        # print(f"  Name: {retrieved_technique_data['original_object'].get('Name', 'N/A')}")
        # print(f"  L2 Distance: {distance:.4f}")
        # print(f"  Cosine Similarity: {cosine_similarity:.4f}")
        # print(f"  Text Embedded (first 200 chars): '{retrieved_technique_data['text_for_embedding'][:200]}...'") # For debugging
        # print(f"  Retrieved Full Object:")
        # print(json.dumps(retrieved_technique_data['original_object'], indent=2))

    return retrieved_tech_list

def load_and_process_fight_data(json_filepath):
    """
    Loads MITRE FiGHT techniques from a JSON file.
    Extracts relevant text for embedding (Name, Description, Tactics, Procedure Examples) 
    and keeps the original object.
    """
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            fight_data_raw = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {json_filepath} was not found.")
        print("Please ensure 'mitre_fight_techniques-3.0.1.json' exists in the same directory or provide the correct path.")
        # Create a dummy file for demonstration if not found
        return None

    processed_techniques = []
    # Assuming your JSON is a dictionary where keys are IDs and values are technique objects
    for tech_id, tech_obj in fight_data_raw.items():
        name = tech_obj.get("Name", "")
        description = tech_obj.get("Description", "")
        
        tactics_data = tech_obj.get("Tactics", "")
        # Tactics can be a string or a list of strings. Ensure it's a single string.
        if isinstance(tactics_data, list):
            tactics = ", ".join(tactics_data)
        else:
            tactics = tactics_data if tactics_data else ""

        procedure_examples_list = tech_obj.get("Procedure Examples", [])
        procedures_text_parts = []
        if isinstance(procedure_examples_list, list):
            for proc in procedure_examples_list:
                proc_name = proc.get("name", "")
                proc_desc = proc.get("description", "")
                if proc_name or proc_desc: # Only add if there's some content
                    procedures_text_parts.append(f"{proc_name}: {proc_desc}")
        procedures_text = " ".join(procedures_text_parts)
        
        # Concatenate relevant fields for embedding.
        # This is a crucial step for retrieval quality.
        text_to_embed = f"Name: {name}. Description: {description}. Tactics: {tactics}. Procedure Examples: {procedures_text}"
        
        # Clean up extra whitespace that might result from empty fields
        text_to_embed = " ".join(text_to_embed.split())


        if not text_to_embed.strip() or text_to_embed == "Name: . Description: . Tactics: . Procedure Examples:":
            # print(f"Warning: Technique {tech_id} has minimal or no extracted content for embedding. Using fallback.")
            # Fallback to embedding the whole object string if critical fields are missing or empty
            text_to_embed = json.dumps(tech_obj)


        processed_techniques.append({
            "id": tech_id,
            "text_for_embedding": text_to_embed,
            "original_object": tech_obj # Store the full original object
        })
    return processed_techniques

def load_or_create_mitre_fight_faiss_index(fight_json_file_name: str=None, fight_db_name: str=None, embedding_model_name="all-MiniLM-L6-v2"):
    """
    Load or create a FAISS index for MITRE FiGHT techniques.
    """
    if fight_json_file_name is None:
        fight_json_file_name = "mitre_fight_techniques-3.0.1.json"
    if fight_db_name is None:
        fight_db_name = "mitre_fight.faiss_index"
    
    fight_db_path = os.path.join(os.path.dirname(__file__), fight_db_name)
    if os.path.exists(fight_db_path):
        print("Loading existing FAISS index from file...")
        index = faiss.read_index(fight_db_path)
        return index

    # --- Specify the path to your JSON file ---
    fight_json_file_path = os.path.join(os.path.dirname(__file__), fight_json_file_name)
    structured_techniques_data = load_and_process_fight_data(fight_json_file_path)

    if not structured_techniques_data:
        print("No techniques loaded. Exiting.")
        return None

    # Extract the texts that will actually be embedded
    corpus_for_embedding = [item['text_for_embedding'] for item in structured_techniques_data]

    print(f"Loaded and processed {len(structured_techniques_data)} techniques.")
    if corpus_for_embedding:
        print(f"Sample text for embedding (first processed technique): '{corpus_for_embedding[0]}'")


    # 2. Initialize a sentence embedding model
    embedding_model = SentenceTransformer(embedding_model_name)

    # 3. Embed the corpus
    print("Embedding techniques... This might take a while depending on the corpus size.")
    corpus_embeddings = embedding_model.encode(corpus_for_embedding, convert_to_tensor=False, show_progress_bar=True)
    print(f"Embeddings generated with shape: {corpus_embeddings.shape}")

    # 4. Construct FAISS Vector DB
    corpus_embeddings_faiss = np.array(corpus_embeddings, dtype='float32')
    embedding_dimension = corpus_embeddings_faiss.shape[1]

    faiss.normalize_L2(corpus_embeddings_faiss) # Normalize for cosine similarity
    index = faiss.IndexFlatL2(embedding_dimension)
    index.add(corpus_embeddings_faiss)

    print(f"FAISS index built successfully with {index.ntotal} vectors (Dimension: {index.d}).")

    faiss.write_index(index, fight_db_name)
    return index


# test_query = '''
# **(1) Short Summary of the Event**
# A critical security event was detected by MobieXpert in Cell ID 20000 involving UE ID 54649. The event, named "RRC Null Cipher", indicates that the User Equipment (UE) is operating its Radio Resource Control (RRC) session without encryption (using null cipher mode).

# **(2) Root Cause Analysis**
# The root cause of this event is the failure to successfully negotiate and apply RRC integrity protection and ciphering algorithms during the RRC connection establishment phase between the UE and the gNB. This failure results in the RRC connection falling back to using the null ciphering algorithm, which provides no confidentiality for the RRC signaling messages. Potential reasons for this failure could include misconfiguration on the network side (gNB or core network), issues with the UE's security capabilities or implementation, or potentially an attempt to force a less secure connection.

# **(3) Security Implication**
# The primary security implication of using null cipher mode for the RRC session is the complete lack of confidentiality for RRC signaling traffic. All RRC messages exchanged between the UE and the network are transmitted in plaintext. This makes the communication vulnerable to passive sniffing attacks, where an attacker can intercept and read sensitive information contained within the RRC messages. Such information could include details about the UE's identity (if not properly protected at higher layers), its capabilities, network configuration details, and control plane procedures, potentially enabling further attacks or reconnaissance against the user or the network.
# '''

# res = search_mitre_fight_techniques.invoke({"threat_summary": test_query, "top_k": 5})
# print(res)

load_or_create_mitre_fight_faiss_index()
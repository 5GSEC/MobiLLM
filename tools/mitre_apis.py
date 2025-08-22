import os
import json
from pathlib import Path
import faiss
import numpy as np
from langchain.tools import tool
from sentence_transformers import SentenceTransformer 
from importlib.resources import files as pkg_files
from typing import List, Dict, Any, Optional

from .global_vars import * 

# ---------- assets path resolution helpers ----------

def _assets_dir() -> Path:
    return (pkg_files("MobiLLM") / "assets")

def _resolve_path(maybe_path: str, default_name: Optional[str] = None) -> Path:
    """
    Resolve a path:
      - absolute path: returned as-is (must exist)
      - path relative to CWD: if exists, use it
      - bare filename: resolved under package assets dir
    """
    p = Path(maybe_path)
    if p.is_absolute() and p.exists():
        return p

    # try relative to CWD
    if p.exists():
        return p.resolve()

    # fall back to package assets
    base = _assets_dir()
    if default_name is not None and maybe_path.strip() == "":
        # empty string: use default name under assets
        p = base / default_name
    else:
        # given string: interpret under assets
        p = base / maybe_path
    return p.resolve()

# ---------- tools ----------

@tool
def get_all_mitre_fight_techniques(
    fight_json_path: str = "mitre_fight_techniques.json"
) -> dict:
    """
    Read all MITRE FiGHT techniques from JSON. Defaults to package asset.
    """
    json_path = _resolve_path(fight_json_path, default_name="mitre_fight_techniques.json")
    if not json_path.exists():
        raise FileNotFoundError(f"Could not find techniques JSON at: {json_path}")
    with json_path.open("r", encoding="utf-8") as f:
        techniques = json.load(f)
    return techniques


@tool
def get_mitre_fight_technique_by_id(
    tech_id: str,
    fight_json_path: str = "mitre_fight_techniques.json"
) -> dict:
    """
    Read a specific MITRE FiGHT technique by ID.
    """
    if not tech_id:
        return {}
    json_path = _resolve_path(fight_json_path, default_name="mitre_fight_techniques.json")
    if not json_path.exists():
        raise FileNotFoundError(f"Could not find techniques JSON at: {json_path}")

    with json_path.open("r", encoding="utf-8") as f:
        techniques = json.load(f)
    return techniques.get(tech_id, {})


@tool
def search_mitre_fight_techniques(
    threat_summary: str,
    top_k: int = 5,
    fight_json_path: str = "mitre_fight_techniques.json",
    embedding_model_name: str = "all-MiniLM-L6-v2",
) -> list:
    """
    Similarity search through MITRE FiGHT technique descriptions via FAISS.
    """
    if not threat_summary or not threat_summary.strip():
        return []

    embedding_model = SentenceTransformer(embedding_model_name)
    query_embedding = embedding_model.encode([threat_summary], convert_to_tensor=False)
    query_embedding_faiss = np.array(query_embedding, dtype="float32")
    faiss.normalize_L2(query_embedding_faiss)

    if mitre_faiss_db is not None:
        index = mitre_faiss_db
    else:
        index = load_or_create_mitre_fight_faiss_index(
            fight_json_path=fight_json_path,
            embedding_model_name=embedding_model_name
        )

    if index is None:
        print("Error: FAISS index could not be loaded or created. Please check the data file.")
        return []

    distances, indices = index.search(query_embedding_faiss, top_k)

    structured_techniques_data = load_and_process_fight_data(fight_json_path)
    if not structured_techniques_data:
        return []

    retrieved_tech_list = []
    for i in range(min(top_k, indices.shape[1])):
        retrieved_index = indices[0][i]
        # distance = distances[0][i]  # available if you want similarity scores
        technique_id = structured_techniques_data[retrieved_index]["id"]
        retrieved_tech_list.append(technique_id)

    return retrieved_tech_list


# ---------- core helpers ----------

def load_and_process_fight_data(json_filepath: str | Path):
    """
    Loads MITRE FiGHT techniques from a JSON file and prepares text for embedding.
    """
    json_path = _resolve_path(str(json_filepath), default_name="mitre_fight_techniques.json")
    if not json_path.exists():
        print(f"Error: The file {json_path} was not found.")
        return None

    with json_path.open("r", encoding="utf-8") as f:
        fight_data_raw = json.load(f)

    processed_techniques = []
    for tech_id, tech_obj in fight_data_raw.items():
        name = tech_obj.get("Name", "")
        description = tech_obj.get("Description", "")

        tactics_data = tech_obj.get("Tactics", "")
        tactics = ", ".join(tactics_data) if isinstance(tactics_data, list) else (tactics_data or "")

        procedure_examples_list = tech_obj.get("Procedure Examples", [])
        procedures_text_parts = []
        if isinstance(procedure_examples_list, list):
            for proc in procedure_examples_list:
                proc_name = proc.get("name", "")
                proc_desc = proc.get("description", "")
                if proc_name or proc_desc:
                    procedures_text_parts.append(f"{proc_name}: {proc_desc}")
        procedures_text = " ".join(procedures_text_parts)

        text_to_embed = (
            f"Name: {name}. Description: {description}. "
            f"Tactics: {tactics}. Procedure Examples: {procedures_text}"
        )
        text_to_embed = " ".join(text_to_embed.split())

        if not text_to_embed.strip() or text_to_embed == "Name: . Description: . Tactics: . Procedure Examples:":
            text_to_embed = json.dumps(tech_obj)

        processed_techniques.append(
            {
                "id": tech_id,
                "text_for_embedding": text_to_embed,
                "original_object": tech_obj,
            }
        )
    return processed_techniques


def load_or_create_mitre_fight_faiss_index(
    fight_json_path: str = "mitre_fight_techniques.json",
    fight_db_name: str = "mitre_fight.faiss_index",
    embedding_model_name: str = "all-MiniLM-L6-v2",
):
    """
    Load or create a FAISS index for MITRE FiGHT techniques.
    Defaults resolve to package assets.
    """
    assets = _assets_dir()
    fight_db_path = _resolve_path(fight_db_name, default_name="mitre_fight.faiss_index")
    json_path = _resolve_path(fight_json_path, default_name="mitre_fight_techniques.json")

    if fight_db_path.exists():
        print(f"Loading existing FAISS index from file: {fight_db_path}")
        return faiss.read_index(str(fight_db_path))

    structured_techniques_data = load_and_process_fight_data(json_path)
    if not structured_techniques_data:
        print("No techniques loaded. Exiting.")
        return None

    corpus_for_embedding = [item["text_for_embedding"] for item in structured_techniques_data]
    print(f"Loaded and processed {len(structured_techniques_data)} techniques.")
    if corpus_for_embedding:
        print(f"Sample text for embedding (first): '{corpus_for_embedding[0]}'")

    embedding_model = SentenceTransformer(embedding_model_name)

    print("Embedding techniques... This might take a while depending on corpus size.")
    corpus_embeddings = embedding_model.encode(
        corpus_for_embedding, convert_to_tensor=False, show_progress_bar=True
    )

    corpus_embeddings_faiss = np.array(corpus_embeddings, dtype="float32")
    embedding_dimension = corpus_embeddings_faiss.shape[1]
    faiss.normalize_L2(corpus_embeddings_faiss)

    index = faiss.IndexFlatL2(embedding_dimension)
    index.add(corpus_embeddings_faiss)

    print(f"FAISS index built successfully with {index.ntotal} vectors (Dimension: {index.d}).")

    # Ensure assets dir exists (if someone customized path outside package)
    fight_db_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(fight_db_path))
    print(f"Wrote FAISS index to: {fight_db_path}")
    return index
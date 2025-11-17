"""
Record serialization and chunking utilities for RAG pipeline.

Converts MongoDB documents to searchable text format with metadata preservation.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter


def serialize_record_to_text(record: Dict, collection_name: str) -> str:
    """
    Convert a MongoDB document to a searchable text format.
    
    Args:
        record: MongoDB document
        collection_name: Name of the source collection
        
    Returns:
        Formatted text string representing the record
    """
    # Extract key fields based on collection type
    text_parts = []
    
    # Add collection context
    text_parts.append(f"Collection: {collection_name}")
    
    # Add date if available
    if "date" in record:
        text_parts.append(f"Date: {record['date']}")
    
    # Collection-specific formatting
    if collection_name == "food_logs":
        text_parts.append(f"Food: {record.get('item', 'Unknown')}")
        if record.get('calories'):
            text_parts.append(f"Calories: {record['calories']}")
        if record.get('protein_g'):
            text_parts.append(f"Protein: {record['protein_g']}g")
        if record.get('carbs_g'):
            text_parts.append(f"Carbs: {record['carbs_g']}g")
        if record.get('fat_g'):
            text_parts.append(f"Fat: {record['fat_g']}g")
        if record.get('fiber_g'):
            text_parts.append(f"Fiber: {record['fiber_g']}g")
        if record.get('timestamp'):
            text_parts.append(f"Time: {record['timestamp']}")
    
    elif collection_name == "exercise_logs":
        text_parts.append(f"Exercise: {record.get('exercise_type', 'Unknown')}")
        if record.get('duration_minutes'):
            text_parts.append(f"Duration: {record['duration_minutes']} minutes")
        if record.get('calories_burned'):
            text_parts.append(f"Calories burned: {record['calories_burned']}")
        if record.get('peloton_strive_score'):
            text_parts.append(f"Peloton Strive Score: {record['peloton_strive_score']}")
        if record.get('peloton_output'):
            text_parts.append(f"Peloton Output: {record['peloton_output']}")
        if record.get('peloton_avg_hr'):
            text_parts.append(f"Average Heart Rate: {record['peloton_avg_hr']} bpm")
        if record.get('training_zones'):
            zones = record['training_zones']
            if isinstance(zones, dict):
                zone_text = ", ".join([f"Zone {k[-1]}: {v}m" for k, v in zones.items() if v])
                if zone_text:
                    text_parts.append(f"Training Zones: {zone_text}")
        if record.get('notes'):
            text_parts.append(f"Notes: {record['notes']}")
        if record.get('timestamp'):
            text_parts.append(f"Time: {record['timestamp']}")
    
    elif collection_name == "hydration_logs":
        text_parts.append("Hydration")
        if record.get('amount_oz'):
            text_parts.append(f"Amount: {record['amount_oz']} oz")
        if record.get('timestamp'):
            text_parts.append(f"Time: {record['timestamp']}")
    
    elif collection_name == "sleep_logs":
        text_parts.append("Sleep")
        if record.get('hours'):
            text_parts.append(f"Hours: {record['hours']}")
        if record.get('sleep_score'):
            text_parts.append(f"Sleep Score: {record['sleep_score']}")
        if record.get('quality_notes'):
            text_parts.append(f"Quality: {record['quality_notes']}")
    
    elif collection_name == "wellness_scores":
        text_parts.append("Wellness")
        if record.get('mood'):
            text_parts.append(f"Mood: {record['mood']}")
        if record.get('stress_level') is not None:
            text_parts.append(f"Stress Level: {record['stress_level']}/5")
        if record.get('energy_score') is not None:
            text_parts.append(f"Energy Score: {record['energy_score']}/10")
        if record.get('hunger_score') is not None:
            text_parts.append(f"Hunger Score: {record['hunger_score']}/10")
        if record.get('soreness_score') is not None:
            text_parts.append(f"Soreness Score: {record['soreness_score']}/10")
        if record.get('timestamp'):
            text_parts.append(f"Time: {record['timestamp']}")
    
    elif collection_name == "daily_health":
        text_parts.append("Daily Health")
        if record.get('weight_lbs'):
            text_parts.append(f"Weight: {record['weight_lbs']} lbs")
        if record.get('bowel_movements'):
            text_parts.append(f"Bowel Movements: {record['bowel_movements']}")
        if record.get('electrolytes_taken'):
            text_parts.append(f"Electrolytes: {'Yes' if record['electrolytes_taken'] else 'No'}")
    
    elif collection_name == "training_days":
        text_parts.append("Training Day")
        if record.get('intensity'):
            text_parts.append(f"Intensity: {record['intensity']}")
        if record.get('exercise_calories'):
            text_parts.append(f"Exercise Calories: {record['exercise_calories']}")
        if record.get('notes'):
            text_parts.append(f"Notes: {record['notes']}")
    
    else:
        # Generic fallback: include all non-metadata fields
        for key, value in record.items():
            if key not in ['_id', 'lifelog_id', 'created_at', 'updated_at']:
                if value is not None:
                    text_parts.append(f"{key}: {value}")
    
    return "\n".join(text_parts)


def chunk_record(
    record: Dict,
    collection_name: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Dict[str, Any]]:
    """
    Chunk a MongoDB record into text chunks with metadata.
    
    Args:
        record: MongoDB document
        collection_name: Name of the source collection
        chunk_size: Maximum size of each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of chunk dictionaries with 'text' and 'metadata' keys
    """
    # Serialize record to text
    text = serialize_record_to_text(record, collection_name)
    
    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    # Split text into chunks
    chunks = text_splitter.split_text(text)
    
    # Determine module from collection name
    module_map = {
        "food_logs": "nutrition",
        "hydration_logs": "nutrition",
        "sleep_logs": "nutrition",
        "wellness_scores": "nutrition",
        "daily_health": "nutrition",
        "exercise_logs": "workout",
        "training_days": "workout"
    }
    module = module_map.get(collection_name, "unknown")
    
    # Create chunk documents with metadata
    chunk_docs = []
    for i, chunk_text in enumerate(chunks):
        chunk_doc = {
            "text": chunk_text,
            "metadata": {
                "source_collection": collection_name,
                "source_id": str(record.get("_id", "")),
                "date": record.get("date", ""),
                "module": module,
                "record_type": collection_name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "lifelog_id": record.get("lifelog_id"),
                "timestamp": record.get("timestamp") or record.get("created_at")
            }
        }
        chunk_docs.append(chunk_doc)
    
    return chunk_docs


def get_collections_to_vectorize() -> List[str]:
    """
    Get list of collection names that should be vectorized.
    
    Returns:
        List of collection names
    """
    return [
        "food_logs",
        "exercise_logs",
        "hydration_logs",
        "sleep_logs",
        "wellness_scores",
        "daily_health",
        "training_days"
    ]


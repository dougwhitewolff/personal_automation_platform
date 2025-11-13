"""
Database initialization and management.

Provides MongoDB connection and core collection setup.
Modules add their own collections via setup_database() method.
"""

from pymongo import MongoClient
from pymongo.database import Database
from datetime import date, datetime
import os
from urllib.parse import urlparse


def init_database(mongodb_url: str = None):
    """
    Initialize MongoDB database with core collections.
    
    Modules will add their own collections via their setup_database() methods.
    
    Args:
        mongodb_url: MongoDB connection URL (can include database name in path)
                    If not provided, uses MONGODB_URL env var or defaults to localhost
        
    Returns:
        pymongo.Database: Database instance
    """
    if mongodb_url is None:
        # Default to local MongoDB
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/automation_platform")
    
    # Parse URL to extract database name
    parsed = urlparse(mongodb_url)
    
    # Extract database name from path (remove leading slash)
    db_name = parsed.path.lstrip('/') if parsed.path and parsed.path != '/' else None
    
    # If no database name in URL, use default
    if not db_name:
        db_name = "automation_platform"
    
    # Create connection string without database name for MongoClient
    # MongoClient works with the full URL, but we'll use the database name explicitly
    # Reconstruct base connection string (without database path)
    if parsed.query:
        # Preserve query parameters (like authSource, etc.)
        connection_string = f"{parsed.scheme}://{parsed.netloc}/?{parsed.query}"
    else:
        connection_string = f"{parsed.scheme}://{parsed.netloc}/"
    
    client = MongoClient(connection_string)
    db = client[db_name]
    
    # Core metadata collection
    system_metadata = db["system_metadata"]
    system_metadata.create_index("key", unique=True)
    
    # Track last processed lifelog
    processing_state = db["processing_state"]
    processing_state.create_index("id", unique=True)
    
    # Initialize processing state if not exists
    if processing_state.count_documents({}) == 0:
        processing_state.insert_one({
            "id": 1,
            "last_processed_time": datetime.utcnow().isoformat(),
            "last_processed_id": None,
            "updated_at": datetime.utcnow()
        })
    
    print("✅ Core database initialized")
    return db


def get_last_processed_time(db: Database):
    """Get the last processed timestamp for Limitless polling"""
    processing_state = db["processing_state"]
    doc = processing_state.find_one({"id": 1}, sort=[("id", -1)])
    if doc:
        return doc.get("last_processed_time", datetime.utcnow().isoformat())
    return datetime.utcnow().isoformat()


def update_last_processed_time(db: Database, timestamp, lifelog_id=None):
    """Update the last processed timestamp"""
    processing_state = db["processing_state"]
    processing_state.update_one(
        {"id": 1},
        {
            "$set": {
                "last_processed_time": timestamp,
                "last_processed_id": lifelog_id,
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True
    )

"""
Database initialization and management.

Provides MongoDB connection and core collection setup.
Modules add their own collections via setup_database() method.
"""

from pymongo import MongoClient
from datetime import datetime
from urllib.parse import urlparse
from core.env_loader import get_env


def init_database(connection_url=None):
    """
    Initialize MongoDB database with core collections.
    
    Modules will add their own collections via their setup_database() methods.
    
    Args:
        connection_url: MongoDB connection URL (defaults to MONGODB_URL env var)
        
    Returns:
        pymongo.database.Database: Database object
    """
    if connection_url is None:
        connection_url = get_env("MONGODB_URL")
        if not connection_url:
            raise ValueError("MONGODB_URL environment variable is required")
    
    # Connect to MongoDB
    client = MongoClient(connection_url)
    
    # Get database name from connection URL or use default
    # MongoDB connection URLs typically include database name: mongodb://host:port/dbname
    # If not specified, use default
    try:
        parsed = urlparse(connection_url)
        db_name = parsed.path.lstrip('/').split('?')[0].split('/')[0]
        if not db_name:
            db_name = "automation_platform"
    except:
        db_name = "automation_platform"
    
    db = client[db_name]
    
    # Create indexes for core collections
    # Collections are created automatically on first insert
    
    # System metadata collection
    system_metadata = db["system_metadata"]
    system_metadata.create_index("key", unique=True)
    
    # Processing state collection
    processing_state = db["processing_state"]
    processing_state.create_index("id", unique=True)
    
    # Initialize processing state if not exists
    if processing_state.count_documents({}) == 0:
        processing_state.insert_one({
            "id": 1,
            "last_processed_time": datetime.utcnow().isoformat(),
            "last_processed_id": None,
            "updated_at": datetime.utcnow().isoformat()
        })
    
    print("✅ Core database initialized")
    return db


def get_last_processed_time(db):
    """Get the last processed timestamp for Limitless polling"""
    processing_state = db["processing_state"]
    doc = processing_state.find_one(sort=[("id", -1)])
    return doc["last_processed_time"] if doc else datetime.utcnow().isoformat()


def update_last_processed_time(db, timestamp, lifelog_id=None):
    """Update the last processed timestamp"""
    processing_state = db["processing_state"]
    # Get the latest document
    latest = processing_state.find_one(sort=[("id", -1)])
    if latest:
        processing_state.update_one(
            {"id": latest["id"]},
            {
                "$set": {
                    "last_processed_time": timestamp,
                    "last_processed_id": lifelog_id,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
    else:
        # Create new if doesn't exist
        processing_state.insert_one({
            "id": 1,
            "last_processed_time": timestamp,
            "last_processed_id": lifelog_id,
            "updated_at": datetime.utcnow().isoformat()
        })

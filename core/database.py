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
    
    # Track processed lifelogs (for deduplication)
    processed_lifelogs = db["processed_lifelogs"]
    processed_lifelogs.create_index("lifelog_id", unique=True)
    
    print("✅ Core database initialized")
    return db



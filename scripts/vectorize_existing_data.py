#!/usr/bin/env python3
"""
Batch vectorization script for existing MongoDB records.

This script vectorizes all existing records in the database collections
for use with the RAG pipeline. It reads from MongoDB and stores vectors in Pinecone.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.database import init_database
from core.rag_service import RAGService
from core.env_loader import get_env
from utils.vectorization_helper import vectorize_all_collections


def main():
    """Main entry point for batch vectorization."""
    print("=" * 60)
    print("  Batch Vectorization Script")
    print("=" * 60)
    print()
    
    # Helper function for safe printing on Windows
    def safe_print(text):
        try:
            print(text)
        except UnicodeEncodeError:
            # Replace common emojis with ASCII alternatives
            text = text.replace("✅", "[OK]")
            text = text.replace("❌", "[ERROR]")
            text = text.replace("⚠️", "[WARN]")
            text = text.replace("📦", "[INFO]")
            text = text.replace("ℹ️", "[INFO]")
            print(text)
    
    # Initialize database (for reading source data)
    mongodb_url = get_env("MONGODB_URL", "mongodb://localhost:27017/automation_platform")
    db = init_database(mongodb_url)
    safe_print("✅ MongoDB connection established (for reading source data)")
    
    # Get API keys
    openai_api_key = get_env("OPENAI_API_KEY")
    if not openai_api_key:
        safe_print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    pinecone_api_key = get_env("PINECONE_API_KEY")
    if not pinecone_api_key:
        safe_print("❌ ERROR: PINECONE_API_KEY environment variable not set")
        print("   Please set PINECONE_API_KEY in your environment or .env file")
        sys.exit(1)
    
    # Initialize RAG service with Pinecone
    try:
        index_name = get_env("PINECONE_INDEX_NAME", "rag-chunks")
        namespace = get_env("PINECONE_NAMESPACE", "default")
        
        rag_service = RAGService(
            pinecone_api_key=pinecone_api_key,
            openai_api_key=openai_api_key,
            index_name=index_name,
            namespace=namespace
        )
        safe_print(f"✅ RAG Service initialized with Pinecone")
        print(f"   Index: {index_name}")
        print(f"   Namespace: {namespace}")
    except Exception as e:
        safe_print(f"❌ ERROR: Failed to initialize RAG service: {e}")
        sys.exit(1)
    
    print()
    safe_print("ℹ️  This script will:")
    print("   1. Read records from MongoDB collections")
    print("   2. Vectorize and store them in Pinecone")
    print()
    
    response = input("Continue with vectorization? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)
    
    print()
    
    # Vectorize all collections
    results = vectorize_all_collections(rag_service, db)
    
    # Print summary
    print("\n" + "=" * 60)
    print("  Vectorization Summary")
    print("=" * 60)
    for collection_name, count in results.items():
        print(f"  {collection_name}: {count} records")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()


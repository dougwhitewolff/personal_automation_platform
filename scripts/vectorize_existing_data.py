#!/usr/bin/env python3
"""
Batch vectorization script for existing MongoDB records.

This script vectorizes all existing records in the database collections
for use with the RAG pipeline.
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
    
    # Initialize database
    mongodb_url = get_env("MONGODB_URL", "mongodb://localhost:27017/automation_platform")
    db = init_database(mongodb_url)
    
    # Initialize RAG service
    openai_api_key = get_env("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    try:
        rag_service = RAGService(
            db=db,
            openai_api_key=openai_api_key,
            collection_name="rag_chunks",
            index_name="vector_index"
        )
        print("✅ RAG Service initialized")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize RAG service: {e}")
        sys.exit(1)
    
    # Check if vector search index exists
    print("\nℹ️  Note: Make sure the vector search index 'vector_index' exists in MongoDB Atlas")
    print("   Collection: rag_chunks")
    print("   Index configuration:")
    print("   - Fields: [{'type': 'vector', 'path': 'embedding', 'numDimensions': 1536, 'similarity': 'cosine'}]")
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


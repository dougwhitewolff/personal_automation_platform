"""
Helper functions for vectorizing MongoDB records for RAG.

Provides utilities for real-time and batch vectorization.
"""

from typing import List, Dict, Optional
from pymongo.database import Database
from utils.vectorization import chunk_record, get_collections_to_vectorize


def vectorize_record(
    rag_service,
    record: Dict,
    collection_name: str
) -> bool:
    """
    Vectorize a single record and add it to the vector store.
    
    Args:
        rag_service: RAGService instance
        record: MongoDB document to vectorize
        collection_name: Name of the source collection
        
    Returns:
        True if successful
    """
    try:
        # Chunk the record
        chunks = chunk_record(record, collection_name)
        
        if not chunks:
            return False
        
        # Add to vector store
        ids = rag_service.add_documents(chunks)
        return len(ids) > 0
    except Exception as e:
        print(f"⚠️  Error vectorizing record from {collection_name}: {e}")
        return False


def vectorize_collection(
    rag_service: 'RAGService',
    db: Database,
    collection_name: str,
    batch_size: int = 100
) -> int:
    """
    Vectorize all records in a collection.
    
    Args:
        rag_service: RAGService instance
        db: MongoDB database instance
        collection_name: Name of the collection to vectorize
        batch_size: Number of records to process at once
        
    Returns:
        Number of records vectorized
    """
    collection = db[collection_name]
    total_vectorized = 0
    
    # Get all records
    records = list(collection.find({}))
    total_records = len(records)
    
    print(f"📦 Vectorizing {total_records} records from {collection_name}...")
    
    # Process in batches
    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_chunks = []
        
        for record in batch:
            try:
                chunks = chunk_record(record, collection_name)
                batch_chunks.extend(chunks)
            except Exception as e:
                print(f"⚠️  Error chunking record {record.get('_id')}: {e}")
                continue
        
        # Add batch to vector store
        if batch_chunks:
            try:
                rag_service.add_documents(batch_chunks)
                total_vectorized += len(batch)
                print(f"   ✓ Vectorized {min(i + batch_size, total_records)}/{total_records} records")
            except Exception as e:
                print(f"⚠️  Error adding batch to vector store: {e}")
    
    print(f"✅ Completed vectorizing {collection_name}: {total_vectorized} records")
    return total_vectorized


def vectorize_all_collections(
    rag_service: 'RAGService',
    db: Database
) -> Dict[str, int]:
    """
    Vectorize all collections that should be vectorized.
    
    Args:
        rag_service: RAGService instance
        db: MongoDB database instance
        
    Returns:
        Dict mapping collection names to number of records vectorized
    """
    results = {}
    collections = get_collections_to_vectorize()
    
    print(f"🚀 Starting batch vectorization of {len(collections)} collections...")
    
    for collection_name in collections:
        if collection_name not in db.list_collection_names():
            print(f"⚠️  Collection {collection_name} does not exist, skipping")
            continue
        
        count = vectorize_collection(rag_service, db, collection_name)
        results[collection_name] = count
    
    total = sum(results.values())
    print(f"\n✅ Batch vectorization complete: {total} total records vectorized")
    return results


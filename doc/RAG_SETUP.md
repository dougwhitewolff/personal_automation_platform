# RAG Pipeline Setup Instructions

This document describes how to set up the RAG (Retrieval-Augmented Generation) pipeline for cross-datatable question answering.

## Prerequisites

1. MongoDB Atlas cluster with Vector Search enabled
2. OpenAI API key (already configured)
3. LangChain packages installed (see requirements.txt)

## Step 1: Create Vector Search Index

You need to create a vector search index in MongoDB Atlas for the `rag_chunks` collection.

### Via MongoDB Atlas UI:

1. Go to your MongoDB Atlas cluster
2. Navigate to "Atlas Search" in the left sidebar
3. Click "Create Search Index"
4. Select "JSON Editor" option
5. Use the following configuration:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "string",
      "path": "metadata.source_collection"
    },
    {
      "type": "string",
      "path": "metadata.date"
    },
    {
      "type": "string",
      "path": "metadata.module"
    }
  ]
}
```

6. Name the index: `vector_index`
7. Select the database and collection: `automation_platform.rag_chunks`
8. Click "Create Search Index"

### Via MongoDB Atlas API:

You can also create the index programmatically using the MongoDB Atlas Admin API. See the MongoDB Atlas documentation for details.

## Step 2: Vectorize Existing Data

After creating the index, run the batch vectorization script to vectorize all existing records:

```bash
python scripts/vectorize_existing_data.py
```

This will:
- Connect to your MongoDB database
- Vectorize all records from configured collections (food_logs, exercise_logs, etc.)
- Store chunks in the `rag_chunks` collection

## Step 3: Verify Setup

1. Check that the vector search index is active in MongoDB Atlas
2. Verify that records are being vectorized (check `rag_chunks` collection)
3. Test a query that requires data (e.g., "How much protein did I eat today?")

## Real-time Vectorization

Currently, new records are not automatically vectorized. To enable real-time vectorization:

1. Modules can call `rag_service.vectorize_record(record, collection_name)` after inserting records
2. Or implement MongoDB change streams to automatically vectorize new records

## Troubleshooting

### Index Not Found Error

If you see errors about the vector search index not being found:
- Verify the index name matches `vector_index` (or update the configuration)
- Ensure the index is fully built (can take a few minutes)
- Check that Vector Search is enabled on your Atlas cluster

### No Results from Queries

If queries return no results:
- Verify records have been vectorized (check `rag_chunks` collection)
- Ensure the embedding model matches (text-embedding-3-small, 1536 dimensions)
- Check that the vector search index is active

### Import Errors

If you see import errors for LangChain packages:
```bash
pip install -r requirements.txt
```

## Configuration

The RAG service can be configured via environment variables:

- `MONGODB_URL`: MongoDB connection string (defaults to localhost)
- `OPENAI_API_KEY`: OpenAI API key (required)

The service uses these defaults:
- Collection: `rag_chunks`
- Index name: `vector_index`
- Embedding model: `text-embedding-3-small`
- LLM model: `gpt-5-nano`
- Top-k results: 5


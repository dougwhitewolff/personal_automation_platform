# RAG Pipeline Setup Instructions

This document describes how to set up the RAG (Retrieval-Augmented Generation) pipeline for cross-datatable question answering using Pinecone.

## Prerequisites

1. Pinecone account and API key
2. OpenAI API key (already configured)
3. LangChain packages installed (see requirements.txt)

## Step 1: Get Pinecone API Key

1. Sign up for a Pinecone account at https://www.pinecone.io/
2. Create a new project (or use an existing one)
3. Navigate to API Keys section in your Pinecone dashboard
4. Copy your API key
5. Set it as an environment variable:
   ```bash
   export PINECONE_API_KEY="your-api-key-here"
   ```
   Or add it to your `.env` file:
   ```
   PINECONE_API_KEY=your-api-key-here
   ```

## Step 2: Index Creation

The Pinecone index will be created automatically when you first initialize the RAG service. The default configuration is:

- **Index name**: `rag-chunks` (configurable via `PINECONE_INDEX_NAME` env var)
- **Namespace**: `default` (configurable via `PINECONE_NAMESPACE` env var)
- **Dimension**: 1536 (for `text-embedding-3-small` model)
- **Metric**: cosine similarity
- **Cloud**: AWS (us-east-1 by default)

### Manual Index Creation (Optional)

If you prefer to create the index manually via Pinecone dashboard:

1. Go to your Pinecone project dashboard
2. Click "Create Index"
3. Configure:
   - **Name**: `rag-chunks` (or your preferred name)
   - **Dimensions**: `1536`
   - **Metric**: `cosine`
   - **Cloud Provider**: AWS (or your preference)
   - **Region**: us-east-1 (or your preference)

## Step 3: Vectorize Existing Data

After setting up Pinecone, run the batch vectorization script to vectorize all existing records:

```bash
python scripts/vectorize_existing_data.py
```

This will:
- Connect to your MongoDB database (for reading source data)
- Connect to Pinecone (for storing vectors)
- Vectorize all records from configured collections (food_logs, exercise_logs, etc.)
- Store chunks in the Pinecone index

## Step 4: Verify Setup

1. Check that the Pinecone index exists and is ready in your Pinecone dashboard
2. Verify that records are being vectorized (check index stats in Pinecone dashboard)
3. Test a query that requires data (e.g., "How much protein did I eat today?")

## Real-time Vectorization

To enable real-time vectorization when new records are added:

1. Modules can call `rag_service.vectorize_record(record, collection_name)` after inserting records
2. The RAG service will automatically chunk and add the record to Pinecone

## Configuration

The RAG service can be configured via environment variables:

- `PINECONE_API_KEY`: Pinecone API key (required)
- `PINECONE_INDEX_NAME`: Pinecone index name (default: `rag-chunks`)
- `PINECONE_NAMESPACE`: Pinecone namespace (default: `default`)
- `PINECONE_REGION`: AWS region for serverless index (default: `us-east-1`)
- `OPENAI_API_KEY`: OpenAI API key (required)
- `MONGODB_URL`: MongoDB connection string (for reading source data, defaults to localhost)

The service uses these defaults:
- Index name: `rag-chunks`
- Namespace: `default`
- Embedding model: `text-embedding-3-small`
- LLM model: `gpt-5-nano`
- Top-k results: 5
- Vector dimension: 1536

## Troubleshooting

### Index Not Found Error

If you see errors about the Pinecone index not being found:
- Verify your `PINECONE_API_KEY` is set correctly
- Check that the index name matches your configuration
- Ensure you have permission to create indexes in your Pinecone project
- The index will be created automatically on first use if it doesn't exist

### No Results from Queries

If queries return no results:
- Verify records have been vectorized (check index stats in Pinecone dashboard)
- Ensure the embedding model matches (text-embedding-3-small, 1536 dimensions)
- Check that the index is ready (not still building)
- Verify the namespace matches if you're using a custom namespace

### Import Errors

If you see import errors for LangChain or Pinecone packages:
```bash
pip install -r requirements.txt
```

### API Key Errors

If you see authentication errors:
- Verify your `PINECONE_API_KEY` is correct
- Check that the API key has the necessary permissions
- Ensure the API key is set in your environment or `.env` file

## Metadata Structure

Documents stored in Pinecone include the following metadata fields:
- `source_id`: Original document ID from MongoDB
- `source_collection`: Source collection name (e.g., "food_logs")
- `date`: Date of the record
- `module`: Module name that created the record
- `record_type`: Type of record (e.g., "food_entry", "exercise")

These metadata fields are used for filtering and context in queries.

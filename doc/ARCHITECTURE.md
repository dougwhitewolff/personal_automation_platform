# Architecture Documentation

## Overview

Personal Automation Platform is a modular system that connects voice input (via Limitless Pendant) to intelligent automation modules through Discord. It uses AI-powered semantic routing to process natural language commands and queries.

## System Architecture

```
┌─────────────────┐
│ Limitless API   │───┐
└─────────────────┘   │
                      │
┌─────────────────┐   │    ┌──────────────────┐
│   Discord Bot   │───┼───▶│   Orchestrator   │
└─────────────────┘   │    │  (Intent Router) │
                      │    └────────┬─────────┘
┌─────────────────┐   │             │
│   Scheduler     │───┘             │
└─────────────────┘                 │
                                    ▼
                    ┌─────────────────────────────┐
                    │      Module Registry        │
                    └───────────┬─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
        ┌───────────┐   ┌───────────┐   ┌───────────┐
        │ Nutrition │   │  Workout  │   │   Sleep   │
        │  Module   │   │  Module   │   │  Module   │
        └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   MongoDB Database │
                    └───────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   RAG Service     │
                    │  (Pinecone + LLM) │
                    └───────────────────┘
```

## Core Components

### 1. Entry Point (`main.py`)
- Initializes all services
- Coordinates polling, Discord bot, and scheduler
- Manages application lifecycle

### 2. Core Services (`core/`)

**Orchestrator** (`orchestrator.py`)
- AI-powered intent routing using OpenAI function calling
- Determines which modules to invoke based on user intent
- Handles scope checking and direct answers
- Uses `gpt-5.1` for routing decisions

**OpenAI Client** (`openai_client.py`)
- Text extraction and analysis (`gpt-5-nano`)
- Image/vision analysis (`gpt-5-nano`)
- Query answering (`gpt-5-nano`)

**Limitless Client** (`limitless_client.py`)
- Polls Limitless API for new lifelogs
- Semantic search for "log that" commands (hybrid search)
- Fetches daily transcripts
- Handles date filtering and timezone conversion
- Returns lifelogs with `id`, `markdown`, timestamps

**Discord Bot** (`discord_bot.py`)
- Handles Discord messages and attachments
- Routes to orchestrator for processing
- Sends responses and notifications

**RAG Service** (`rag_service.py`)
- Vector search over Pinecone
- Date-aware query filtering
- Context retrieval for Q&A

**Database** (`database.py`)
- MongoDB connection management
- Collection initialization
- Tracks processed lifelogs (`processed_lifelogs` collection)

**Scheduler** (`scheduler.py`)
- Task scheduling (reminders, summaries)
- Timezone-aware execution

### 3. Module System (`modules/`)

**Base Module** (`base.py`)
- Abstract base class for all modules
- Defines interface: `handle_log()`, `handle_image()`, `get_keywords()`
- Provides vectorization helper

**Module Registry** (`registry.py`)
- Auto-discovers and loads modules
- Routes keywords to modules
- Aggregates scheduled tasks

**Concrete Modules**
- `nutrition.py` - Food, macros, hydration tracking
- `workout.py` - Exercise and Peloton stats
- `sleep.py` - Sleep tracking with OCR/LLM image processing
- `health.py` - Health metrics and wellness scores

## Data Flow

### 1. Voice Input Flow (Lifelog Processing)
```
Limitless Pendant → Limitless API → Polling Loop → Context Extraction → Orchestrator → Module → MongoDB → RAG
```

**Detailed Lifelog Retrieval & Processing:**

1. **Polling** (`polling_loop` in `main.py`)
   - Runs every 2-10 seconds (configurable via `POLL_INTERVAL`)
   - Uses semantic search: `limitless_client.search_lifelogs(query="log that", limit=3)`

2. **Lifelog Retrieval** (`limitless_client.search_lifelogs`)
   - Searches Limitless API with hybrid (semantic + keyword) search
   - Filters by today's date in configured timezone
   - Returns up to 3 newest entries matching "log that"
   - Each entry contains: `id`, `markdown`, `startTime`, `endTime`

3. **Deduplication**
   - Checks `processed_lifelogs` collection for `lifelog_id`
   - Skips already processed entries to prevent duplicate processing

4. **Context Extraction** (`extract_context_before_log_that`)
   - Finds all "log that" occurrences (case-insensitive, word boundaries)
   - For each occurrence, extracts up to 5 sentences before it
   - Includes the "log that" keyword itself
   - Merges overlapping chunks if multiple "log that" commands are close together
   - Returns combined context string (or empty if no "log that" found)

5. **Processing**
   - If no "log that" found → mark as processed, skip
   - If context extracted → route to orchestrator with extracted context
   - Orchestrator determines which modules to invoke
   - Modules process and store data
   - Entry marked as processed after successful handling

**Example:**
```
Full Markdown: "I had eggs and toast for breakfast. Then I went for a run. Log that."
Extracted Context: "I had eggs and toast for breakfast. Then I went for a run. Log that."
```

### 2. Discord Message Flow
```
Discord Message → Discord Bot → Orchestrator → Module → MongoDB → Response
```

### 3. Image Processing Flow
```
Image Upload → OCR (rapidocr) → Regex Parsing → Fallback to LLM → Module → MongoDB
```

### 4. Query Flow
```
User Question → Orchestrator → RAG Service → Date Filter → Pinecone → LLM → Answer
```

## Key Technologies

- **Language**: Python 3.13
- **Database**: MongoDB (document storage)
- **Vector DB**: Pinecone (semantic search)
- **AI Models**:
  - `gpt-5.1` - Intent routing (orchestrator)
  - `gpt-5-nano` - All other operations (extraction, Q&A, images)
- **OCR**: rapidocr (optional, falls back to LLM)
- **Embeddings**: text-embedding-3-small (1536 dimensions)
- **Communication**: Discord.py, Limitless API

## Module Architecture

Each module is self-contained:

```python
class Module(BaseModule):
    - get_name() → str
    - get_keywords() → List[str]
    - get_question_patterns() → List[regex]
    - setup_database() → None
    - handle_log() → Dict
    - handle_image() → Dict
    - get_scheduled_tasks() → List[Dict]
    - get_daily_summary() → Dict
```

**Module Responsibilities:**
- Own database collections
- Define trigger keywords
- Process logs and images
- Schedule tasks
- Generate summaries

## Context Extraction Algorithm

The `extract_context_before_log_that()` function intelligently extracts relevant context from lifelog markdown:

**Process:**
1. **Find all "log that" occurrences** - Uses regex with word boundaries to avoid false matches
2. **Split into sentences** - Identifies sentence boundaries using punctuation patterns
3. **Map "log that" to sentences** - Determines which sentence contains each "log that"
4. **Extract context windows** - For each "log that", gets up to 5 sentences before it (including the sentence with "log that")
5. **Merge overlapping chunks** - If multiple "log that" commands are within 5 sentences of each other, merges them into one chunk
6. **Combine results** - Joins all chunks with double newlines

**Example:**
```
Input Markdown:
"I had eggs and toast for breakfast. Then I went for a run. Log that. 
Later I had a protein shake. Log that."

Extracted Context:
"I had eggs and toast for breakfast. Then I went for a run. Log that.
Later I had a protein shake. Log that."
```

**Benefits:**
- Captures relevant context before "log that" commands
- Handles multiple "log that" commands in one lifelog
- Prevents processing irrelevant parts of long transcripts
- Reduces token usage by only sending relevant context to LLM

## Data Storage

**MongoDB Collections:**
- `food_logs` - Nutrition entries
- `hydration_logs` - Water intake
- `sleep_logs` - Sleep data
- `exercise_logs` - Workout records
- `training_days` - Training calendar
- `daily_health` - Health metrics
- `processed_lifelogs` - Tracks processed lifelog IDs (prevents duplicates)

**Pinecone Index:**
- `rag-chunks` - Vectorized document chunks
- Metadata: `date`, `source_id`, `source_collection`, `module`, `record_type`

## Integration Points

1. **Limitless API** - Voice input polling (every 2-10s)
2. **Discord** - Two-way communication
3. **OpenAI API** - LLM operations
4. **Pinecone** - Vector search
5. **MongoDB** - Data persistence

## Design Principles

1. **Modularity** - Independent modules, no cross-dependencies
2. **Extensibility** - Add modules without modifying core
3. **Cost Efficiency** - Single deployment, shared infrastructure
4. **AI-First** - Semantic routing, not keyword matching
5. **Privacy** - All data stored locally/self-hosted

## Error Handling

- Graceful degradation (OCR → LLM fallback)
- Optional dependencies (modules work without RAG)
- Retry logic for API calls
- Comprehensive logging

## Performance

- Async/await for I/O operations
- Thread pool for blocking operations (OCR)
- Efficient vector search with metadata filtering
- Cached module tools in orchestrator

## Security

- Environment variable configuration
- API key management
- No hardcoded secrets
- MongoDB connection security


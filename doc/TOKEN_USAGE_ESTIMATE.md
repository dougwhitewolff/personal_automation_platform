# Token Usage Estimate for "Log that" Requests

## Overview
Each "Log that" request triggers two OpenAI API calls:
1. **Orchestrator Routing** - Determines which module(s) to use
2. **Module Processing** - Extracts and processes the data

## Token Breakdown

### 1. Orchestrator Routing Call
**Model**: `gpt-5-nano`  
**Input**: Context transcript (last 5 entries) - built BEFORE routing for better context

| Component | Token Estimate | Notes |
|-----------|---------------|-------|
| System prompt | 200-300 | Instructions for routing |
| Tool definitions | 500-800 | ~250-400 per module (2 modules = ~600) |
| User message | 250-1,000 | Context transcript (last 5 entries) |
| **Input Total** | **950-2,100** | |
| Tool call response | 50-150 | JSON function call |
| **Total Routing** | **~1,000-2,250 tokens** | |

### 2. Module Processing Call
**Model**: `gpt-5-nano`  
**Input**: Context transcript (last 5 entries)

| Component | Token Estimate | Notes |
|-----------|---------------|-------|
| System prompt | 100-200 | Module-specific instructions |
| Custom foods context | 200-500 | Varies by number of custom foods |
| Context transcript | 250-1,000 | Last 5 entries from polling batch |
| Prompt template | 300-400 | Extraction instructions |
| **Input Total** | **850-2,100** | |
| JSON response | 200-500 | Structured data extraction |
| **Total Processing** | **~1,050-2,600 tokens** | |

## Total Per "Log that" Request

**Estimated Range**: **2,050 - 4,850 tokens per request**

**Typical/Average**: **~3,000 tokens per request**

### Breakdown:
- Orchestrator routing: ~1,600 tokens (53%) - now uses context transcript
- Module processing: ~1,400 tokens (47%)

## Cost Estimate (GPT-5-nano pricing)
Assuming $0.10 per 1M input tokens and $0.30 per 1M output tokens:

- **Input tokens**: ~2,500 tokens × $0.10/1M = **$0.00025**
- **Output tokens**: ~500 tokens × $0.30/1M = **$0.00015**
- **Total per request**: **~$0.0004** (0.04 cents)

**For 100 "log that" requests**: ~$0.04  
**For 1,000 "log that" requests**: ~$0.40  
**For 10,000 "log that" requests**: ~$4.00

## Comparison: Before vs After

### Before (Full Transcript):
- Full day's transcript: 2,000-8,000 tokens
- **Total per request**: ~3,000-10,000 tokens
- **Cost per request**: ~$0.0005-0.0015

### After (Context Chunks):
- Last 5 entries: 250-1,000 tokens (used by both orchestrator and modules)
- **Total per request**: ~2,050-4,850 tokens
- **Cost per request**: ~$0.0004

**Savings**: **~30-50% reduction in token usage**

**Note**: The orchestrator now uses the same context transcript as modules, ensuring better routing decisions when "Log that" appears in a separate entry from the content being logged.

## Factors Affecting Token Usage

1. **Number of modules**: More modules = larger tool definitions
2. **Custom foods database**: Larger DB = more context tokens
3. **Entry length**: Longer entries = more tokens in context transcript
4. **Polling batch size**: More entries = potentially longer context (capped at 5)

## Optimization Notes

- Tool definitions are cached after first call (no rebuild overhead)
- Context is limited to last 5 entries (prevents unbounded growth)
- Custom foods context could be optimized with RAG in future


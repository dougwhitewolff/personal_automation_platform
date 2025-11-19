"""
Automation Orchestrator - AI-powered semantic routing.

Uses OpenAI function calling to semantically route messages to appropriate modules.
Handles both "Log that" commands and general queries, with support for multi-module routing.
"""

from typing import Dict, List, Optional, Any
import json
import inspect
import yaml
import os
import re
from datetime import date, datetime, timedelta
import pytz


class AutomationOrchestrator:
    """
    Semantic routing orchestrator using OpenAI function calling.
    
    Analyzes user intent and routes messages to appropriate modules using
    AI-based classification instead of keyword matching.
    """
    
    def __init__(self, openai_client, registry, rag_service=None, scope_config_path: str = "scope.yaml", timezone: str = "America/Los_Angeles"):
        """
        Initialize orchestrator.
        
        Args:
            openai_client: OpenAIClient instance
            registry: ModuleRegistry instance
            rag_service: Optional RAGService instance for answering queries
            scope_config_path: Path to scope configuration file
            timezone: Timezone string (e.g., "America/Los_Angeles") for date calculations
        """
        self.openai_client = openai_client
        self.registry = registry
        self.rag_service = rag_service
        self._module_tools_cache = None
        self.scope_config = self._load_scope_config(scope_config_path)
        self.timezone = pytz.timezone(timezone)
    
    def _get_today_in_timezone(self) -> date:
        """
        Get today's date in the configured timezone.
        
        Returns:
            date object representing today in the configured timezone
        """
        now_tz = datetime.now(self.timezone)
        return now_tz.date()
    
    def _parse_date_from_text(self, text: str) -> Optional[date]:
        """
        Parse date from natural language text.
        
        Args:
            text: Text that may contain date information
            
        Returns:
            date object or None if no date found
        """
        if not text:
            return None
            
        text_lower = text.lower().strip()
        
        # Get today in configured timezone
        today = self._get_today_in_timezone()
        
        # Check for relative dates
        if 'yesterday' in text_lower:
            return today - timedelta(days=1)
        elif 'today' in text_lower:
            return today
        elif 'tomorrow' in text_lower:
            return today + timedelta(days=1)
        
        # Check for "X days ago"
        days_ago_match = re.search(r'(\d+)\s+days?\s+ago', text_lower)
        if days_ago_match:
            days = int(days_ago_match.group(1))
            return today - timedelta(days=days)
        
        # Check for "last week", "last month", etc.
        if 'last week' in text_lower:
            return today - timedelta(days=7)
        elif 'last month' in text_lower:
            # Approximate: 30 days ago
            return today - timedelta(days=30)
        
        # Check for "X weeks ago", "X months ago"
        weeks_ago_match = re.search(r'(\d+)\s+weeks?\s+ago', text_lower)
        if weeks_ago_match:
            weeks = int(weeks_ago_match.group(1))
            return today - timedelta(days=weeks * 7)
        
        # Check for date patterns
        # YYYY-MM-DD
        date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
        if date_match:
            try:
                return datetime.strptime(date_match.group(0), "%Y-%m-%d").date()
            except ValueError:
                pass
        
        # MM/DD/YYYY or YYYY/MM/DD
        date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
        if date_match:
            try:
                # Try MM/DD/YYYY first
                return datetime.strptime(date_match.group(0), "%m/%d/%Y").date()
            except ValueError:
                try:
                    # Try YYYY/MM/DD
                    return datetime.strptime(date_match.group(0), "%Y/%m/%d").date()
                except ValueError:
                    pass
        
        # Check for month/day patterns like "January 15" or "Jan 15"
        month_day_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})', text_lower)
        if month_day_match:
            month_str = month_day_match.group(1)
            day = int(month_day_match.group(2))
            month_map = {
                'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
                'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
                'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
                'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
                'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
                'december': 12, 'dec': 12
            }
            month = month_map.get(month_str)
            if month:
                try:
                    # Use current year in configured timezone, or previous year if the date hasn't occurred yet
                    today = self._get_today_in_timezone()
                    year = today.year
                    parsed_date = date(year, month, day)
                    # If the date is in the future (in configured timezone), use previous year
                    if parsed_date > today:
                        parsed_date = date(year - 1, month, day)
                    return parsed_date
                except ValueError:
                    pass
        
        return None
    
    def _is_summary_request(self, transcript: str) -> bool:
        """
        Check if the transcript is requesting a summary.
        
        Args:
            transcript: User message/transcript
            
        Returns:
            True if this appears to be a summary request
        """
        transcript_lower = transcript.lower()
        
        # Explicit summary keywords (high confidence)
        explicit_summary_keywords = [
            'summary', 'summarize', 'daily summary', 'day summary', 
            'give me a summary', 'show summary', 'get summary', 
            'summary for', 'summary of', 'overview'
        ]
        
        # Check for explicit summary requests
        if any(keyword in transcript_lower for keyword in explicit_summary_keywords):
            return True
        
        # Check for "what did i do" type requests (but not specific data queries)
        # These are summary requests, not specific data queries
        if 'what did i do' in transcript_lower or 'what did i' in transcript_lower:
            # But exclude specific data queries like "what did i eat", "what are the things i ate"
            # These should use RAG, not summary
            exclude_patterns = [
                'eat', 'ate', 'things i ate', 'food', 'meals', 'drank',
                'workout', 'exercise', 'slept', 'sleep', 'weighed', 'weight',
                'bowel', 'bm', 'electrolytes'
            ]
            # If it contains specific data query patterns, it's NOT a summary request
            if any(pattern in transcript_lower for pattern in exclude_patterns):
                return False
            return True
        
        # "how was" can be summary or specific query - be conservative
        if 'how was' in transcript_lower:
            # Only treat as summary if it's clearly asking about the day overall
            if 'day' in transcript_lower or 'today' in transcript_lower or 'yesterday' in transcript_lower:
                return True
        
        return False
    
    def route_intent(
        self, 
        transcript: str, 
        source: str = "limitless",
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Route a message/transcript to appropriate module(s) using semantic analysis.
        
        Args:
            transcript: User message or transcript text
            source: Source of message ("limitless" or "discord")
            context: Additional context (lifelog_id, etc.)
            
        Returns:
            Dict with routing decision:
            {
                "modules": [{"name": "nutrition", "action": "log", "confidence": 0.95}],
                "summary_request": False,
                "summary_date": None,
                "out_of_scope": False,
                "reasoning": "User mentioned meal",
                "error": None
            }
        """
        if not transcript or not transcript.strip():
            return {
                "modules": [],
                "summary_request": False,
                "summary_date": None,
                "out_of_scope": True,
                "direct_answer": None,
                "needs_rag": False,
                "rag_query": None,
                "reasoning": "Empty transcript",
                "error": None
            }
        
        # Check for summary requests first (before module routing)
        if self._is_summary_request(transcript):
            target_date = self._parse_date_from_text(transcript)
            if target_date is None:
                target_date = self._get_today_in_timezone()  # Default to today in configured timezone
            
            return {
                "modules": [],
                "summary_request": True,
                "summary_date": target_date,
                "out_of_scope": False,
                "direct_answer": None,
                "needs_rag": False,
                "rag_query": None,
                "reasoning": f"Summary request detected for {target_date.isoformat()}",
                "error": None
            }
        
        # Build module tools dynamically
        tools = self._build_module_tools()
        
        if not tools:
            return {
                "modules": [],
                "summary_request": False,
                "summary_date": None,
                "out_of_scope": False,
                "direct_answer": None,
                "needs_rag": False,
                "rag_query": None,
                "reasoning": "No modules available",
                "error": "No modules loaded in registry"
            }
        
        # Classify intent using OpenAI function calling
        try:
            routing_decision = self._classify_intent(transcript, tools, source)
            return routing_decision
        except Exception as e:
            # Fallback to keyword matching on error
            print(f"⚠️  Orchestrator error, falling back to keyword matching: {e}")
            return self._fallback_keyword_routing(transcript)
    
    def _build_module_tools(self) -> List[Dict]:
        """
        Convert registered modules to OpenAI function/tool definitions.
        
        Returns:
            List of tool definitions for OpenAI function calling
        """
        # Cache tools to avoid rebuilding on every call
        if self._module_tools_cache is not None:
            return self._module_tools_cache
        
        tools = []
        
        # Add summary tool first (so it can be detected semantically)
        summary_tool = {
            "type": "function",
            "function": {
                "name": "get_daily_summary",
                "description": (
                    "Get a daily summary of all tracked data (nutrition, workouts, sleep, health) "
                    "for a specific date. Use this ONLY when the user explicitly asks for a summary, "
                    "overview, or a list of what they did on a particular day. "
                    "DO NOT use this for analytical questions, comparisons, evaluations, or questions that require "
                    "reasoning about relationships between data points. "
                    "Examples: 'show me my summary', 'what did I do yesterday', 'give me a summary for last week', "
                    "'show stats for 2024-01-15'. "
                    "NOT for: 'is my sleep aligned with my workouts', 'how is my nutrition', 'tell me about my progress', "
                    "'can you tell me whether my sleep is properly aligned with my nutrition and workout'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": (
                                "The date to get the summary for. Can be: "
                                "'today', 'yesterday', 'tomorrow', 'X days ago' (e.g., '3 days ago'), "
                                "or a date in YYYY-MM-DD format (e.g., '2024-01-15'). "
                                "If no date is specified in the user's message, use 'today'."
                            )
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence score (0-1) that this is a summary request"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of why this is a summary request"
                        }
                    },
                    "required": ["date", "confidence", "reasoning"]
                }
            }
        }
        tools.append(summary_tool)
        
        # Add RAG tool for answering analytical/comparative questions that need data
        if self.rag_service:
            rag_tool = {
                "type": "function",
                "function": {
                    "name": "answer_query_with_rag",
                    "description": (
                        "Answer a question using the user's historical data and records. "
                        "Use this for analytical questions, comparisons, evaluations, or any questions that require "
                        "reasoning about relationships between data points, trends, patterns, or insights from the user's data. "
                        "ALSO use this for questions asking for specific lists or items from the user's data, such as: "
                        "'what are the things i ate', 'what did i eat', 'list my workouts', 'what foods did i have', "
                        "'show me what i ate today', 'what are my meals', etc. "
                        "This tool searches through the user's logged data (nutrition, workouts, sleep, health metrics, etc.) "
                        "and provides answers based on their actual records. "
                        "Examples: 'is my sleep aligned with my workouts', 'how is my nutrition', 'tell me about my progress', "
                        "'can you tell me whether my sleep is properly aligned with my nutrition and workout', "
                        "'what's my average protein intake', 'how has my weight changed', 'compare my sleep and workout patterns', "
                        "'what are the things i ate', 'what did i eat today', 'list my foods', 'what workouts did i do'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The user's question or query that needs to be answered using their data"
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": "Confidence score (0-1) that this query needs RAG to answer"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief explanation of why this query needs RAG"
                            }
                        },
                        "required": ["query", "confidence", "reasoning"]
                    }
                }
            }
            tools.append(rag_tool)
        
        # Add module tools
        modules = self.registry.get_all_modules()
        
        for module in modules:
            module_name = module.get_name()
            
            # Get module description from docstring or class name
            description = self._get_module_description(module)
            
            # Build tool definition
            tool = {
                "type": "function",
                "function": {
                    "name": f"{module_name}_module",
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["log", "query"],
                                "description": "Action type: 'log' for logging data, 'query' for answering questions"
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": "Confidence score (0-1) that this module should handle the request"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief explanation of why this module was selected"
                            }
                        },
                        "required": ["action", "confidence", "reasoning"]
                    }
                }
            }
            tools.append(tool)
        
        self._module_tools_cache = tools
        return tools
    
    def _get_module_description(self, module) -> str:
        """
        Extract module description from docstring or generate from class name.
        
        Args:
            module: Module instance
            
        Returns:
            Description string for OpenAI tool definition
        """
        # Try to get docstring from module class
        module_class = module.__class__
        docstring = inspect.getdoc(module_class)
        
        if docstring:
            # Use first paragraph of docstring
            first_line = docstring.split('\n')[0].strip()
            if first_line:
                return first_line
        
        # Fallback: generate from module name and keywords
        module_name = module.get_name()
        keywords = module.get_keywords()[:5]  # First 5 keywords
        
        return (
            f"Handles {module_name}-related tasks. "
            f"Keywords: {', '.join(keywords)}"
        )
    
    def _classify_intent(
        self, 
        transcript: str, 
        tools: List[Dict],
        source: str
    ) -> Dict:
        """
        Use OpenAI function calling to classify intent and select modules.
        
        Args:
            transcript: User message/transcript
            tools: OpenAI tool definitions for modules
            source: Source of message
            
        Returns:
            Routing decision dict
        """
        # Build system prompt based on source
        if source == "limitless":
            system_prompt = (
                "You are an intent classification system for a personal automation platform. "
                "The user has said 'Log that' and provided context. "
                "Analyze the transcript and determine which module(s) should handle this request. "
                "If the user is asking for a summary or overview of their data, use the 'get_daily_summary' function. "
                "You can select multiple modules if the request spans multiple domains. "
                "Only select modules if you are confident (>= 0.7) they should handle the request. "
                "If the request is completely out of scope, do not call any functions."
            )
        else:  # discord
            system_prompt = (
                "You are an intent classification system for a personal automation platform. "
                "Analyze the user's message and determine which tool(s) should handle it. "
                "The message could be a question, a command to log data, a request for a summary, or a general query. "
                "\n\n"
                "AVAILABLE TOOLS:\n"
                "- 'get_daily_summary': Use ONLY for explicit requests for summaries/overviews of the entire day "
                "(e.g., 'show me my summary', 'what did I do today', 'give me an overview'). "
                "DO NOT use for questions asking for specific lists or items (e.g., 'what did I eat', 'what are the things I ate')\n"
                "- 'answer_query_with_rag': Use for analytical questions, comparisons, evaluations, questions requiring reasoning "
                "about relationships between data points, trends, or insights from the user's historical data, "
                "OR questions asking for specific lists or items from the user's data. "
                "Examples: 'is my sleep aligned with workouts', 'tell me whether X is properly aligned with Y', "
                "'how is my nutrition', 'what's my progress', 'what are the things i ate', 'what did i eat today', "
                "'list my workouts', 'what foods did i have', 'show me what i ate'.\n"
                "- Module tools (e.g., 'nutrition_module', 'workout_module'): Use 'log' action for logging/recording data, "
                "or 'query' action for simple questions that a specific module can answer directly\n"
                "\n"
                "You can select multiple tools/modules if the request spans multiple domains. "
                "Only select tools if you are confident (>= 0.7) they should handle the request. "
                "If the request is completely out of scope (e.g., asking about weather, news, etc.), "
                "do not call any functions."
            )
        
        user_prompt = f"User message/transcript:\n\n{transcript}"
        
        try:
            # Call OpenAI with function calling
            response = self.openai_client.client.chat.completions.create(
                model="gpt-5-nano",  # Use more capable model for routing
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                tools=tools,
                tool_choice="auto",  # Let model decide which tools to call
                max_completion_tokens=1000
            )
            
            choice = response.choices[0]
            message = choice.message
            
            # Check if any tools were called
            # tool_calls can be None or an empty list
            tool_calls = getattr(message, 'tool_calls', None)
            if not tool_calls or len(tool_calls) == 0:
                # No tools called - check scope and provide direct answer if in scope
                scope_check = self._check_scope(transcript)
                
                if not scope_check["in_scope"]:
                    # Out of scope
                    return {
                        "modules": [],
                        "summary_request": False,
                        "summary_date": None,
                        "out_of_scope": True,
                        "direct_answer": None,
                        "needs_rag": False,
                        "rag_query": None,
                        "reasoning": scope_check.get("reasoning") or getattr(message, 'content', None) or "No relevant tools found for this request",
                        "error": None
                    }
                
                # If in scope but no tools called, provide direct answer if allowed
                if self.scope_config.get("scope_config", {}).get("allow_direct_answers", True):
                    direct_answer = self._generate_direct_answer(transcript, source)
                    return {
                        "modules": [],
                        "summary_request": False,
                        "summary_date": None,
                        "out_of_scope": False,
                        "direct_answer": direct_answer,
                        "needs_rag": False,
                        "rag_query": None,
                        "reasoning": f"In-scope general query: {scope_check['reasoning']}",
                        "error": None
                    }
                else:
                    # In-scope but can't answer
                    return {
                        "modules": [],
                        "summary_request": False,
                        "summary_date": None,
                        "out_of_scope": False,
                        "direct_answer": None,
                        "needs_rag": False,
                        "rag_query": None,
                        "reasoning": "Query in scope but cannot be answered",
                        "error": None
                    }
            
            # Parse tool calls into routing decisions
            modules = []
            summary_request = False
            summary_date = None
            rag_query = None
            rag_confidence = 0.0
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                # Check if this is a summary request
                if function_name == "get_daily_summary":
                    summary_request = True
                    date_str = arguments.get("date", "today")
                    # Parse the date string from the AI's response
                    summary_date = self._parse_date_from_text(date_str)
                    if summary_date is None:
                        # Try parsing the date_str directly as it might be a date format
                        summary_date = self._parse_date_from_text(f" {date_str} ")
                        if summary_date is None:
                            summary_date = self._get_today_in_timezone()  # Default to today in configured timezone
                    continue
                
                # Check if this is a RAG query
                if function_name == "answer_query_with_rag":
                    rag_query = arguments.get("query", transcript)  # Fallback to original transcript if not provided
                    rag_confidence = arguments.get("confidence", 0.8)
                    continue
                
                # Extract module name from function name (e.g., "nutrition_module" -> "nutrition")
                module_name = function_name.replace("_module", "")
                
                modules.append({
                    "name": module_name,
                    "action": arguments.get("action", "log"),
                    "confidence": arguments.get("confidence", 0.8),
                    "reasoning": arguments.get("reasoning", "Selected by AI")
                })
            
            # If RAG was requested, return RAG routing decision
            if rag_query:
                return {
                    "modules": [],
                    "summary_request": False,
                    "summary_date": None,
                    "out_of_scope": False,
                    "direct_answer": None,
                    "needs_rag": True,
                    "rag_query": rag_query,
                    "reasoning": f"RAG query detected (confidence: {rag_confidence:.2f})",
                    "error": None
                }
            
            # If summary was requested, return summary routing decision
            if summary_request:
                return {
                    "modules": [],
                    "summary_request": True,
                    "summary_date": summary_date,
                    "out_of_scope": False,
                    "direct_answer": None,
                    "needs_rag": False,
                    "rag_query": None,
                    "reasoning": f"Summary request detected for {summary_date.isoformat()}",
                    "error": None
                }
            
            # Determine if out of scope based on confidence scores
            # If all modules have low confidence, consider out of scope
            max_confidence = max([m["confidence"] for m in modules]) if modules else 0
            out_of_scope = max_confidence < 0.7
            
            # Check if any modules have "query" action - these should use RAG instead
            has_query_action = any(m.get("action") == "query" for m in modules)
            
            return {
                "modules": modules,
                "summary_request": False,
                "summary_date": None,
                "out_of_scope": out_of_scope,
                "direct_answer": None,
                "needs_rag": has_query_action and self.rag_service is not None,
                "rag_query": transcript if has_query_action and self.rag_service is not None else None,
                "reasoning": f"Selected {len(modules)} module(s) with max confidence {max_confidence:.2f}",
                "error": None
            }
            
        except json.JSONDecodeError as e:
            return {
                "modules": [],
                "summary_request": False,
                "summary_date": None,
                "out_of_scope": False,
                "direct_answer": None,
                "needs_rag": False,
                "rag_query": None,
                "reasoning": "Failed to parse tool call arguments",
                "error": f"JSON decode error: {str(e)}"
            }
        except Exception as e:
            return {
                "modules": [],
                "summary_request": False,
                "summary_date": None,
                "out_of_scope": False,
                "direct_answer": None,
                "needs_rag": False,
                "rag_query": None,
                "reasoning": "Error during intent classification",
                "error": str(e)
            }
    
    def _fallback_keyword_routing(self, transcript: str) -> Dict:
        """
        Fallback to keyword-based routing if AI routing fails.
        
        Args:
            transcript: User message/transcript
            
        Returns:
            Routing decision dict using keyword matching
        """
        modules = []
        transcript_lower = transcript.lower()
        
        for module in self.registry.get_all_modules():
            if module.matches_keyword(transcript_lower):
                # Check if it's a question
                is_question = module.matches_question(transcript_lower)
                
                modules.append({
                    "name": module.get_name(),
                    "action": "query" if is_question else "log",
                    "confidence": 0.6,  # Lower confidence for keyword fallback
                    "reasoning": "Matched via keyword fallback"
                })
        
        has_query_action = any(m.get("action") == "query" for m in modules)
        return {
            "modules": modules,
            "summary_request": False,
            "summary_date": None,
            "out_of_scope": len(modules) == 0,
            "direct_answer": None,
            "needs_rag": has_query_action and self.rag_service is not None,
            "rag_query": transcript if has_query_action and self.rag_service is not None else None,
            "reasoning": "Fallback keyword matching",
            "error": None
        }
    
    def _load_scope_config(self, config_path: str) -> Dict:
        """
        Load scope configuration from YAML file.
        
        Args:
            config_path: Path to scope.yaml file
            
        Returns:
            Scope configuration dict
        """
        default_config = {
            "in_scope_topics": [],
            "out_of_scope_topics": [],
            "scope_config": {
                "enable_scope_check": True,
                "allow_direct_answers": True,
                "direct_answer_model": "gpt-5-nano",
                "direct_answer_system_prompt": (
                    "You are a helpful personal automation assistant. "
                    "You help users with their personal tracking, health, fitness, "
                    "nutrition, and productivity goals. Answer questions concisely and helpfully."
                )
            }
        }
        
        if not os.path.exists(config_path):
            print(f"⚠️  Scope config file not found at {config_path}, using defaults")
            return default_config
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                # Merge with defaults
                if config:
                    default_config.update(config)
                return default_config
        except Exception as e:
            print(f"⚠️  Error loading scope config: {e}, using defaults")
            return default_config
    
    def _check_scope(self, transcript: str) -> Dict[str, bool]:
        """
        Check if a transcript is within scope using the scope configuration.
        
        Args:
            transcript: User message/transcript
            
        Returns:
            Dict with 'in_scope' (bool) and 'reasoning' (str)
        """
        if not self.scope_config.get("scope_config", {}).get("enable_scope_check", True):
            # Scope checking disabled
            return {"in_scope": True, "reasoning": "Scope checking disabled"}
        
        transcript_lower = transcript.lower()
        
        # Check explicit out-of-scope topics first
        out_of_scope_topics = self.scope_config.get("out_of_scope_topics", [])
        for topic in out_of_scope_topics:
            if topic.lower() in transcript_lower:
                return {
                    "in_scope": False,
                    "reasoning": f"Contains out-of-scope topic: {topic}"
                }
        
        # Check in-scope topics
        in_scope_topics = self.scope_config.get("in_scope_topics", [])
        for topic in in_scope_topics:
            if topic.lower() in transcript_lower:
                return {
                    "in_scope": True,
                    "reasoning": f"Matches in-scope topic: {topic}"
                }
        
        # Use AI to determine if it's in-scope (general personal automation context)
        # If it's a question about personal data, health, fitness, etc., it's likely in-scope
        scope_keywords = [
            "my", "i", "me", "personal", "health", "fitness", "nutrition",
            "workout", "exercise", "food", "meal", "sleep", "track", "log",
            "progress", "summary", "stats", "data", "goal", "target"
        ]
        
        has_scope_keywords = any(keyword in transcript_lower for keyword in scope_keywords)
        
        if has_scope_keywords:
            return {
                "in_scope": True,
                "reasoning": "Contains personal automation keywords"
            }
        
        # Default: assume in-scope for personal automation platform
        # (let the model decide if it can answer)
        return {
            "in_scope": True,
            "reasoning": "Default: within personal automation scope"
        }
    
    def _generate_direct_answer(self, transcript: str, source: str) -> str:
        """
        Generate a direct answer for an in-scope query when no module routing is needed.
        
        Args:
            transcript: User message/transcript
            source: Source of message
            
        Returns:
            Direct answer string
        """
        scope_cfg = self.scope_config.get("scope_config", {})
        model = scope_cfg.get("direct_answer_model", "gpt-5-nano")
        system_prompt = scope_cfg.get(
            "direct_answer_system_prompt",
            "You are a helpful personal automation assistant."
        )
        
        # Enhance system prompt with module context
        modules = self.registry.get_all_modules()
        module_list = ", ".join([m.get_name() for m in modules])
        
        enhanced_system_prompt = (
            f"{system_prompt}\n\n"
            f"Available modules: {module_list}\n"
            "You can answer questions about personal automation, health, fitness, nutrition, "
            "and productivity. If the question is about specific data that requires module access, "
            "suggest using the appropriate module or command."
        )
        
        try:
            response = self.openai_client.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": enhanced_system_prompt},
                    {"role": "user", "content": transcript}
                ],
                max_completion_tokens=1000
            )
            
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            return f"I encountered an error while generating a response: {str(e)}"
    
    def _query_needs_data(self, transcript: str) -> bool:
        """
        Determine if a query needs data from records to answer.
        
        Args:
            transcript: User's query/question
            
        Returns:
            True if query likely needs data from records
        """
        transcript_lower = transcript.lower()
        
        # Keywords that indicate the query needs data
        data_keywords = [
            "my", "i", "me", "today", "yesterday", "this week", "last week",
            "how much", "how many", "what did", "when did", "did i",
            "have i", "show me", "tell me", "tell me about", "what is my", "what was my",
            "calories", "protein", "workout", "exercise", "food", "meal",
            "sleep", "weight", "hydration", "water", "mood", "energy",
            "summary", "stats", "progress", "total", "average", "nutrition"
        ]
        
        # Analytical/comparative keywords that definitely need RAG
        analytical_keywords = [
            "aligned", "alignment", "whether", "properly", "compare", "comparison",
            "relationship", "correlation", "affect", "impact", "influence",
            "better", "worse", "improve", "decline", "trend", "pattern"
        ]
        
        # Check if query contains data-related keywords
        has_data_keywords = any(keyword in transcript_lower for keyword in data_keywords)
        
        # Check if it contains analytical keywords (strong indicator for RAG)
        has_analytical_keywords = any(keyword in transcript_lower for keyword in analytical_keywords)
        
        # Check if it's a question (starts with question words or contains question patterns)
        is_question = any(transcript_lower.strip().startswith(q) for q in [
            "how", "what", "when", "where", "who", "why", "did", "have", "has",
            "was", "were", "is", "are", "can", "could", "would", "should"
        ]) or "?" in transcript or any(q in transcript_lower for q in ["can you", "could you", "would you"])
        
        # If it has analytical keywords, it definitely needs RAG
        if has_analytical_keywords:
            return True
        
        # Otherwise, check if it's a question with data keywords
        return has_data_keywords and is_question
    
    def answer_query_with_rag(self, query: str) -> str:
        """
        Answer a query using RAG service.
        
        Args:
            query: User's question
            
        Returns:
            Answer string
        """
        if not self.rag_service:
            return "RAG service is not available. Please check configuration."
        
        return self.rag_service.answer_query(query)
    
    def invalidate_cache(self):
        """Invalidate module tools cache (call when modules are added/removed)."""
        self._module_tools_cache = None


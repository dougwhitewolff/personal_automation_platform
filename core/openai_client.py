# core/openai_client.py
"""
OpenAI API client wrapper.

Handles:
- Text extraction and analysis
- Image/vision analysis
- Question answering
"""
from openai import OpenAI
import json
import base64
from typing import Dict

class OpenAIClient:
    """Wrapper for OpenAI API"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    @staticmethod
    def _clean_json_text(text: str) -> str:
        # Remove common fenced code wrappers
        return text.replace("```json", "").replace("```", "").strip()

    def analyze_text(
        self,
        transcript: str,
        module_name: str,
        custom_context: str = "",
        prompt_template: str = ""
    ) -> Dict:
        """
        Analyze text using OpenAI to extract structured JSON.
        """
        if not prompt_template:
            prompt = (
                f"Extract relevant information for the {module_name} module from this transcript.\n\n"
                f"{custom_context}\n\n"
                f"TRANSCRIPT:\n{transcript}\n\n"
                "Respond with ONLY valid JSON. Do not include markdown code blocks or any text outside the JSON."
            )
        else:
            # Allow prompt template to include {transcript} and {custom_context}
            prompt = prompt_template.format(
                transcript=transcript,
                custom_context=custom_context
            )

        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",  # fast/cheap for extraction
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise data extraction assistant. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                # IMPORTANT: correct parameter name for this SDK
                max_completion_tokens=9000
            )

            choice = response.choices[0]
            content = (choice.message.content or "").strip()

            if not content:
                # Return structured diagnostic so callers can log accurately
                return {
                    "error": "empty_completion",
                    "finish_reason": getattr(choice, "finish_reason", None),
                    "usage": getattr(response, "usage", None)
                }

            result_text = self._clean_json_text(content)

            return json.loads(result_text)

        except json.JSONDecodeError as e:
            # Provide raw text for debugging
            return {
                "error": "json_parse_failed",
                "details": str(e),
                "raw": locals().get("result_text", "")
            }
        except Exception as e:
            return {"error": str(e)}

    def analyze_image(self, image_bytes: bytes, prompt: str, model: str = "gpt-4o") -> Dict:
        """
        Analyze an image using a vision-capable model.
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                        ]
                    }
                ],
                # IMPORTANT: correct parameter name
                max_completion_tokens=9000
            )

            choice = response.choices[0]
            content = (choice.message.content or "").strip()
            if not content:
                return {
                    "error": "empty_completion",
                    "finish_reason": getattr(choice, "finish_reason", None),
                    "usage": getattr(response, "usage", None)
                }

            result_text = self._clean_json_text(content)
            return json.loads(result_text)

        except json.JSONDecodeError as e:
            return {"error": "json_parse_failed", "details": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def answer_query(self, query: str, context: Dict, system_prompt: str = "") -> str:
        """
        Answer natural language questions using provided context.
        """
        if not system_prompt:
            system_prompt = (
                "You are a helpful personal assistant with access to the user's personal data. "
                "Answer questions concisely and accurately."
            )

        context_str = json.dumps(context, indent=2)

        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"AVAILABLE CONTEXT:\n{context_str}\n\n"
                            f"USER QUESTION:\n{query}\n\n"
                            "Provide a helpful, concise answer based on the available context."
                        )
                    }
                ],
                # IMPORTANT: correct parameter name
                max_completion_tokens=9000
            )
            return (response.choices[0].message.content or "").strip()

        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

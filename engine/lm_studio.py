"""
LM Studio API Client

Handles communication with LM Studio's MCP API endpoint.
Simplified from previous project:
- Removed MCP Memory extraction (replaced by awareness-thinking server)
- Removed chat_simple() (unified into single chat method)
- Single integration: mcp/awareness-thinking
"""

import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Fallback model if nothing is configured or loaded
FALLBACK_MODEL = "qwen/qwen3-30b-a3b-2507"


class LMStudioClient:
    """LM Studio MCP API Client"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1234,
        api_token: str = "",
        timeout: int = 300,
        selected_model: str = "",
    ):
        self.host = host
        self.port = port
        self.api_token = api_token
        self.timeout = timeout
        self.selected_model = selected_model  # User-selected model from config

        self.base_url = f"http://{host}:{port}"
        self.mcp_url = f"{self.base_url}/api/v1/chat"
        self.models_url = f"{self.base_url}/api/v1/models"

    def _get_headers(self) -> dict:
        """Build request headers"""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    # ========== Connection ==========

    def check_connection(self) -> dict:
        """Test connection to LM Studio"""
        try:
            response = requests.get(
                self.models_url,
                headers=self._get_headers(),
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                loaded = [m for m in models if m.get("loaded_instances")]
                return {
                    "status": "connected",
                    "total_models": len(models),
                    "loaded_models": len(loaded),
                    "loaded_model_names": [m["key"] for m in loaded],
                }
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}

        except requests.exceptions.ConnectionError:
            return {"status": "disconnected", "error": "Cannot connect to LM Studio"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_loaded_model(self) -> Optional[str]:
        """Get currently loaded model name (None if no model loaded)"""
        try:
            response = requests.get(
                self.models_url,
                headers=self._get_headers(),
                timeout=5,
            )

            if response.status_code == 200:
                for model in response.json().get("models", []):
                    if model.get("loaded_instances"):
                        return model.get("key", model["loaded_instances"][0]["id"])
        except Exception:
            pass
        return None

    def get_available_models(self) -> list[str]:
        """Get list of all available models in LM Studio"""
        try:
            response = requests.get(
                self.models_url,
                headers=self._get_headers(),
                timeout=5,
            )

            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m["key"] for m in models if "key" in m]
        except Exception:
            pass
        return []

    def get_model_info(self, model_key: str) -> dict:
        """Get detailed info for a specific model including max_context_length"""
        try:
            response = requests.get(
                self.models_url,
                headers=self._get_headers(),
                timeout=5,
            )

            if response.status_code == 200:
                models = response.json().get("models", [])
                for model in models:
                    if model.get("key") == model_key:
                        return {
                            "key": model.get("key", ""),
                            "max_context_length": model.get("max_context_length", 32000),
                            "architecture": model.get("architecture", ""),
                            "size": model.get("size", 0),
                        }
        except Exception as e:
            logger.warning(f"Failed to get model info: {e}")
        return {"max_context_length": 32000}  # fallback

    # ========== Chat ==========

    def chat(
        self,
        input_text: str,
        system_prompt: str,
        integrations: Optional[list[str]] = None,
        context_length: int = 32000,
        temperature: float = 0.7,
    ) -> tuple[str, dict]:
        """
        Send a message via LM Studio MCP API.

        Args:
            input_text: Full input text (with conversation history)
            system_prompt: Complete system prompt (with injected context)
            integrations: MCP integrations list (e.g. ["mcp/awareness-thinking"])
            context_length: Max context window
            temperature: Sampling temperature

        Returns:
            tuple: (response_text, metadata_dict)
        """
        # Get model — Priority: 1) selected_model from config, 2) loaded model, 3) fallback
        if self.selected_model:
            model = self.selected_model
            logger.info(f"Using configured model: {model}")
        else:
            model = self.get_loaded_model()
            if not model:
                model = FALLBACK_MODEL
                logger.info(f"No model configured/loaded, using fallback: {model}")
            else:
                logger.info(f"Using currently loaded model: {model}")

        payload = {
            "input": input_text,
            "model": model,
            "system_prompt": system_prompt,
            "integrations": integrations or [],
            "context_length": context_length,
            "temperature": temperature,
        }

        try:
            logger.info(f"MCP API call — Model: {model}, integrations: {integrations}")

            response = requests.post(
                self.mcp_url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                error_detail = response.text[:500] if response.text else "No details"
                logger.error(f"MCP API error: {response.status_code} — {error_detail}")
                return f"API Error: {response.status_code}", {"error": True}

            result = response.json()

            # Parse response output
            messages = []
            tool_calls = []

            for item in result.get("output", []):
                item_type = item.get("type")

                if item_type == "message":
                    content = item.get("content", "")
                    if content:
                        messages.append(content)

                elif item_type == "tool_call":
                    tool_calls.append({
                        "tool": item.get("tool"),
                        "arguments": item.get("arguments"),
                        "output": item.get("output"),
                    })

            response_text = "\n".join(messages).strip() or "No response"

            # Extract sequential thinking thoughts
            thoughts = []
            # デバッグ: tool_callsの中身を確認
            for tc in tool_calls:
                logger.debug(f"Tool call: tool={tc.get('tool')}, output_type={type(tc.get('output'))}, output={str(tc.get('output'))[:200]}")

            for tc in tool_calls:
                if tc.get("tool") == "sequentialthinking":
                    # argumentsに思考が入っている場合
                    args = tc.get("arguments", {})
                    if isinstance(args, dict) and args.get("thought"):
                        thoughts.append({
                            "number": args.get("thoughtNumber", 0),
                            "total": args.get("totalThoughts", 0),
                            "thought": args.get("thought", ""),
                        })
                        continue

                    # outputに結果が入っている場合
                    output = tc.get("output", "")
                    if isinstance(output, str):
                        try:
                            import json
                            output_data = json.loads(output)
                            if isinstance(output_data, dict):
                                thought = output_data.get("thought", "")
                                thought_num = output_data.get("thoughtNumber", 0)
                                total = output_data.get("totalThoughts", 0)
                                if thought:
                                    thoughts.append({
                                        "number": thought_num,
                                        "total": total,
                                        "thought": thought,
                                    })
                        except:
                            if output.strip():
                                thoughts.append({"thought": output, "number": 0, "total": 0})
                    elif isinstance(output, dict):
                        thought = output.get("thought", "")
                        thought_num = output.get("thoughtNumber", 0)
                        total = output.get("totalThoughts", 0)
                        if thought:
                            thoughts.append({
                                "number": thought_num,
                                "total": total,
                                "thought": thought,
                            })

            metadata = {
                "tool_calls": tool_calls,
                "thoughts": thoughts,
                "stats": result.get("stats", {}),
                "model": model,
            }

            logger.info(f"Response received: {len(response_text)} chars, "
                        f"{len(tool_calls)} tool calls, {len(thoughts)} thoughts")

            return response_text, metadata

        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            return "Request timed out", {"error": True, "timeout": True}
        except Exception as e:
            logger.error(f"MCP API exception: {e}")
            return f"Error: {str(e)}", {"error": True}

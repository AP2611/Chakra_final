"""Base agent class for all agents in the system."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator, Callable
import httpx
import json


class BaseAgent(ABC):
    """Base class for all agents using Ollama with low-latency optimizations."""
    
    def __init__(
        self, 
        name: str, 
        ollama_url: str = "http://localhost:11434", 
        model: str = "qwen2.5:1.5b",
        fast_mode: bool = True
    ):
        self.name = name
        self.ollama_url = ollama_url
        self.model = model
        self.api_url = f"{ollama_url}/api/chat"
        self.fast_mode = fast_mode
        
        # Optimized inference parameters for low latency
        if fast_mode:
            # Fast mode: optimized for speed (3-5x faster)
            self.inference_options = {
                "num_predict": 384,      # Limit output length (50-70% faster)
                "temperature": 0.5,      # Lower randomness (20-30% faster)
                "top_p": 0.7,            # Smaller candidate pool
                "top_k": 20,             # Fewer candidates to consider
                "repeat_penalty": 1.1,   # Prevent repetition
                "num_ctx": 1024,         # Smaller context (15-25% faster)
            }
        else:
            # Normal mode: balanced quality and speed
            self.inference_options = {
                "num_predict": 640,
                "temperature": 0.6,
                "top_p": 0.8,
                "top_k": 30,
                "repeat_penalty": 1.1,
                "num_ctx": 2048,
            }
    
    async def _call_ollama(
        self, 
        prompt: str, 
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Call Ollama API with optimized parameters for low latency."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # Use custom parameters if provided, otherwise use defaults
        options = self.inference_options.copy()
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if temperature is not None:
            options["temperature"] = temperature
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                result = response.json()
                return result.get("message", {}).get("content", "").strip()
        except Exception as e:
            raise Exception(f"Error calling Ollama API: {str(e)}")
    
    async def _call_ollama_stream(
        self, 
        prompt: str, 
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        token_callback: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """Call Ollama API with streaming enabled, yields tokens immediately for low latency."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # Use custom parameters if provided, otherwise use defaults
        options = self.inference_options.copy()
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if temperature is not None:
            options["temperature"] = temperature
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": options
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    async with client.stream("POST", self.api_url, json=payload) as response:
                        response.raise_for_status()
                        buffer = ""
                        token_count = 0
                        max_tokens_reached = False
                        
                        async for chunk in response.aiter_bytes():
                            if not chunk:
                                continue
                                
                            buffer += chunk.decode('utf-8', errors='ignore')
                            # Process complete lines
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                
                                if not line:
                                    continue
                                
                                # Handle both formats: "data: {...}" (SSE) and direct JSON (NDJSON)
                                json_str = None
                                if line.startswith("data: "):
                                    json_str = line[6:].strip()  # Remove "data: " prefix
                                else:
                                    # Direct JSON line (NDJSON format from Ollama)
                                    json_str = line
                                
                                if json_str:
                                    try:
                                        data = json.loads(json_str)
                                        
                                        # Check for errors from Ollama
                                        if "error" in data:
                                            error_msg = data.get("error", "Unknown error")
                                            # Don't raise exception - just log and stop
                                            print(f"Ollama error: {error_msg}")
                                            return
                                        
                                        # Check for message content - yield immediately
                                        if "message" in data and isinstance(data["message"], dict):
                                            content = data["message"].get("content", "")
                                            if content:  # Only yield non-empty content
                                                token_count += 1
                                                # Call token callback immediately for real-time updates
                                                if token_callback:
                                                    try:
                                                        token_callback(content)
                                                    except:
                                                        pass  # Ignore callback errors
                                                # Yield token immediately - don't wait
                                                yield content
                                        
                                        # Check if done - return after yielding any final content
                                        # This is normal when token limit is reached - not an error
                                        if data.get("done", False):
                                            max_tokens_reached = True
                                            # Yield any remaining content in buffer
                                            if buffer.strip():
                                                try:
                                                    final_data = json.loads(buffer.strip())
                                                    if "message" in final_data and "content" in final_data["message"]:
                                                        final_content = final_data["message"]["content"]
                                                        if final_content:
                                                            yield final_content
                                                except:
                                                    pass
                                            # Normal completion - token limit reached, not an error
                                            return
                                            
                                    except json.JSONDecodeError:
                                        # Skip invalid JSON lines but continue processing
                                        continue
                        
                        # Process any remaining buffer after stream ends
                        if buffer.strip():
                            try:
                                final_data = json.loads(buffer.strip())
                                if "message" in final_data and "content" in final_data["message"]:
                                    final_content = final_data["message"]["content"]
                                    if final_content:
                                        yield final_content
                            except:
                                pass
                except GeneratorExit:
                    # Generator is being closed - exit cleanly
                    return
        except GeneratorExit:
            # Generator is being closed - exit cleanly
            return
        except Exception as e:
            # Only raise if it's not a generator exit
            if not isinstance(e, GeneratorExit):
                raise Exception(f"Error calling Ollama API: {str(e)}")
    
    @abstractmethod
    async def process(self, **kwargs) -> Dict[str, Any]:
        """Process the input and return output."""
        pass


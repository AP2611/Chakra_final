"""
Test to diagnose why chatbot terminates with error when first LLM output exceeds token limit.
This test will:
1. Send prompts that should generate long responses
2. Track token counts and limits
3. Monitor when and why errors occur
4. Check if Ollama truncates or errors on token limit
"""

import asyncio
import httpx
import json
import time
from typing import Dict, List, Any

class ChatbotTokenLimitDiagnostic:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.events_received = []
        self.token_counts = []
        self.error_events = []
        
    async def check_backend_health(self) -> bool:
        """Check if backend is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.backend_url}/health")
                return response.status_code == 200
        except Exception as e:
            print(f"❌ Backend health check failed: {e}")
            return False
    
    async def test_chatbot_response(self, prompt: str, expected_tokens: int = None):
        """Test chatbot response and track token limits."""
        print(f"\n{'='*80}")
        print(f"TEST: Chatbot Token Limit Diagnostic")
        print(f"{'='*80}")
        print(f"\nPrompt: {prompt}")
        if expected_tokens:
            print(f"Expected tokens: ~{expected_tokens}")
        print(f"\n🔍 Tracking token counts and errors...\n")
        
        # Track state
        token_count = 0
        response_content = ""
        error_occurred = False
        error_message = ""
        start_time = time.time()
        first_token_time = None
        
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                # Start SSE stream
                async with client.stream(
                    "POST",
                    f"{self.backend_url}/process-stream",
                    json={
                        "task": prompt,
                        "context": "",
                        "use_rag": False,
                        "is_code": False  # Chatbot mode
                    },
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    response.raise_for_status()
                    
                    print("📡 Connected to SSE stream\n")
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        if line.startswith("data: "):
                            json_str = line[6:]  # Remove "data: " prefix
                            try:
                                data = json.loads(json_str)
                                event_type = data.get("type", "unknown")
                                
                                # Track event
                                self.events_received.append({
                                    "type": event_type,
                                    "data": data,
                                    "timestamp": time.time()
                                })
                                
                                # Track tokens
                                if event_type == "token":
                                    token = data.get("token", "")
                                    if token:
                                        response_content += token
                                        token_count += 1
                                        
                                        if first_token_time is None:
                                            first_token_time = time.time()
                                            print(f"✅ First token received at {first_token_time - start_time:.2f}s")
                                        
                                        # Track token count from backend if provided
                                        backend_token_count = data.get("token_count", 0)
                                        if backend_token_count > 0:
                                            self.token_counts.append({
                                                "count": backend_token_count,
                                                "timestamp": time.time(),
                                                "source": "token_event"
                                            })
                                        
                                        # Log every 50 tokens
                                        if token_count % 50 == 0:
                                            print(f"   📊 Tokens: {token_count} (content length: {len(response_content)})")
                                
                                if event_type == "improved_token":
                                    token = data.get("token", "")
                                    if token:
                                        response_content += token
                                        backend_token_count = data.get("token_count", 0)
                                        if backend_token_count > 0:
                                            self.token_counts.append({
                                                "count": backend_token_count,
                                                "timestamp": time.time(),
                                                "source": "improved_token_event"
                                            })
                                
                                if event_type == "improved":
                                    improved_output = data.get("improved_output") or data.get("solution")
                                    if improved_output:
                                        response_content = improved_output
                                        backend_token_count = data.get("token_count", 0)
                                        if backend_token_count > 0:
                                            print(f"   📊 Improved output token count: {backend_token_count}")
                                
                                if event_type == "error":
                                    error_occurred = True
                                    error_message = data.get("message", "Unknown error")
                                    self.error_events.append({
                                        "message": error_message,
                                        "timestamp": time.time(),
                                        "token_count_at_error": token_count,
                                        "content_length": len(response_content)
                                    })
                                    print(f"\n❌ ERROR RECEIVED:")
                                    print(f"   Message: {error_message}")
                                    print(f"   Token count: {token_count}")
                                    print(f"   Content length: {len(response_content)}")
                                    break
                                
                                if event_type == "end":
                                    print(f"\n✅ Stream completed successfully")
                                    break
                                
                            except json.JSONDecodeError as e:
                                print(f"⚠️  Failed to parse JSON: {e}")
                                print(f"   Line: {line[:100]}")
                        
        except httpx.TimeoutException:
            print(f"\n❌ Request timed out after 180 seconds")
            error_occurred = True
            error_message = "Request timeout"
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            error_occurred = True
            error_message = str(e)
            import traceback
            traceback.print_exc()
        
        # Analyze results
        elapsed_time = time.time() - start_time
        self.analyze_results(
            token_count, 
            len(response_content), 
            error_occurred, 
            error_message,
            elapsed_time,
            first_token_time
        )
    
    def analyze_results(
        self, 
        token_count: int, 
        content_length: int,
        error_occurred: bool,
        error_message: str,
        elapsed_time: float,
        first_token_time: float
    ):
        """Analyze the collected data to identify token limit issues."""
        print(f"\n{'='*80}")
        print(f"ANALYSIS")
        print(f"{'='*80}\n")
        
        # Count event types
        event_counts = {}
        for event in self.events_received:
            event_type = event["type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        print(f"📊 Event Summary:")
        for event_type, count in sorted(event_counts.items()):
            print(f"   {event_type}: {count}")
        
        print(f"\n📝 Token Analysis:")
        print(f"   Total tokens received: {token_count}")
        print(f"   Content length: {content_length} characters")
        print(f"   Average chars per token: {content_length / token_count if token_count > 0 else 0:.2f}")
        
        if self.token_counts:
            max_backend_count = max(tc["count"] for tc in self.token_counts)
            print(f"   Max backend token count: {max_backend_count}")
        
        # Check token limits
        # Code: 384/640, Chatbot: 512/1024
        fast_mode_limit = 512  # Chatbot fast mode
        normal_mode_limit = 1024  # Chatbot normal mode
        
        print(f"\n🔍 Token Limit Analysis:")
        print(f"   Fast mode limit: {fast_mode_limit}")
        print(f"   Normal mode limit: {normal_mode_limit}")
        print(f"   Tokens received: {token_count}")
        
        if token_count >= fast_mode_limit:
            print(f"   ⚠️  Token count exceeds fast mode limit!")
        if token_count >= normal_mode_limit:
            print(f"   ⚠️  Token count exceeds normal mode limit!")
        
        if error_occurred:
            print(f"\n❌ ERROR ANALYSIS:")
            print(f"   Error message: {error_message}")
            print(f"   Token count at error: {token_count}")
            print(f"   Content length at error: {content_length}")
            
            # Check if error is related to token limit
            error_lower = error_message.lower()
            if any(keyword in error_lower for keyword in ["token", "limit", "exceed", "truncate", "max"]):
                print(f"\n🚨 ISSUE IDENTIFIED: Error is likely related to token limit!")
                print(f"   The backend or Ollama may be terminating when token limit is reached.")
            elif "timeout" in error_lower:
                print(f"\n🚨 ISSUE IDENTIFIED: Request timed out!")
                print(f"   The response may be too long and taking too much time.")
            else:
                print(f"\n⚠️  Error may not be directly related to token limit.")
                print(f"   Check backend logs for more details.")
        else:
            print(f"\n✅ No errors occurred")
        
        print(f"\n⏱️  Timing Analysis:")
        if first_token_time:
            time_to_first_token = first_token_time - (time.time() - elapsed_time)
            print(f"   Time to first token: {time_to_first_token:.2f}s")
        print(f"   Total elapsed time: {elapsed_time:.2f}s")
        print(f"   Tokens per second: {token_count / elapsed_time if elapsed_time > 0 else 0:.2f}")
        
        # Check for abrupt termination
        if error_occurred and token_count > 0:
            # Check if we were receiving tokens right before error
            last_token_event = None
            for event in reversed(self.events_received):
                if event["type"] == "token":
                    last_token_event = event
                    break
            
            if last_token_event:
                time_before_error = elapsed_time - last_token_event["timestamp"]
                if time_before_error < 1.0:  # Error within 1 second of last token
                    print(f"\n🚨 ISSUE IDENTIFIED: Abrupt termination!")
                    print(f"   Error occurred {time_before_error:.2f}s after last token")
                    print(f"   This suggests the stream was cut off, possibly due to token limit.")
        
        print(f"\n{'='*80}\n")


async def main():
    diagnostic = ChatbotTokenLimitDiagnostic()
    
    # Check backend health
    print("🔍 Checking backend health...")
    if not await diagnostic.check_backend_health():
        print("❌ Backend is not running. Please start it first.")
        return
    
    print("✅ Backend is healthy\n")
    
    # Test 1: Long response prompt (should exceed token limit)
    print("\n" + "="*80)
    print("TEST 1: Long Response (Should Exceed Token Limit)")
    print("="*80)
    await diagnostic.test_chatbot_response(
        "Write a detailed explanation of how machine learning works, including supervised learning, unsupervised learning, and reinforcement learning. Provide examples for each type and explain the differences between them. Also explain neural networks, deep learning, and their applications in real-world scenarios.",
        expected_tokens=600  # Should exceed 512 fast mode limit
    )
    
    await asyncio.sleep(2)
    
    # Test 2: Very long response prompt
    print("\n" + "="*80)
    print("TEST 2: Very Long Response (Should Definitely Exceed Token Limit)")
    print("="*80)
    await diagnostic.test_chatbot_response(
        "Write a comprehensive guide to web development covering HTML, CSS, JavaScript, React, Node.js, databases, APIs, authentication, deployment, and best practices. Include code examples for each topic and explain how they all work together to build modern web applications.",
        expected_tokens=800  # Should exceed both limits
    )
    
    await asyncio.sleep(2)
    
    # Test 3: Medium response (should be within limit)
    print("\n" + "="*80)
    print("TEST 3: Medium Response (Should Be Within Limit)")
    print("="*80)
    await diagnostic.test_chatbot_response(
        "Explain what Python is and list 5 common use cases.",
        expected_tokens=50  # Should be well within limit
    )


if __name__ == "__main__":
    asyncio.run(main())



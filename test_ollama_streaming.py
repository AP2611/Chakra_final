"""Test Ollama streaming directly to identify the issue."""
import asyncio
import httpx
import json
import time

async def test_ollama_streaming():
    """Test if Ollama is actually streaming tokens."""
    print("Testing Ollama streaming directly...")
    print("="*80)
    
    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [
            {"role": "user", "content": "Write a Python function to add two numbers. Keep it short."}
        ],
        "stream": True,
        "options": {
            "num_predict": 100,
            "temperature": 0.5
        }
    }
    
    start = time.time()
    first_token_time = None
    token_count = 0
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", "http://localhost:11434/api/chat", json=payload) as response:
                print(f"Response status: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                print("\nStreaming tokens...\n")
                
                buffer = ""
                chunk_count = 0
                async for chunk in response.aiter_bytes():
                    chunk_count += 1
                    chunk_time = time.time()
                    chunk_str = chunk.decode('utf-8', errors='ignore')
                    buffer += chunk_str
                    
                    print(f"Chunk {chunk_count} ({len(chunk)} bytes, {(chunk_time - start)*1000:.0f}ms): {repr(chunk_str[:100])}")
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                            
                        # Try both formats: "data: {...}" and direct JSON
                        json_str = None
                        if line.startswith("data: "):
                            json_str = line[6:].strip()
                        else:
                            json_str = line
                        
                        if json_str:
                            try:
                                data = json.loads(json_str)
                                
                                # Check for done flag
                                if data.get("done", False):
                                    print(f"\n✓ Stream complete. Total tokens: {token_count}")
                                    print(f"Total time: {(time.time() - start)*1000:.2f}ms")
                                    return
                                
                                # Check for message content
                                if "message" in data:
                                    content = data["message"].get("content", "")
                                    if content:
                                        token_count += 1
                                        if first_token_time is None:
                                            first_token_time = chunk_time
                                            ttft = (first_token_time - start) * 1000
                                            print(f"\n⏱  First token received: {ttft:.2f}ms")
                                        
                                        elapsed = (chunk_time - start) * 1000
                                        print(f"Token {token_count} ({elapsed:.0f}ms): {repr(content[:50])}")
                                        
                                        if token_count >= 20:  # Limit output
                                            print(f"\n... (showing first 20 tokens)")
                                            print(f"Continuing to collect all tokens...")
                                
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e}")
                                print(f"Line: {line[:100]}")
                
                # Check if we have any remaining buffer
                if buffer:
                    print(f"\nRemaining buffer: {repr(buffer[:200])}")
        
        if first_token_time:
            print(f"\n✓ Streaming test complete")
            print(f"Time to first token: {(first_token_time - start)*1000:.2f}ms")
            print(f"Total tokens: {token_count}")
        else:
            print(f"\n✗ No tokens received!")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ollama_streaming())


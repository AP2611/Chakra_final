"""Test Agni streaming directly."""
import asyncio
import sys
sys.path.insert(0, 'Chakra/backend')

from agents.agni import Agni

async def test_agni_streaming():
    """Test if Agni's streaming works."""
    print("Testing Agni streaming...")
    print("="*80)
    
    agni = Agni(fast_mode=True)
    
    prompt = "Write a simple hello function"
    system = "You are Agni, an expert optimizer."
    
    print(f"Prompt: {prompt}")
    print(f"System: {system}")
    print("\nStreaming tokens...\n")
    
    import time
    start = time.time()
    token_count = 0
    first_token_time = None
    
    try:
        async for token in agni._call_ollama_stream(prompt, system, max_tokens=50):
            current_time = time.time()
            token_count += 1
            
            if first_token_time is None:
                first_token_time = current_time
                ttft = (first_token_time - start) * 1000
                print(f"⏱  First token: {ttft:.2f}ms")
            
            elapsed = (current_time - start) * 1000
            print(f"Token {token_count} ({elapsed:.0f}ms): {repr(token[:50])}")
            
            if token_count >= 10:
                print(f"\n... (showing first 10 tokens)")
                break
        
        if token_count > 0:
            print(f"\n✓ Streaming works! Received {token_count} tokens")
        else:
            print(f"\n✗ No tokens received!")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agni_streaming())


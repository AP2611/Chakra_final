"""Temporary test to verify Agni streaming works in isolation."""
import asyncio
import sys
sys.path.insert(0, 'Chakra/backend')

from orchestrator import Orchestrator

async def test_agni_in_api_context():
    """Test if Agni streaming works when called from API context."""
    o = Orchestrator(fast_mode=True)
    
    prompt = "Original Task: Write hello\n--- Original Output ---\nprint('hello')\n--- Critique and Issues Found ---\nMissing error handling\n--- Your Task ---\nRewrite the solution addressing ALL issues mentioned in the critique."
    system = "You are Agni, an expert optimizer."
    
    print("Testing Agni in API-like context...")
    print("="*80)
    
    count = 0
    tokens_received = []
    
    try:
        async for token in o.agni._call_ollama_stream(prompt, system, max_tokens=100):
            count += 1
            tokens_received.append(token)
            if count <= 10:
                print(f"Token {count}: {repr(token[:50])}")
            if count >= 20:
                break
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTotal tokens: {count}")
    print(f"Tokens received: {len(tokens_received)}")
    
    if count == 0:
        print("\n❌ PROBLEM: No tokens received from Agni stream")
    else:
        print(f"\n✓ SUCCESS: {count} tokens received")

if __name__ == "__main__":
    asyncio.run(test_agni_in_api_context())


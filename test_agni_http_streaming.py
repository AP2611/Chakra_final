"""Test Agni streaming via HTTP to see exact issue."""
import requests
import json
import time

BACKEND_URL = "http://localhost:8000"

def test_agni_http():
    """Test Agni streaming via HTTP endpoint."""
    print("Testing Agni streaming via HTTP...")
    print("="*80)
    
    start = time.time()
    
    response = requests.post(
        f"{BACKEND_URL}/process-stream",
        json={
            "task": "Write hello world",
            "use_rag": False,
            "is_code": True
        },
        stream=True,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"✗ HTTP {response.status_code}")
        return
    
    print("Events received:")
    print("-" * 80)
    
    improved_tokens = []
    events = []
    
    for line in response.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                event_type = data.get("type")
                elapsed = time.time() - start
                events.append((elapsed, event_type))
                
                if event_type == "improved_token":
                    token = data.get("token", "")
                    improved_tokens.append((elapsed, token))
                    if len(improved_tokens) <= 5:
                        print(f"[{elapsed:6.2f}s] improved_token: {repr(token[:50])}")
                elif event_type in ["improving_started", "first_response_complete", "improved", "end"]:
                    print(f"[{elapsed:6.2f}s] {event_type}")
                
                if event_type in ["end", "complete"]:
                    break
            except Exception as e:
                print(f"Error: {e}")
    
    response.close()
    
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"Total events: {len(events)}")
    print(f"Improved tokens: {len(improved_tokens)}")
    
    if len(improved_tokens) == 0:
        print("\n❌ PROBLEM IDENTIFIED:")
        print("   No improved_token events received via HTTP")
        print("   But they work when called directly")
        print("   This means the generator yields aren't reaching HTTP client")
        print("\n   Possible causes:")
        print("   1. FastAPI StreamingResponse buffering")
        print("   2. Generator not being consumed properly")
        print("   3. Events being lost in nested generator")
    else:
        print(f"\n✓ SUCCESS: {len(improved_tokens)} improved tokens received")

if __name__ == "__main__":
    test_agni_http()


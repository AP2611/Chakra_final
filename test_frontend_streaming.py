"""Test frontend streaming to see what events are actually received."""
import requests
import json
import time

BACKEND_URL = "http://localhost:8000"

def test_frontend_perspective():
    """Test what the frontend would receive."""
    print("="*80)
    print("FRONTEND STREAMING PERSPECTIVE TEST")
    print("="*80)
    print("\nSimulating what frontend receives...\n")
    
    start = time.time()
    
    response = requests.post(
        f"{BACKEND_URL}/process-stream",
        json={
            "task": "Write a Python function to add two numbers",
            "use_rag": False,
            "is_code": True
        },
        stream=True,
        timeout=60
    )
    
    if response.status_code != 200:
        print(f"✗ HTTP Error: {response.status_code}")
        return
    
    print("Event Sequence (as frontend would see):")
    print("-" * 80)
    
    token_events = []
    improved_token_events = []
    other_events = []
    
    for line in response.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                event_type = data.get("type")
                elapsed = time.time() - start
                
                if event_type == "token":
                    token_events.append((elapsed, data.get("token", "")))
                    if len(token_events) <= 3:
                        print(f"[{elapsed:6.2f}s] token: {repr(data.get('token', '')[:30])}")
                elif event_type == "improved_token":
                    improved_token_events.append((elapsed, data.get("token", "")))
                    if len(improved_token_events) <= 10:
                        print(f"[{elapsed:6.2f}s] improved_token: {repr(data.get('token', '')[:30])}")
                else:
                    other_events.append((elapsed, event_type))
                    print(f"[{elapsed:6.2f}s] {event_type}")
                
                if event_type in ["end", "complete"]:
                    break
                    
            except Exception as e:
                print(f"Error parsing: {e}")
    
    response.close()
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total token events: {len(token_events)}")
    print(f"Total improved_token events: {len(improved_token_events)}")
    print(f"Other events: {len(other_events)}")
    
    if improved_token_events:
        first_improved = improved_token_events[0][0]
        print(f"\n✓ First improved_token at: {first_improved:.2f}s")
        print(f"✓ Total improved tokens: {len(improved_token_events)}")
    else:
        print(f"\n❌ NO improved_token events received!")
        print(f"   This is why the frontend shows 'generating' - no tokens to display")
    
    # Check event order
    print(f"\n{'='*80}")
    print("EVENT ORDER ANALYSIS")
    print(f"{'='*80}")
    
    all_events = sorted(token_events + improved_token_events + [(t, e) for t, e in other_events], key=lambda x: x[0])
    
    improving_started_time = None
    first_improved_time = None
    
    for elapsed, event_type in other_events:
        if event_type == "improving_started":
            improving_started_time = elapsed
        if event_type == "first_response_complete":
            print(f"  First response complete at: {elapsed:.2f}s")
    
    if improving_started_time:
        print(f"  Improving started at: {improving_started_time:.2f}s")
    
    if improved_token_events:
        first_improved_time = improved_token_events[0][0]
        print(f"  First improved_token at: {first_improved_time:.2f}s")
        if improving_started_time:
            delay = first_improved_time - improving_started_time
            print(f"  Delay after improving_started: {delay:.2f}s")
            if delay > 10:
                print(f"  ⚠️  WARNING: Long delay ({delay:.2f}s) - frontend will show 'generating'")
    else:
        print(f"  ❌ No improved_token events - frontend stuck on 'generating'")

if __name__ == "__main__":
    test_frontend_perspective()


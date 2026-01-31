"""Test Agni streaming directly in the API context to debug the issue."""
import asyncio
import sys
sys.path.insert(0, 'Chakra/backend')

from api import generate_process_events, TaskRequest

async def test_agni_in_context():
    """Test Agni streaming within the actual API context."""
    print("Testing Agni streaming in API context...")
    print("="*80)
    
    request = TaskRequest(task='Write hello world', use_rag=False, is_code=True)
    
    improved_tokens = []
    events_received = []
    
    async for event in generate_process_events(request):
        if 'improved_token' in event:
            improved_tokens.append(event)
            if len(improved_tokens) <= 5:
                # Parse and show token
                try:
                    import json
                    data = json.loads(event.split('data: ')[1])
                    print(f"Improved token {len(improved_tokens)}: {repr(data.get('token', '')[:50])}")
                except:
                    print(f"Improved token {len(improved_tokens)}: {event[:100]}")
        else:
            # Track other events
            try:
                import json
                data = json.loads(event.split('data: ')[1])
                event_type = data.get('type')
                events_received.append(event_type)
                if event_type in ['improving_started', 'first_response_complete', 'improved', 'end']:
                    print(f"Event: {event_type}")
            except:
                pass
        
        if len(improved_tokens) >= 10 or len(events_received) > 30:
            break
    
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"Improved tokens received: {len(improved_tokens)}")
    print(f"Total events: {len(events_received)}")
    
    if len(improved_tokens) == 0:
        print("\n❌ PROBLEM: No improved_token events in API context!")
        print("   But Agni streaming works when called directly.")
        print("   This suggests the nested generator isn't yielding properly.")
    else:
        print(f"\n✓ SUCCESS: {len(improved_tokens)} improved tokens received")

if __name__ == "__main__":
    asyncio.run(test_agni_in_context())


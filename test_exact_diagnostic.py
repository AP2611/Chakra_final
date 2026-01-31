"""Exact diagnostic test to see what events are sent and received."""
import time
import requests
import json
import sys

BACKEND_URL = "http://localhost:8000"

def test_exact_diagnostic():
    """Test exact flow and show detailed event information."""
    print("="*80)
    print("EXACT FLOW DIAGNOSTIC TEST")
    print("="*80)
    
    test_prompt = "Create a Python function that calculates factorial."
    
    print(f"\nTest Prompt: {test_prompt}")
    print("\nTracing ALL events from backend...")
    print("-"*80)
    
    events_log = []
    improved_token_found = False
    improved_found = False
    end_found = False
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/process-stream",
            json={
                "task": test_prompt,
                "use_rag": False,
                "is_code": True
            },
            stream=True,
            timeout=180
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
        
        print("\n[EVENTS RECEIVED]")
        print("-"*80)
        
        for line_num, line in enumerate(response.iter_lines(decode_unicode=True), 1):
            if not line or not line.startswith("data: "):
                continue
            
            try:
                data = json.loads(line[6:])
                event_type = data.get("type")
                elapsed = time.time() - start_time
                
                events_log.append({
                    'line': line_num,
                    'type': event_type,
                    'data': data,
                    'time': elapsed
                })
                
                # Show key events
                if event_type in ["start", "improving_started", "improved_token", "improved", "end", "complete"]:
                    print(f"[{elapsed:6.2f}s] {event_type}")
                    
                    if event_type == "improved_token":
                        improved_token_found = True
                        token = data.get("token", "")
                        print(f"         Token length: {len(token)} chars")
                        print(f"         Token preview: {repr(token[:100])}")
                        print(f"         Has iteration: {data.get('iteration')}")
                    
                    elif event_type == "improved":
                        improved_found = True
                        improved_output = data.get("improved_output", "")
                        solution = data.get("solution", "")
                        print(f"         improved_output length: {len(improved_output)} chars")
                        print(f"         solution length: {len(solution)} chars")
                        print(f"         improved_output preview: {repr(improved_output[:100])}")
                        print(f"         solution preview: {repr(solution[:100])}")
                    
                    elif event_type in ["end", "complete"]:
                        end_found = True
                        final_solution = data.get("final_solution", "")
                        print(f"         final_solution length: {len(final_solution)} chars")
                        if final_solution:
                            print(f"         final_solution preview: {repr(final_solution[:100])}")
                
                if event_type in ["end", "complete"]:
                    break
                    
            except json.JSONDecodeError as e:
                print(f"[Line {line_num}] JSON decode error: {e}")
                continue
            except Exception as e:
                print(f"[Line {line_num}] Error: {e}")
                continue
        
        response.close()
        
        # Analysis
        print("\n" + "="*80)
        print("ANALYSIS")
        print("="*80)
        
        print(f"\nTotal events: {len(events_log)}")
        event_types = set(e['type'] for e in events_log)
        print(f"Event types received: {sorted(event_types)}")
        
        # Check for improved_token
        print("\n" + "-"*80)
        print("improved_token EVENT CHECK:")
        print("-"*80)
        if improved_token_found:
            print("✓ improved_token event IS being sent by backend")
            improved_token_events = [e for e in events_log if e['type'] == 'improved_token']
            print(f"  Found {len(improved_token_events)} improved_token event(s)")
            for event in improved_token_events:
                token = event['data'].get('token', '')
                print(f"  - Token length: {len(token)} chars")
                print(f"  - This will go to onToken callback in api.ts")
                print(f"  - It will NOT go to onEvent callback")
                print(f"  - CodeAssistant improved_token handler (line 120) will NEVER RUN")
        else:
            print("✗ improved_token event NOT being sent by backend")
            print("  → Check backend code at api.py line 252")
        
        # Check for improved
        print("\n" + "-"*80)
        print("improved EVENT CHECK:")
        print("-"*80)
        if improved_found:
            print("✓ improved event IS being sent by backend")
            improved_events = [e for e in events_log if e['type'] == 'improved']
            print(f"  Found {len(improved_events)} improved event(s)")
            for event in improved_events:
                data = event['data']
                improved_output = data.get('improved_output', '')
                solution = data.get('solution', '')
                final_output = improved_output or solution
                
                print(f"  - improved_output length: {len(improved_output)} chars")
                print(f"  - solution length: {len(solution)} chars")
                print(f"  - This will go to onEvent callback in api.ts")
                print(f"  - CodeAssistant improved handler (line 141) SHOULD RUN")
                
                if final_output:
                    print(f"  ✓ Has valid output data - handler should work")
                else:
                    print(f"  ✗ NO output data - handler will NOT work")
        else:
            print("✗ improved event NOT being sent by backend")
            print("  → Check backend code at api.py line 255")
        
        # Check event sequence
        print("\n" + "-"*80)
        print("EVENT SEQUENCE:")
        print("-"*80)
        
        key_events = ['improving_started', 'improved_token', 'improved', 'end', 'complete']
        sequence = []
        for event in events_log:
            if event['type'] in key_events:
                sequence.append((event['type'], event['time']))
        
        for i, (event_type, event_time) in enumerate(sequence):
            print(f"  {i+1}. [{event_time:6.2f}s] {event_type}")
        
        # Final diagnosis
        print("\n" + "="*80)
        print("DIAGNOSIS")
        print("="*80)
        
        issues = []
        
        if not improved_token_found:
            issues.append("❌ improved_token events NOT being sent")
            issues.append("   → Backend should send at api.py:252")
        else:
            issues.append("✓ improved_token events ARE being sent")
            issues.append("   ⚠️  BUT: They go to onToken, not onEvent")
            issues.append("   ⚠️  CodeAssistant handler in onEvent will NEVER RUN")
        
        if not improved_found:
            issues.append("❌ improved events NOT being sent")
        else:
            issues.append("✓ improved events ARE being sent")
            improved_events = [e for e in events_log if e['type'] == 'improved']
            if improved_events:
                data = improved_events[0]['data']
                if data.get('improved_output') or data.get('solution'):
                    issues.append("✓ improved event has valid data")
                else:
                    issues.append("❌ improved event has NO data")
        
        if issues:
            print("\nISSUES FOUND:")
            for issue in issues:
                print(f"  {issue}")
        
        print("\n" + "="*80)
        print("RECOMMENDED FIX")
        print("="*80)
        
        if improved_token_found:
            print("\nSince improved_token events ARE being sent but go to onToken:")
            print("  → Fix api.ts to also call onEvent for improved_token events")
            print("  → This will allow CodeAssistant handler to set phase flag")
        
        if improved_found:
            improved_events = [e for e in events_log if e['type'] == 'improved']
            if improved_events and (improved_events[0]['data'].get('improved_output') or improved_events[0]['data'].get('solution')):
                print("\nSince improved events ARE being sent with valid data:")
                print("  → CodeAssistant improved handler (line 141) SHOULD work")
                print("  → But verify it's actually running (add console.log)")
        
        return {
            'improved_token_found': improved_token_found,
            'improved_found': improved_found,
            'end_found': end_found,
            'events_log': events_log,
            'issues': issues
        }
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    try:
        result = test_exact_diagnostic()
        sys.exit(0 if result and not result.get('issues') else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


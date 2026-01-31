"""Thorough test that simulates frontend behavior with real-life example."""
import time
import requests
import json
import sys
from typing import Dict, List, Optional

BACKEND_URL = "http://localhost:8000"

class FrontendSimulator:
    """Simulates exactly how the frontend processes events."""
    
    def __init__(self):
        self.events_received = []
        self.tokens_received = []
        self.onToken_calls = []
        self.onEvent_calls = []
        
        # Simulate frontend state
        self.isInImprovementPhase = False
        self.currentFirstCode = ''
        self.currentRefinedCode = ''
        self.refinedCode_state = ''  # Simulated React state
        self.firstGeneratedCode_state = ''  # Simulated React state
        
    def simulate_api_ts_processLine(self, data: Dict):
        """Simulate exactly how api.ts processLine works."""
        event_type = data.get('type')
        
        # Simulate api.ts line 89-95: Token events go to onToken
        if (event_type == 'token' or event_type == 'improved_token') and data.get('token'):
            token = data.get('token', '')
            self.tokens_received.append({
                'type': event_type,
                'token': token,
                'time': time.time()
            })
            # Call onToken callback
            self.onToken(token, event_type)
        else:
            # Simulate api.ts line 96-101: Other events go to onEvent
            self.onEvent(data)
    
    def onToken(self, token: str, event_type: str):
        """Simulate CodeAssistant onToken callback."""
        self.onToken_calls.append({
            'token': token,
            'type': event_type,
            'isInImprovementPhase': self.isInImprovementPhase,
            'time': time.time()
        })
        
        # Simulate CodeAssistant.tsx line 73-83
        if self.isInImprovementPhase:
            # In improvement phase - update refined code
            self.currentRefinedCode += token
            self.refinedCode_state = self.currentRefinedCode
            print(f"  [onToken] {event_type} → refinedCode += token ({len(token)} chars)")
            print(f"           isInImprovementPhase: {self.isInImprovementPhase}")
            print(f"           refinedCode_state length: {len(self.refinedCode_state)}")
        else:
            # Still in first generation phase
            self.currentFirstCode += token
            self.firstGeneratedCode_state = self.currentFirstCode
            print(f"  [onToken] {event_type} → firstCode += token ({len(token)} chars) ⚠️ WRONG!")
            print(f"           isInImprovementPhase: {self.isInImprovementPhase}")
            print(f"           firstCode_state length: {len(self.firstGeneratedCode_state)}")
    
    def onEvent(self, data: Dict):
        """Simulate CodeAssistant onEvent callback."""
        event_type = data.get('type')
        self.onEvent_calls.append({
            'type': event_type,
            'data': data,
            'time': time.time()
        })
        
        # Simulate CodeAssistant.tsx event handlers
        if event_type == 'improving_started':
            # Line 112-117
            self.isInImprovementPhase = True
            self.currentRefinedCode = ''
            self.refinedCode_state = ''
            print(f"  [onEvent] improving_started → isInImprovementPhase = true")
        
        elif event_type == 'improved_token':
            # Line 120-139
            print(f"  [onEvent] improved_token handler called")
            if not self.isInImprovementPhase:
                self.isInImprovementPhase = True
                self.currentRefinedCode = ''
                self.refinedCode_state = ''
                print(f"           Set isInImprovementPhase = true")
            
            token = data.get('token', '')
            if token:
                self.currentRefinedCode += token
                self.refinedCode_state = self.currentRefinedCode
                print(f"           refinedCode += token ({len(token)} chars)")
                print(f"           refinedCode_state length: {len(self.refinedCode_state)}")
        
        elif event_type == 'improved':
            # Line 141-151
            print(f"  [onEvent] improved handler called")
            improved_output = data.get('improved_output', '')
            solution = data.get('solution', '')
            final_output = improved_output or solution
            
            print(f"           improved_output length: {len(improved_output)}")
            print(f"           solution length: {len(solution)}")
            print(f"           final_output length: {len(final_output)}")
            
            if final_output:
                self.refinedCode_state = final_output
                self.currentRefinedCode = final_output
                self.isInImprovementPhase = False
                print(f"           ✓ Set refinedCode_state to {len(final_output)} chars")
            else:
                print(f"           ✗ NO output data!")

def test_thorough_frontend_simulation():
    """Test with real-life example and simulate frontend behavior."""
    print("="*80)
    print("THOROUGH FRONTEND SIMULATION TEST")
    print("="*80)
    
    # Real-life test prompt
    test_prompt = "Create a Python function that takes a list of numbers and returns the sum of all even numbers. Include error handling, type hints, and docstring."
    
    print(f"\nTest Prompt: {test_prompt}")
    print("\nSimulating frontend behavior...")
    print("="*80)
    
    simulator = FrontendSimulator()
    
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
        
        print("\n[PROCESSING EVENTS AS FRONTEND WOULD]")
        print("-"*80)
        
        for line_num, line in enumerate(response.iter_lines(decode_unicode=True), 1):
            if not line or not line.startswith("data: "):
                continue
            
            try:
                data = json.loads(line[6:])
                event_type = data.get("type")
                elapsed = time.time() - start_time
                
                simulator.events_received.append({
                    'line': line_num,
                    'type': event_type,
                    'data': data,
                    'time': elapsed
                })
                
                # Show key events
                if event_type in ["improving_started", "improved_token", "improved", "end", "complete"]:
                    print(f"\n[{elapsed:6.2f}s] Event: {event_type}")
                
                # Simulate api.ts processLine
                simulator.simulate_api_ts_processLine(data)
                
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
        print("FINAL STATE ANALYSIS")
        print("="*80)
        
        print(f"\nFrontend State:")
        print(f"  isInImprovementPhase: {simulator.isInImprovementPhase}")
        print(f"  firstGeneratedCode_state length: {len(simulator.firstGeneratedCode_state)}")
        print(f"  refinedCode_state length: {len(simulator.refinedCode_state)}")
        
        print(f"\nEvents Processed:")
        print(f"  Total events: {len(simulator.events_received)}")
        print(f"  onToken calls: {len(simulator.onToken_calls)}")
        print(f"  onEvent calls: {len(simulator.onEvent_calls)}")
        
        # Check for improved_token events
        improved_token_events = [e for e in simulator.events_received if e['type'] == 'improved_token']
        improved_events = [e for e in simulator.events_received if e['type'] == 'improved']
        
        print(f"\n  improved_token events: {len(improved_token_events)}")
        print(f"  improved events: {len(improved_events)}")
        
        # Check onToken calls for improved_token
        improved_token_onToken = [c for c in simulator.onToken_calls if c['type'] == 'improved_token']
        print(f"  improved_token → onToken calls: {len(improved_token_onToken)}")
        
        # Check onEvent calls for improved_token
        improved_token_onEvent = [c for c in simulator.onEvent_calls if c['type'] == 'improved_token']
        print(f"  improved_token → onEvent calls: {len(improved_token_onEvent)}")
        
        # Check onEvent calls for improved
        improved_onEvent = [c for c in simulator.onEvent_calls if c['type'] == 'improved']
        print(f"  improved → onEvent calls: {len(improved_onEvent)}")
        
        # Detailed analysis
        print("\n" + "="*80)
        print("DETAILED ANALYSIS")
        print("="*80)
        
        # Check if improved_token went to wrong place
        if improved_token_onToken:
            print("\n[ISSUE 1] improved_token events went to onToken:")
            for call in improved_token_onToken:
                was_in_phase = call['isInImprovementPhase']
                print(f"  - Token length: {len(call['token'])} chars")
                print(f"  - isInImprovementPhase was: {was_in_phase}")
                if not was_in_phase:
                    print(f"    ✗ PROBLEM: Token went to firstCode instead of refinedCode!")
        
        # Check if improved_token handler was called
        if improved_token_events and not improved_token_onEvent:
            print("\n[ISSUE 2] improved_token handler NEVER RAN:")
            print(f"  - {len(improved_token_events)} improved_token events received")
            print(f"  - But 0 calls to onEvent handler")
            print(f"  - This means CodeAssistant improved_token handler (line 120) NEVER RUNS")
            print(f"  - REASON: api.ts routes improved_token to onToken, not onEvent")
        
        # Check if improved handler was called
        if improved_events:
            print("\n[CHECK] improved handler:")
            if improved_onEvent:
                print(f"  ✓ improved handler WAS called ({len(improved_onEvent)} times)")
                for call in improved_onEvent:
                    data = call['data']
                    improved_output = data.get('improved_output', '')
                    solution = data.get('solution', '')
                    final_output = improved_output or solution
                    if final_output:
                        print(f"    ✓ Handler had valid data ({len(final_output)} chars)")
                    else:
                        print(f"    ✗ Handler had NO data")
            else:
                print(f"  ✗ improved handler was NOT called")
                print(f"  - {len(improved_events)} improved events received")
                print(f"  - But 0 calls to onEvent handler")
        
        # Final diagnosis
        print("\n" + "="*80)
        print("ROOT CAUSE DIAGNOSIS")
        print("="*80)
        
        issues = []
        
        if len(simulator.refinedCode_state) == 0:
            issues.append("🔴 CRITICAL: refinedCode_state is EMPTY")
            issues.append("   → UI will show 'generating' or placeholder")
        
        if improved_token_events and not improved_token_onEvent:
            issues.append("🔴 CRITICAL: improved_token handler NEVER RUNS")
            issues.append("   → api.ts routes improved_token to onToken only")
            issues.append("   → CodeAssistant handler in onEvent never executes")
            issues.append("   → Tokens go to firstCode if isInImprovementPhase is false")
        
        if improved_token_onToken:
            for call in improved_token_onToken:
                if not call['isInImprovementPhase']:
                    issues.append("🔴 CRITICAL: improved_token processed before phase flag set")
                    issues.append("   → Token went to firstCode instead of refinedCode")
                    issues.append(f"   → Lost {len(call['token'])} chars of refined output")
        
        if improved_onEvent:
            for call in improved_onEvent:
                data = call['data']
                final_output = data.get('improved_output') or data.get('solution', '')
                if final_output and len(simulator.refinedCode_state) == 0:
                    issues.append("⚠️  WARNING: improved handler had data but state is empty")
                    issues.append("   → Handler may have run but state update failed")
                    issues.append("   → Possible React rendering issue")
        
        if issues:
            print("\nISSUES FOUND:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("\n✓ No critical issues found")
            if len(simulator.refinedCode_state) > 0:
                print(f"✓ refinedCode_state has {len(simulator.refinedCode_state)} chars")
                print("  → UI should display refined output correctly")
        
        # Recommended fix
        print("\n" + "="*80)
        print("RECOMMENDED FIX")
        print("="*80)
        
        if improved_token_events and not improved_token_onEvent:
            print("\nFIX 1: Make api.ts call onEvent for improved_token events")
            print("  → Add call to onEvent BEFORE routing to onToken")
            print("  → This allows handler to set phase flag first")
        
        if improved_onEvent and len(simulator.refinedCode_state) == 0:
            print("\nFIX 2: Verify improved handler actually updates state")
            print("  → Check if setRefinedCode is being called")
            print("  → Check if React is re-rendering")
            print("  → Add console.log to verify")
        
        if len(simulator.refinedCode_state) == 0 and not improved_onEvent:
            print("\nFIX 3: Ensure improved events reach onEvent handler")
            print("  → Verify api.ts routing logic")
            print("  → Check for errors in event processing")
        
        return {
            'refinedCode_length': len(simulator.refinedCode_state),
            'firstCode_length': len(simulator.firstGeneratedCode_state),
            'improved_token_events': len(improved_token_events),
            'improved_events': len(improved_events),
            'improved_token_onToken': len(improved_token_onToken),
            'improved_token_onEvent': len(improved_token_onEvent),
            'improved_onEvent': len(improved_onEvent),
            'issues': issues
        }
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    try:
        result = test_thorough_frontend_simulation()
        if result:
            print("\n" + "="*80)
            print("TEST SUMMARY")
            print("="*80)
            print(f"refinedCode length: {result['refinedCode_length']} chars")
            print(f"firstCode length: {result['firstCode_length']} chars")
            print(f"improved_token events: {result['improved_token_events']}")
            print(f"improved events: {result['improved_events']}")
            print(f"improved_token → onToken: {result['improved_token_onToken']}")
            print(f"improved_token → onEvent: {result['improved_token_onEvent']}")
            print(f"improved → onEvent: {result['improved_onEvent']}")
            
            if result['refinedCode_length'] == 0:
                print("\n🔴 PROBLEM: refinedCode is empty - UI will show 'generating'")
                sys.exit(1)
            else:
                print("\n✓ refinedCode has content - should display correctly")
                sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


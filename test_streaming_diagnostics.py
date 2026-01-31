"""Comprehensive diagnostic tests for streaming issues with realistic examples."""
import asyncio
import time
import requests
import json
import sys
from typing import Dict, List, Optional

BACKEND_URL = "http://localhost:8000"

# Realistic test scenarios
REALISTIC_TESTS = [
    {
        "name": "Simple Python Function",
        "task": "Write a Python function to calculate the factorial of a number",
        "use_rag": False,
        "is_code": True,
        "expected_timeout": 60
    },
    {
        "name": "React Component",
        "task": "Create a React component for a todo list with add and delete functionality",
        "use_rag": False,
        "is_code": True,
        "expected_timeout": 90
    },
    {
        "name": "API Endpoint",
        "task": "Create a FastAPI endpoint that accepts user registration data and validates email format",
        "use_rag": False,
        "is_code": True,
        "expected_timeout": 90
    },
    {
        "name": "Document Query",
        "task": "What are the main features of this system?",
        "use_rag": True,
        "is_code": False,
        "expected_timeout": 60
    },
    {
        "name": "Chatbot Question",
        "task": "Explain how machine learning works in simple terms",
        "use_rag": False,
        "is_code": False,
        "expected_timeout": 60
    }
]

class StreamingDiagnostics:
    """Diagnostic tool for streaming issues."""
    
    def __init__(self):
        self.results = []
    
    def test_streaming_flow(self, test_config: Dict) -> Dict:
        """Test complete streaming flow with detailed diagnostics."""
        print(f"\n{'='*80}")
        print(f"TEST: {test_config['name']}")
        print(f"Task: {test_config['task']}")
        print(f"{'='*80}")
        
        result = {
            "test_name": test_config['name'],
            "task": test_config['task'],
            "start_time": time.time(),
            "events": [],
            "phases": {},
            "errors": [],
            "stuck_at": None,
            "completed": False
        }
        
        try:
            start = time.time()
            
            # Make request
            response = requests.post(
                f"{BACKEND_URL}/process-stream",
                json={
                    "task": test_config['task'],
                    "use_rag": test_config.get('use_rag', False),
                    "is_code": test_config.get('is_code', True)
                },
                stream=True,
                timeout=test_config.get('expected_timeout', 120)
            )
            
            connection_time = time.time() - start
            result["phases"]["connection"] = connection_time
            print(f"⏱  Connection established: {connection_time:.2f}s")
            
            if response.status_code != 200:
                result["errors"].append(f"HTTP {response.status_code}: {response.text}")
                print(f"✗ HTTP Error: {response.status_code}")
                return result
            
            # Track events
            last_event_time = time.time()
            event_timeout = 30  # If no event for 30s, consider stuck
            first_token_time = None
            first_response_complete_time = None
            improving_started_time = None
            first_improved_token_time = None
            improved_complete_time = None
            end_time = None
            
            token_count = 0
            improved_token_count = 0
            
            print("\n📊 Event Timeline:")
            print("-" * 80)
            
            for line in response.iter_lines(decode_unicode=True):
                current_time = time.time()
                
                # Check for timeout
                if current_time - last_event_time > event_timeout:
                    result["stuck_at"] = f"No events for {event_timeout}s after: {result['events'][-1]['type'] if result['events'] else 'start'}"
                    print(f"\n⚠️  STUCK: {result['stuck_at']}")
                    break
                
                if line and line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        elapsed = current_time - start
                        
                        result["events"].append({
                            "type": event_type,
                            "time": elapsed,
                            "data": data
                        })
                        
                        last_event_time = current_time
                        
                        # Track key events
                        if event_type == "start":
                            print(f"[{elapsed:6.2f}s] ✓ Start event")
                        elif event_type == "token":
                            token_count += 1
                            if first_token_time is None:
                                first_token_time = current_time
                                result["phases"]["first_token"] = current_time - start
                                print(f"[{elapsed:6.2f}s] ✓ First token (TTFT: {result['phases']['first_token']:.2f}s)")
                        elif event_type == "first_response_complete":
                            first_response_complete_time = current_time
                            result["phases"]["first_response_complete"] = current_time - start
                            print(f"[{elapsed:6.2f}s] ✓ First response complete ({token_count} tokens)")
                        elif event_type == "improving_started":
                            improving_started_time = current_time
                            result["phases"]["improving_started"] = current_time - start
                            print(f"[{elapsed:6.2f}s] ✓ Improving started")
                        elif event_type == "improved_token":
                            improved_token_count += 1
                            if first_improved_token_time is None:
                                first_improved_token_time = current_time
                                result["phases"]["first_improved_token"] = current_time - start
                                delay = current_time - (first_response_complete_time or start)
                                print(f"[{elapsed:6.2f}s] ✓ First improved token (delay: {delay:.2f}s)")
                        elif event_type == "improved":
                            improved_complete_time = current_time
                            result["phases"]["improved_complete"] = current_time - start
                            print(f"[{elapsed:6.2f}s] ✓ Improved complete ({improved_token_count} tokens)")
                        elif event_type in ["end", "complete"]:
                            end_time = current_time
                            result["phases"]["end"] = current_time - start
                            result["completed"] = True
                            print(f"[{elapsed:6.2f}s] ✓ End/Complete")
                            break
                        elif event_type == "error":
                            error_msg = data.get("message", "Unknown error")
                            result["errors"].append(error_msg)
                            print(f"[{elapsed:6.2f}s] ✗ Error: {error_msg}")
                        else:
                            # Other events
                            if elapsed < 5 or event_type in ["iteration_start", "sutra_started"]:
                                print(f"[{elapsed:6.2f}s] • {event_type}")
                            
                    except json.JSONDecodeError as e:
                        result["errors"].append(f"JSON decode error: {e}")
                        print(f"⚠️  JSON decode error: {e}")
                    except Exception as e:
                        result["errors"].append(f"Event processing error: {e}")
                        print(f"⚠️  Event error: {e}")
            
            response.close()
            
            # Calculate metrics
            total_time = time.time() - start
            result["total_time"] = total_time
            result["token_count"] = token_count
            result["improved_token_count"] = improved_token_count
            
            # Analysis
            print(f"\n{'='*80}")
            print("ANALYSIS")
            print(f"{'='*80}")
            
            if first_token_time:
                print(f"⏱  Time to First Token: {result['phases'].get('first_token', 0):.2f}s")
            
            if first_response_complete_time:
                print(f"⏱  First Generation Time: {result['phases'].get('first_response_complete', 0):.2f}s")
                print(f"   Tokens: {token_count}")
            
            if improving_started_time and first_response_complete_time:
                delay = improving_started_time - first_response_complete_time
                print(f"⏱  Improving Start Delay: {delay:.2f}s")
            
            if first_improved_token_time:
                if first_response_complete_time:
                    refined_delay = first_improved_token_time - first_response_complete_time
                    print(f"⏱  Refined Output Delay: {refined_delay:.2f}s")
                print(f"   First Improved Token: {result['phases'].get('first_improved_token', 0):.2f}s")
            
            if improved_complete_time:
                print(f"⏱  Improved Complete: {result['phases'].get('improved_complete', 0):.2f}s")
                print(f"   Improved Tokens: {improved_token_count}")
            
            print(f"⏱  Total Time: {total_time:.2f}s")
            
            # Identify issues
            print(f"\n{'='*80}")
            print("ISSUES DETECTED")
            print(f"{'='*80}")
            
            issues = []
            
            if not first_token_time:
                issues.append("❌ No tokens received - generation not starting")
            elif result['phases'].get('first_token', 0) > 10:
                issues.append(f"⚠️  Slow first token: {result['phases']['first_token']:.2f}s")
            
            if not first_response_complete_time:
                issues.append("❌ First response never completed")
            elif not improving_started_time:
                issues.append("❌ Improving phase never started")
            elif not first_improved_token_time:
                if improving_started_time:
                    delay = time.time() - improving_started_time
                    if delay > 20:
                        issues.append(f"❌ No improved tokens after {delay:.1f}s - STUCK IN IMPROVING PHASE")
            
            if not result["completed"]:
                issues.append("❌ Process did not complete")
            
            if result["stuck_at"]:
                issues.append(f"❌ {result['stuck_at']}")
            
            if issues:
                for issue in issues:
                    print(issue)
            else:
                print("✓ No issues detected")
            
            result["issues"] = issues
            
        except requests.exceptions.Timeout:
            result["errors"].append("Request timeout")
            result["stuck_at"] = "Request timed out"
            print(f"\n✗ Request timed out after {test_config.get('expected_timeout', 120)}s")
        except Exception as e:
            result["errors"].append(str(e))
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def run_all_tests(self):
        """Run all diagnostic tests."""
        print("="*80)
        print("STREAMING DIAGNOSTICS - REALISTIC EXAMPLES")
        print("="*80)
        print(f"Backend: {BACKEND_URL}")
        print(f"Tests: {len(REALISTIC_TESTS)}")
        print("="*80)
        
        # Check backend health first
        try:
            health = requests.get(f"{BACKEND_URL}/health", timeout=5)
            if health.status_code == 200:
                print("✓ Backend is healthy\n")
            else:
                print(f"✗ Backend health check failed: {health.status_code}\n")
                return
        except Exception as e:
            print(f"✗ Cannot connect to backend: {e}\n")
            return
        
        # Run tests
        for i, test_config in enumerate(REALISTIC_TESTS, 1):
            print(f"\n\n[{i}/{len(REALISTIC_TESTS)}]")
            result = self.test_streaming_flow(test_config)
            self.results.append(result)
            
            # Brief pause between tests
            if i < len(REALISTIC_TESTS):
                time.sleep(2)
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        print(f"\n\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}\n")
        
        total_tests = len(self.results)
        completed = sum(1 for r in self.results if r["completed"])
        stuck_tests = [r for r in self.results if r["stuck_at"]]
        no_improved_tokens = [r for r in self.results if r.get("improved_token_count", 0) == 0 and r.get("phases", {}).get("improving_started")]
        
        print(f"Total Tests: {total_tests}")
        print(f"Completed: {completed}/{total_tests}")
        print(f"Stuck: {len(stuck_tests)}")
        print(f"No Improved Tokens: {len(no_improved_tokens)}")
        
        if stuck_tests:
            print(f"\n{'='*80}")
            print("STUCK TESTS")
            print(f"{'='*80}")
            for test in stuck_tests:
                print(f"\n❌ {test['test_name']}")
                print(f"   Stuck at: {test['stuck_at']}")
                print(f"   Last event: {test['events'][-1]['type'] if test['events'] else 'None'}")
                print(f"   Total time: {test.get('total_time', 0):.2f}s")
        
        if no_improved_tokens:
            print(f"\n{'='*80}")
            print("NO IMPROVED TOKENS")
            print(f"{'='*80}")
            for test in no_improved_tokens:
                print(f"\n⚠️  {test['test_name']}")
                print(f"   Improving started: {test['phases'].get('improving_started', 0):.2f}s")
                print(f"   But no improved tokens received")
                print(f"   Total time: {test.get('total_time', 0):.2f}s")
        
        # Average metrics
        if self.results:
            avg_ttft = sum(r['phases'].get('first_token', 0) for r in self.results if r['phases'].get('first_token')) / max(1, sum(1 for r in self.results if r['phases'].get('first_token')))
            avg_refined_delay = []
            for r in self.results:
                if r['phases'].get('first_improved_token') and r['phases'].get('first_response_complete'):
                    delay = r['phases']['first_improved_token'] - r['phases']['first_response_complete']
                    avg_refined_delay.append(delay)
            
            print(f"\n{'='*80}")
            print("AVERAGE METRICS")
            print(f"{'='*80}")
            if avg_ttft > 0:
                print(f"Average Time to First Token: {avg_ttft:.2f}s")
            if avg_refined_delay:
                avg_delay = sum(avg_refined_delay) / len(avg_refined_delay)
                print(f"Average Refined Output Delay: {avg_delay:.2f}s")
                if avg_delay > 15:
                    print(f"⚠️  WARNING: High refined output delay (>15s)")

if __name__ == "__main__":
    diagnostics = StreamingDiagnostics()
    diagnostics.run_all_tests()


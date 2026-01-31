"""Enhanced test with realistic inputs to identify refined output delays."""
import time
import requests
import json
import sys
from typing import Dict, List

BACKEND_URL = "http://localhost:8000"

# Realistic test prompts
REALISTIC_PROMPTS = [
    {
        "name": "Code Generation - Python Function",
        "task": "Create a Python function that takes a list of numbers and returns the sum of all even numbers. Include error handling and type hints.",
        "use_rag": False,
        "is_code": True
    },
    {
        "name": "Code Generation - React Component",
        "task": "Write a React component that displays a list of items with search and filter functionality. Use hooks and make it responsive.",
        "use_rag": False,
        "is_code": True
    },
    {
        "name": "Code Generation - API Endpoint",
        "task": "Create a FastAPI endpoint that accepts JSON data, validates it using Pydantic, and stores it in a database. Include proper error handling.",
        "use_rag": False,
        "is_code": True
    }
]

class RefinedOutputLatencyTester:
    """Test refined output generation latency with realistic inputs."""
    
    def __init__(self):
        self.timing_data = []
    
    def test_realistic_prompt(self, prompt_config: Dict) -> Dict:
        """Test a realistic prompt and measure all timing phases."""
        print(f"\n{'='*80}")
        print(f"Testing: {prompt_config['name']}")
        print(f"Prompt: {prompt_config['task'][:60]}...")
        print(f"{'='*80}")
        
        timing = {
            "prompt": prompt_config['name'],
            "task": prompt_config['task'],
            "start_time": None,
            "first_event_time": None,
            "first_token_time": None,
            "first_response_complete_time": None,
            "sutra_started_time": None,
            "improving_started_time": None,
            "first_improved_token_time": None,
            "improved_complete_time": None,
            "end_time": None,
            "total_tokens": 0,
            "improved_tokens": 0,
            "phases": {}
        }
        
        try:
            start = time.time()
            timing["start_time"] = start
            
            response = requests.post(
                f"{BACKEND_URL}/process-stream",
                json={
                    "task": prompt_config['task'],
                    "use_rag": prompt_config.get('use_rag', False),
                    "is_code": prompt_config.get('is_code', True)
                },
                stream=True,
                timeout=180
            )
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            
            # Track all events and their timings
            all_events = []  # Debug: track all event types
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        current_time = time.time()
                        all_events.append((event_type, current_time - start))  # Debug
                        
                        # Track first event
                        if timing["first_event_time"] is None:
                            timing["first_event_time"] = current_time
                        
                        # Track first token (Yantra generation)
                        if event_type == "token" and timing["first_token_time"] is None:
                            timing["first_token_time"] = current_time
                            timing["total_tokens"] += 1
                        
                        # Track first response complete
                        if event_type == "first_response_complete":
                            timing["first_response_complete_time"] = current_time
                            print(f"  [DEBUG] first_response_complete at {(current_time - start)*1000:.2f}ms")
                        
                        # Track Sutra started
                        if event_type == "sutra_started":
                            timing["sutra_started_time"] = current_time
                            print(f"  [DEBUG] sutra_started at {(current_time - start)*1000:.2f}ms")
                        
                        # Track improving started
                        if event_type == "improving_started":
                            timing["improving_started_time"] = current_time
                            print(f"  [DEBUG] improving_started at {(current_time - start)*1000:.2f}ms")
                        
                        # Track first improved token
                        if event_type == "improved_token" and timing["first_improved_token_time"] is None:
                            timing["first_improved_token_time"] = current_time
                            timing["improved_tokens"] += 1
                            print(f"  [DEBUG] first_improved_token at {(current_time - start)*1000:.2f}ms")
                        
                        # Track improved complete
                        if event_type == "improved":
                            timing["improved_complete_time"] = current_time
                            print(f"  [DEBUG] improved event at {(current_time - start)*1000:.2f}ms")
                        
                        # Track end
                        if event_type in ["end", "complete"]:
                            timing["end_time"] = current_time
                            print(f"  [DEBUG] end/complete at {(current_time - start)*1000:.2f}ms")
                            break
                        
                        # Count tokens
                        if event_type == "token":
                            timing["total_tokens"] += 1
                        elif event_type == "improved_token":
                            timing["improved_tokens"] += 1
                            
                    except json.JSONDecodeError as e:
                        print(f"  [DEBUG] JSON decode error: {e}, line: {line[:50]}")
                        continue
            
            # Debug: print all event types received
            print(f"\n  [DEBUG] All event types received: {[e[0] for e in all_events[:20]]}")
            
            # Safety timeout check
            if time.time() - start > 180:
                print("  [DEBUG] Timeout reached")
            
            response.close()
            
            # Calculate phase timings
            if timing["first_token_time"]:
                timing["phases"]["time_to_first_token"] = (timing["first_token_time"] - timing["start_time"]) * 1000
            
            if timing["first_response_complete_time"]:
                timing["phases"]["first_generation_time"] = (timing["first_response_complete_time"] - timing["start_time"]) * 1000
            
            if timing["sutra_started_time"] and timing["first_response_complete_time"]:
                timing["phases"]["sutra_delay"] = (timing["sutra_started_time"] - timing["first_response_complete_time"]) * 1000
            
            if timing["improving_started_time"] and timing["sutra_started_time"]:
                timing["phases"]["sutra_processing_time"] = (timing["improving_started_time"] - timing["sutra_started_time"]) * 1000
            
            if timing["first_improved_token_time"] and timing["improving_started_time"]:
                timing["phases"]["time_to_first_improved_token"] = (timing["first_improved_token_time"] - timing["improving_started_time"]) * 1000
                # This is the KEY METRIC - delay in refined output
                timing["phases"]["refined_output_delay"] = (timing["first_improved_token_time"] - timing["first_response_complete_time"]) * 1000
            
            if timing["improved_complete_time"] and timing["improving_started_time"]:
                timing["phases"]["improved_generation_time"] = (timing["improved_complete_time"] - timing["improving_started_time"]) * 1000
            
            if timing["end_time"]:
                timing["phases"]["total_time"] = (timing["end_time"] - timing["start_time"]) * 1000
            
            # Print results
            self.print_timing_analysis(timing)
            
            return timing
            
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def print_timing_analysis(self, timing: Dict):
        """Print detailed timing analysis."""
        print(f"\n{'─'*80}")
        print("TIMING ANALYSIS")
        print(f"{'─'*80}")
        
        phases = timing["phases"]
        
        if "time_to_first_token" in phases:
            print(f"⏱  Time to First Token: {phases['time_to_first_token']:.2f}ms")
        
        if "first_generation_time" in phases:
            print(f"⏱  First Generation Complete: {phases['first_generation_time']:.2f}ms ({timing['total_tokens']} tokens)")
        
        if "sutra_delay" in phases:
            print(f"⏱  Sutra Start Delay: {phases['sutra_delay']:.2f}ms")
        
        if "sutra_processing_time" in phases:
            print(f"⏱  Sutra Processing Time: {phases['sutra_processing_time']:.2f}ms")
        
        if "time_to_first_improved_token" in phases:
            print(f"⏱  Time to First Improved Token: {phases['time_to_first_improved_token']:.2f}ms")
            if phases['time_to_first_improved_token'] > 5000:
                print(f"   ⚠️  WARNING: High delay in improved token generation!")
        
        if "refined_output_delay" in phases:
            delay = phases['refined_output_delay']
            print(f"\n🔴 REFINED OUTPUT DELAY: {delay:.2f}ms ({delay/1000:.2f}s)")
            if delay > 30000:
                print(f"   ⚠️  CRITICAL: Very high delay (>30s) in refined output!")
            elif delay > 15000:
                print(f"   ⚠️  WARNING: High delay (>15s) in refined output")
            elif delay > 10000:
                print(f"   ⚠️  WARNING: Moderate delay (>10s) in refined output")
            else:
                print(f"   ✓ Acceptable delay")
        
        if "improved_generation_time" in phases:
            print(f"⏱  Improved Generation Complete: {phases['improved_generation_time']:.2f}ms ({timing['improved_tokens']} tokens)")
        
        if "total_time" in phases:
            print(f"\n⏱  Total Time: {phases['total_time']:.2f}ms ({phases['total_time']/1000:.2f}s)")
        
        # Breakdown analysis
        print(f"\n{'─'*80}")
        print("BREAKDOWN:")
        print(f"{'─'*80}")
        if "first_generation_time" in phases:
            pct = (phases['first_generation_time'] / phases.get('total_time', 1)) * 100
            print(f"First Generation: {phases['first_generation_time']:.2f}ms ({pct:.1f}%)")
        
        if "sutra_processing_time" in phases:
            pct = (phases['sutra_processing_time'] / phases.get('total_time', 1)) * 100
            print(f"Sutra Processing: {phases['sutra_processing_time']:.2f}ms ({pct:.1f}%)")
        
        if "improved_generation_time" in phases:
            pct = (phases['improved_generation_time'] / phases.get('total_time', 1)) * 100
            print(f"Improved Generation: {phases['improved_generation_time']:.2f}ms ({pct:.1f}%)")
        
        if "refined_output_delay" in phases:
            delay = phases['refined_output_delay']
            pct = (delay / phases.get('total_time', 1)) * 100
            print(f"🔴 Refined Output Delay: {delay:.2f}ms ({pct:.1f}%)")
    
    def run_all_tests(self):
        """Run all realistic prompt tests."""
        print("="*80)
        print("REALISTIC INPUT LATENCY TEST")
        print("Testing with real-world code generation prompts")
        print("="*80)
        
        results = []
        for prompt_config in REALISTIC_PROMPTS:
            result = self.test_realistic_prompt(prompt_config)
            if result:
                results.append(result)
            time.sleep(2)  # Brief pause between tests
        
        # Summary
        print(f"\n\n{'='*80}")
        print("SUMMARY - REFINED OUTPUT DELAY ANALYSIS")
        print(f"{'='*80}\n")
        
        if results:
            refined_delays = [r["phases"].get("refined_output_delay", 0) for r in results if "refined_output_delay" in r["phases"]]
            
            if refined_delays:
                avg_delay = sum(refined_delays) / len(refined_delays)
                max_delay = max(refined_delays)
                min_delay = min(refined_delays)
                
                print(f"Average Refined Output Delay: {avg_delay:.2f}ms ({avg_delay/1000:.2f}s)")
                print(f"Maximum Delay: {max_delay:.2f}ms ({max_delay/1000:.2f}s)")
                print(f"Minimum Delay: {min_delay:.2f}ms ({min_delay/1000:.2f}s)")
                
                print(f"\n{'─'*80}")
                print("BOTTLENECK IDENTIFICATION:")
                print(f"{'─'*80}")
                
                # Analyze each result
                for i, result in enumerate(results, 1):
                    phases = result["phases"]
                    print(f"\nTest {i}: {result['prompt']}")
                    
                    if "sutra_processing_time" in phases:
                        print(f"  Sutra Time: {phases['sutra_processing_time']:.2f}ms")
                    
                    if "time_to_first_improved_token" in phases:
                        print(f"  First Improved Token: {phases['time_to_first_improved_token']:.2f}ms")
                    
                    if "refined_output_delay" in phases:
                        delay = phases['refined_output_delay']
                        print(f"  🔴 Total Refined Delay: {delay:.2f}ms")
                        
                        # Identify bottleneck
                        if "sutra_processing_time" in phases:
                            sutra_pct = (phases['sutra_processing_time'] / delay) * 100 if delay > 0 else 0
                            improved_pct = ((delay - phases['sutra_processing_time']) / delay) * 100 if delay > 0 else 0
                            print(f"     - Sutra: {sutra_pct:.1f}% of delay")
                            print(f"     - Agni: {improved_pct:.1f}% of delay")
        
        return results

def main():
    """Run realistic input tests."""
    tester = RefinedOutputLatencyTester()
    results = tester.run_all_tests()
    return len(results) > 0

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


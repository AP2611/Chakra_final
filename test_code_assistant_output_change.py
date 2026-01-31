"""
Test to diagnose why first generated code changes to JavaScript when refined version is generated.
This test will:
1. Send a code generation request
2. Track all events and state changes
3. Monitor firstGeneratedCode and refinedCode throughout the process
4. Identify when and why firstGeneratedCode changes
"""

import asyncio
import httpx
import json
import time
from typing import Dict, List, Any

class CodeAssistantDiagnostic:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.events_received = []
        self.first_code_snapshots = []
        self.refined_code_snapshots = []
        self.is_in_improvement_phase = False
        
    async def check_backend_health(self) -> bool:
        """Check if backend is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.backend_url}/health")
                return response.status_code == 200
        except Exception as e:
            print(f"❌ Backend health check failed: {e}")
            return False
    
    async def test_code_generation(self, prompt: str):
        """Test code generation and track all state changes."""
        print(f"\n{'='*80}")
        print(f"TEST: Code Generation Output Change Diagnostic")
        print(f"{'='*80}")
        print(f"\nPrompt: {prompt}")
        print(f"\n🔍 Tracking all events and state changes...\n")
        
        # Simulate frontend state
        current_first_code = ""
        current_refined_code = ""
        is_in_improvement_phase = False
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Start SSE stream
                async with client.stream(
                    "POST",
                    f"{self.backend_url}/process-stream",
                    json={
                        "task": prompt,
                        "context": "",
                        "use_rag": False,
                        "is_code": True
                    },
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    response.raise_for_status()
                    
                    print("📡 Connected to SSE stream\n")
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        if line.startswith("data: "):
                            json_str = line[6:]  # Remove "data: " prefix
                            try:
                                data = json.loads(json_str)
                                event_type = data.get("type", "unknown")
                                
                                # Track event
                                self.events_received.append({
                                    "type": event_type,
                                    "data": data,
                                    "timestamp": time.time()
                                })
                                
                                # Simulate frontend onToken handler
                                if event_type == "token":
                                    token = data.get("token", "")
                                    if is_in_improvement_phase:
                                        current_refined_code += token
                                    else:
                                        current_first_code += token
                                        # Track first code changes
                                        if current_first_code:
                                            self.first_code_snapshots.append({
                                                "code": current_first_code[:200],  # First 200 chars
                                                "timestamp": time.time(),
                                                "source": "token_event",
                                                "phase": "first_generation"
                                            })
                                
                                # Simulate frontend onEvent handler
                                if event_type == "improving_started":
                                    is_in_improvement_phase = True
                                    print(f"🔄 Phase change: First generation → Improvement")
                                    print(f"   First code length: {len(current_first_code)}")
                                    print(f"   First code preview: {current_first_code[:100]}...")
                                
                                if event_type == "improved_token":
                                    token = data.get("token", "")
                                    if token:
                                        current_refined_code += token
                                
                                if event_type == "improved":
                                    final_output = data.get("improved_output") or data.get("solution")
                                    if final_output:
                                        current_refined_code = final_output
                                        self.refined_code_snapshots.append({
                                            "code": current_refined_code[:200],
                                            "timestamp": time.time(),
                                            "source": "improved_event"
                                        })
                                
                                if event_type == "iteration_complete":
                                    iteration_data = data.get("data", {})
                                    agni_output = iteration_data.get("agni_output")
                                    if agni_output:
                                        # Check if this would overwrite refinedCode
                                        print(f"\n⚠️  iteration_complete received with agni_output")
                                        print(f"   Current refined_code length: {len(current_refined_code)}")
                                        print(f"   agni_output length: {len(agni_output) if agni_output else 0}")
                                        
                                        # Check if first code changed
                                        if current_first_code:
                                            # Check if first code contains JavaScript keywords (unexpected)
                                            js_keywords = ["function", "const", "let", "var", "=>", "console.log"]
                                            has_js = any(keyword in current_first_code for keyword in js_keywords)
                                            if has_js and "python" in prompt.lower():
                                                print(f"\n🚨 PROBLEM DETECTED: First code contains JavaScript!")
                                                print(f"   First code preview: {current_first_code[:300]}")
                                
                                if event_type == "end":
                                    print(f"\n✅ Stream completed")
                                    break
                                
                                if event_type == "error":
                                    print(f"\n❌ Error received: {data.get('message', 'Unknown error')}")
                                    break
                                
                            except json.JSONDecodeError as e:
                                print(f"⚠️  Failed to parse JSON: {e}")
                                print(f"   Line: {line[:100]}")
                        
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Analyze results
        self.analyze_results(current_first_code, current_refined_code)
    
    def analyze_results(self, final_first_code: str, final_refined_code: str):
        """Analyze the collected data to identify issues."""
        print(f"\n{'='*80}")
        print(f"ANALYSIS")
        print(f"{'='*80}\n")
        
        # Count event types
        event_counts = {}
        for event in self.events_received:
            event_type = event["type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        print(f"📊 Event Summary:")
        for event_type, count in sorted(event_counts.items()):
            print(f"   {event_type}: {count}")
        
        print(f"\n📝 First Code Analysis:")
        print(f"   Final length: {len(final_first_code)}")
        print(f"   Preview (first 300 chars):")
        print(f"   {final_first_code[:300]}")
        
        # Check for JavaScript in first code (if prompt was for Python)
        js_keywords = ["function", "const", "let", "var", "=>", "console.log", "document.", "window."]
        has_js = any(keyword in final_first_code.lower() for keyword in js_keywords)
        
        if has_js:
            print(f"\n🚨 ISSUE FOUND: First code contains JavaScript keywords!")
            print(f"   This suggests first code was overwritten or corrupted.")
            print(f"   JavaScript keywords found:")
            for keyword in js_keywords:
                if keyword in final_first_code.lower():
                    print(f"     - {keyword}")
        
        print(f"\n📝 Refined Code Analysis:")
        print(f"   Final length: {len(final_refined_code)}")
        print(f"   Preview (first 300 chars):")
        print(f"   {final_refined_code[:300]}")
        
        # Check if first code changed after improvement phase started
        if len(self.first_code_snapshots) > 1:
            first_snapshot = self.first_code_snapshots[0]
            last_snapshot = self.first_code_snapshots[-1]
            
            if first_snapshot["code"] != last_snapshot["code"]:
                print(f"\n🚨 ISSUE FOUND: First code changed during generation!")
                print(f"   Initial: {first_snapshot['code'][:100]}...")
                print(f"   Final: {last_snapshot['code'][:100]}...")
        
        # Check for token events after improvement phase
        improvement_started = False
        tokens_after_improvement = []
        for event in self.events_received:
            if event["type"] == "improving_started":
                improvement_started = True
            if improvement_started and event["type"] == "token":
                tokens_after_improvement.append(event)
        
        if tokens_after_improvement:
            print(f"\n⚠️  WARNING: {len(tokens_after_improvement)} token events received AFTER improvement phase started")
            print(f"   These tokens might be incorrectly routed to firstGeneratedCode")
        
        print(f"\n{'='*80}\n")


async def main():
    diagnostic = CodeAssistantDiagnostic()
    
    # Check backend health
    print("🔍 Checking backend health...")
    if not await diagnostic.check_backend_health():
        print("❌ Backend is not running. Please start it first.")
        return
    
    print("✅ Backend is healthy\n")
    
    # Test 1: Python code generation
    print("\n" + "="*80)
    print("TEST 1: Python Code Generation")
    print("="*80)
    await diagnostic.test_code_generation(
        "Implement a Python function to calculate the factorial of a number using recursion"
    )
    
    await asyncio.sleep(2)
    
    # Test 2: Another code generation
    print("\n" + "="*80)
    print("TEST 2: Another Code Generation")
    print("="*80)
    await diagnostic.test_code_generation(
        "Create a Python class for a simple calculator with add, subtract, multiply, and divide methods"
    )


if __name__ == "__main__":
    asyncio.run(main())



"""
Simple diagnostic test to check both issues quickly.
"""

import asyncio
import httpx
import json
import sys

async def test_code_assistant():
    """Test code assistant output change issue."""
    print("\n" + "="*80)
    print("TEST 1: Code Assistant - First Code Changing Issue")
    print("="*80)
    
    prompt = "Implement a Python function to calculate factorial"
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Check health
            try:
                health = await client.get("http://localhost:8000/health")
                if health.status_code != 200:
                    print("❌ Backend not healthy")
                    return
            except:
                print("❌ Backend not running")
                return
            
            print(f"✅ Backend is running")
            print(f"📤 Sending prompt: {prompt}\n")
            
            first_code_snapshots = []
            refined_code_snapshots = []
            is_improving = False
            
            async with client.stream(
                "POST",
                "http://localhost:8000/process-stream",
                json={
                    "task": prompt,
                    "context": "",
                    "use_rag": False,
                    "is_code": True
                },
                headers={"Accept": "text/event-stream"}
            ) as response:
                response.raise_for_status()
                
                first_code = ""
                refined_code = ""
                
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        
                        if event_type == "token":
                            token = data.get("token", "")
                            if is_improving:
                                refined_code += token
                            else:
                                first_code += token
                                if len(first_code_snapshots) < 5 or len(first_code) % 50 == 0:
                                    first_code_snapshots.append({
                                        "len": len(first_code),
                                        "preview": first_code[:100]
                                    })
                        
                        if event_type == "improving_started":
                            is_improving = True
                            print(f"🔄 Improvement phase started")
                            print(f"   First code length: {len(first_code)}")
                            print(f"   First code preview: {first_code[:150]}")
                            
                            # Check for JavaScript
                            js_keywords = ["function", "const", "let", "var", "=>", "console.log"]
                            has_js = any(kw in first_code.lower() for kw in js_keywords)
                            if has_js:
                                print(f"   🚨 FIRST CODE CONTAINS JAVASCRIPT!")
                        
                        if event_type == "improved_token":
                            token = data.get("token", "")
                            if token:
                                refined_code += token
                        
                        if event_type == "improved":
                            output = data.get("improved_output") or data.get("solution")
                            if output:
                                refined_code = output
                                refined_code_snapshots.append({
                                    "len": len(refined_code),
                                    "preview": refined_code[:100]
                                })
                        
                        if event_type == "iteration_complete":
                            # Check if first code changed
                            if first_code:
                                js_keywords = ["function", "const", "let", "var", "=>", "console.log"]
                                has_js = any(kw in first_code.lower() for kw in js_keywords)
                                if has_js:
                                    print(f"\n🚨 PROBLEM: First code contains JavaScript after iteration_complete!")
                                    print(f"   First code: {first_code[:200]}")
                        
                        if event_type == "end":
                            break
                        
                        if event_type == "error":
                            print(f"\n❌ Error: {data.get('message')}")
                            break
                            
                    except json.JSONDecodeError:
                        continue
                
                print(f"\n📊 Final Results:")
                print(f"   First code length: {len(first_code)}")
                print(f"   Refined code length: {len(refined_code)}")
                
                # Check for JavaScript in first code
                js_keywords = ["function", "const", "let", "var", "=>", "console.log", "document."]
                has_js = any(kw in first_code.lower() for kw in js_keywords)
                if has_js:
                    print(f"\n🚨 ISSUE CONFIRMED: First code contains JavaScript!")
                    print(f"   First code preview: {first_code[:300]}")
                else:
                    print(f"   ✅ First code looks correct (no JavaScript)")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_chatbot_token_limit():
    """Test chatbot token limit issue."""
    print("\n" + "="*80)
    print("TEST 2: Chatbot - Token Limit Error Issue")
    print("="*80)
    
    prompt = "Write a detailed explanation of how machine learning works, including supervised learning, unsupervised learning, and reinforcement learning. Provide examples for each type and explain the differences between them."
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"📤 Sending long prompt (should exceed token limit)\n")
            
            token_count = 0
            error_occurred = False
            error_message = ""
            
            async with client.stream(
                "POST",
                "http://localhost:8000/process-stream",
                json={
                    "task": prompt,
                    "context": "",
                    "use_rag": False,
                    "is_code": False
                },
                headers={"Accept": "text/event-stream"}
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        
                        if event_type == "token":
                            token = data.get("token", "")
                            if token:
                                token_count += 1
                                if token_count % 50 == 0:
                                    print(f"   📊 Tokens: {token_count}")
                        
                        if event_type == "error":
                            error_occurred = True
                            error_message = data.get("message", "Unknown error")
                            print(f"\n❌ ERROR RECEIVED:")
                            print(f"   Message: {error_message}")
                            print(f"   Token count at error: {token_count}")
                            break
                        
                        if event_type == "end":
                            print(f"\n✅ Stream completed successfully")
                            print(f"   Total tokens: {token_count}")
                            break
                            
                    except json.JSONDecodeError:
                        continue
                
                print(f"\n📊 Final Results:")
                print(f"   Total tokens: {token_count}")
                print(f"   Token limit (fast mode): 512")
                print(f"   Token limit (normal mode): 1024")
                
                if error_occurred:
                    print(f"\n🚨 ISSUE CONFIRMED: Error occurred!")
                    print(f"   Error message: {error_message}")
                    print(f"   Token count: {token_count}")
                    
                    # Check if error is related to token limit
                    error_lower = error_message.lower()
                    if any(kw in error_lower for kw in ["token", "limit", "exceed", "truncate", "max"]):
                        print(f"   ✅ Error is likely related to token limit")
                    elif "timeout" in error_lower:
                        print(f"   ✅ Error is timeout related")
                else:
                    print(f"   ✅ No error occurred")
                
    except httpx.TimeoutException:
        print(f"\n❌ Request timed out")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    print("🔍 Running Diagnostic Tests")
    print("="*80)
    
    # Test 1: Code Assistant
    await test_code_assistant()
    
    await asyncio.sleep(2)
    
    # Test 2: Chatbot
    await test_chatbot_token_limit()
    
    print("\n" + "="*80)
    print("✅ Tests completed")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

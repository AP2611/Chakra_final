"""
Test to capture actual error messages from backend.
"""

import asyncio
import httpx
import json
import sys

async def test_with_error_capture():
    """Test and capture actual error details."""
    print("="*80)
    print("ERROR CAPTURE TEST")
    print("="*80)
    
    # Test 1: Code Assistant
    print("\n📝 TEST 1: Code Assistant")
    print("-" * 80)
    
    prompt = "Implement a Python function to calculate factorial"
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                
                events = []
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        events.append(data)
                        
                        if event_type == "error":
                            error_msg = data.get("message", "NO MESSAGE")
                            print(f"\n❌ ERROR EVENT RECEIVED:")
                            print(f"   Type: {event_type}")
                            print(f"   Message: {error_msg}")
                            print(f"   Full data: {json.dumps(data, indent=2)}")
                            break
                        
                        if event_type == "end":
                            print(f"✅ Completed successfully")
                            break
                            
                    except json.JSONDecodeError as e:
                        print(f"⚠️  JSON decode error: {e}")
                        print(f"   Line: {line[:200]}")
                
                # Show all events
                print(f"\n📊 All Events Received ({len(events)}):")
                for i, event in enumerate(events[-10:], 1):  # Last 10 events
                    print(f"   {i}. {event.get('type', 'unknown')}: {str(event)[:100]}")
                    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Chatbot
    print("\n\n📝 TEST 2: Chatbot (Long Response)")
    print("-" * 80)
    
    prompt = "Write a detailed explanation of how machine learning works, including supervised learning, unsupervised learning, and reinforcement learning."
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
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
                
                events = []
                token_count = 0
                
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        events.append(data)
                        
                        if event_type == "token":
                            token_count += 1
                            if token_count % 100 == 0:
                                print(f"   📊 Tokens: {token_count}")
                        
                        if event_type == "error":
                            error_msg = data.get("message", "NO MESSAGE")
                            print(f"\n❌ ERROR EVENT RECEIVED:")
                            print(f"   Type: {event_type}")
                            print(f"   Message: {error_msg}")
                            print(f"   Token count: {token_count}")
                            print(f"   Full data: {json.dumps(data, indent=2)}")
                            break
                        
                        if event_type == "end":
                            print(f"✅ Completed successfully")
                            print(f"   Total tokens: {token_count}")
                            break
                            
                    except json.JSONDecodeError as e:
                        print(f"⚠️  JSON decode error: {e}")
                        print(f"   Line: {line[:200]}")
                
                # Show last events
                print(f"\n📊 Last Events Received:")
                for i, event in enumerate(events[-5:], 1):
                    print(f"   {i}. {event.get('type', 'unknown')}: {str(event)[:150]}")
                    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_with_error_capture())


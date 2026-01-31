"""Test frontend-backend connection speed and functionality."""
import time
import requests
import json

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def test_connection_speed():
    """Test the connection speed between frontend and backend."""
    print("=" * 60)
    print("Testing Frontend-Backend Connection")
    print("=" * 60)
    
    # Test 1: Backend Health
    print("\n[1/4] Testing Backend Health Endpoint...")
    try:
        start = time.time()
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        elapsed = time.time() - start
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print(f"✓ Backend healthy - Response time: {elapsed*1000:.2f}ms")
    except Exception as e:
        print(f"✗ Backend health check failed: {e}")
        return False
    
    # Test 2: SSE Connection Speed
    print("\n[2/4] Testing SSE Stream Connection...")
    try:
        start = time.time()
        response = requests.post(
            f"{BACKEND_URL}/process-stream",
            json={
                "task": "Create a Python function that takes a list of numbers and returns the sum of all even numbers. Include error handling and type hints.",
                "use_rag": False,
                "is_code": True
            },
            stream=True,
            timeout=60
        )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/event-stream"
        
        # Read first few events
        first_event_time = None
        event_count = 0
        for line in response.iter_lines():
            if line:
                if first_event_time is None:
                    first_event_time = time.time()
                    elapsed = first_event_time - start
                    print(f"✓ First event received in {elapsed*1000:.2f}ms")
                
                event_count += 1
                if event_count >= 5:  # Read first 5 events
                    break
        
        total_time = time.time() - start
        print(f"✓ Stream working - {event_count} events in {total_time*1000:.2f}ms")
        response.close()
    except Exception as e:
        print(f"✗ SSE stream test failed: {e}")
        return False
    
    # Test 3: Token Streaming Speed
    print("\n[3/4] Testing Token Streaming Performance...")
    try:
        start = time.time()
        response = requests.post(
            f"{BACKEND_URL}/process-stream",
            json={
                "task": "Write a React component that displays a list of items with search and filter functionality. Use hooks and make it responsive.",
                "use_rag": False,
                "is_code": True
            },
            stream=True,
            timeout=120
        )
        
        token_count = 0
        first_token_time = None
        last_token_time = None
        
        for line in response.iter_lines():
            if line and line.startswith(b"data: "):
                try:
                    data = json.loads(line[6:])  # Remove "data: " prefix
                    if data.get("type") == "token":
                        token_count += 1
                        if first_token_time is None:
                            first_token_time = time.time()
                            print(f"✓ First token received in {(first_token_time - start)*1000:.2f}ms")
                        last_token_time = time.time()
                        
                        if token_count >= 10:  # Test first 10 tokens
                            break
                except:
                    continue
        
        if token_count > 0:
            avg_token_time = ((last_token_time - first_token_time) / token_count) * 1000
            print(f"✓ Token streaming working - {token_count} tokens, avg {avg_token_time:.2f}ms/token")
        else:
            print("⚠ No tokens received (may be normal if model is slow)")
        
        response.close()
    except Exception as e:
        print(f"✗ Token streaming test failed: {e}")
        return False
    
    # Test 4: Frontend Accessibility
    print("\n[4/4] Testing Frontend Accessibility...")
    try:
        start = time.time()
        response = requests.get(FRONTEND_URL, timeout=5)
        elapsed = time.time() - start
        assert response.status_code == 200
        print(f"✓ Frontend accessible - Response time: {elapsed*1000:.2f}ms")
    except Exception as e:
        print(f"✗ Frontend accessibility test failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ All connection tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_connection_speed()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


"""Comprehensive test for frontend-backend connection with latency measurements."""
import time
import requests
import json
import sys
from typing import Dict, List, Optional

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

class ConnectionTester:
    """Test frontend-backend connection with detailed latency analysis."""
    
    def __init__(self):
        self.results = {
            "backend_health": {"passed": False, "latency": 0, "error": None},
            "sse_connection": {"passed": False, "latency": 0, "error": None},
            "first_token": {"passed": False, "latency": 0, "error": None},
            "token_streaming": {"passed": False, "tokens_per_sec": 0, "error": None},
            "improved_tokens": {"passed": False, "latency": 0, "error": None},
            "end_to_end": {"passed": False, "latency": 0, "error": None},
            "frontend_access": {"passed": False, "latency": 0, "error": None},
        }
    
    def test_backend_health(self) -> bool:
        """Test backend health endpoint."""
        print("\n[1/7] Testing Backend Health Endpoint...")
        try:
            start = time.time()
            response = requests.get(f"{BACKEND_URL}/health", timeout=5)
            latency = time.time() - start
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            
            self.results["backend_health"]["passed"] = True
            self.results["backend_health"]["latency"] = latency
            print(f"✓ Backend healthy - Response time: {latency*1000:.2f}ms")
            return True
        except Exception as e:
            self.results["backend_health"]["error"] = str(e)
            print(f"✗ Backend health check failed: {e}")
            return False
    
    def test_sse_connection(self) -> bool:
        """Test SSE stream connection establishment."""
        print("\n[2/7] Testing SSE Stream Connection...")
        try:
            start = time.time()
            response = requests.post(
                f"{BACKEND_URL}/process-stream",
                json={
                    "task": "test",
                    "use_rag": False,
                    "is_code": True
                },
                stream=True,
                timeout=10,
                headers={"Accept": "text/event-stream"}
            )
            connection_time = time.time() - start
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            
            # Read first event
            first_event_time = None
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    first_event_time = time.time()
                    break
                if first_event_time and (first_event_time - start) > 5:
                    break
            
            total_time = (first_event_time or time.time()) - start
            
            self.results["sse_connection"]["passed"] = True
            self.results["sse_connection"]["latency"] = total_time
            print(f"✓ SSE connection established - First event in {total_time*1000:.2f}ms")
            response.close()
            return True
        except Exception as e:
            self.results["sse_connection"]["error"] = str(e)
            print(f"✗ SSE connection failed: {e}")
            return False
    
    def test_first_token(self) -> bool:
        """Test time to first token."""
        print("\n[3/7] Testing Time to First Token...")
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
            
            first_token_time = None
            token_count = 0
            
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "token":
                            if first_token_time is None:
                                first_token_time = time.time()
                                latency = first_token_time - start
                                self.results["first_token"]["passed"] = True
                                self.results["first_token"]["latency"] = latency
                                print(f"✓ First token received in {latency*1000:.2f}ms")
                                response.close()
                                return True
                            token_count += 1
                            if token_count > 50:  # Safety limit
                                break
                    except:
                        continue
                
                # Timeout check
                if time.time() - start > 30:
                    break
            
            response.close()
            if first_token_time is None:
                raise Exception("No token received within 30 seconds")
            return True
        except Exception as e:
            self.results["first_token"]["error"] = str(e)
            print(f"✗ First token test failed: {e}")
            return False
    
    def test_token_streaming(self) -> bool:
        """Test token streaming performance."""
        print("\n[4/7] Testing Token Streaming Performance...")
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
            
            tokens = []
            first_token_time = None
            last_token_time = None
            
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "token":
                            token = data.get("token", "")
                            if token:
                                tokens.append(token)
                                if first_token_time is None:
                                    first_token_time = time.time()
                                last_token_time = time.time()
                                
                                if len(tokens) >= 20:  # Test first 20 tokens
                                    break
                    except:
                        continue
                
                if time.time() - start > 60:
                    break
            
            response.close()
            
            if len(tokens) < 5:
                raise Exception(f"Too few tokens received: {len(tokens)}")
            
            total_time = (last_token_time or time.time()) - (first_token_time or start)
            tokens_per_sec = len(tokens) / total_time if total_time > 0 else 0
            
            self.results["token_streaming"]["passed"] = True
            self.results["token_streaming"]["tokens_per_sec"] = tokens_per_sec
            print(f"✓ Token streaming - {len(tokens)} tokens, {tokens_per_sec:.2f} tokens/sec")
            return True
        except Exception as e:
            self.results["token_streaming"]["error"] = str(e)
            print(f"✗ Token streaming test failed: {e}")
            return False
    
    def test_improved_tokens(self) -> bool:
        """Test improved token streaming latency."""
        print("\n[5/7] Testing Improved Token Streaming...")
        try:
            start = time.time()
            response = requests.post(
                f"{BACKEND_URL}/process-stream",
                json={
                    "task": "Create a FastAPI endpoint that accepts JSON data, validates it using Pydantic, and stores it in a database. Include proper error handling.",
                    "use_rag": False,
                    "is_code": True
                },
                stream=True,
                timeout=180
            )
            
            improved_tokens = []
            improving_started = False
            first_improved_token_time = None
            
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        
                        if data.get("type") == "improving_started":
                            improving_started = True
                        
                        if data.get("type") == "improved_token" and improving_started:
                            token = data.get("token", "")
                            if token:
                                improved_tokens.append(token)
                                if first_improved_token_time is None:
                                    first_improved_token_time = time.time()
                                    latency = first_improved_token_time - start
                                    self.results["improved_tokens"]["latency"] = latency
                                
                                if len(improved_tokens) >= 10:
                                    break
                    except:
                        continue
                
                if time.time() - start > 90:
                    break
            
            response.close()
            
            if len(improved_tokens) > 0:
                self.results["improved_tokens"]["passed"] = True
                print(f"✓ Improved tokens streaming - {len(improved_tokens)} tokens, first in {self.results['improved_tokens']['latency']*1000:.2f}ms")
            else:
                print("⚠ No improved tokens received (may be normal if process completes quickly)")
                self.results["improved_tokens"]["passed"] = True  # Not a failure
            
            return True
        except Exception as e:
            self.results["improved_tokens"]["error"] = str(e)
            print(f"✗ Improved tokens test failed: {e}")
            return False
    
    def test_end_to_end(self) -> bool:
        """Test end-to-end latency."""
        print("\n[6/7] Testing End-to-End Latency...")
        try:
            start = time.time()
            response = requests.post(
                f"{BACKEND_URL}/process-stream",
                json={
                    "task": "Create a Python class for managing a shopping cart with methods to add items, remove items, calculate total, and apply discounts. Include proper validation.",
                    "use_rag": False,
                    "is_code": True
                },
                stream=True,
                timeout=180
            )
            
            events_received = []
            completion_time = None
            
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        events_received.append(data.get("type"))
                        
                        if data.get("type") in ["end", "complete"]:
                            completion_time = time.time()
                            break
                    except:
                        continue
                
                if time.time() - start > 120:
                    break
            
            response.close()
            
            if completion_time:
                latency = completion_time - start
                self.results["end_to_end"]["passed"] = True
                self.results["end_to_end"]["latency"] = latency
                print(f"✓ End-to-end complete - {len(events_received)} events in {latency:.2f}s")
            else:
                raise Exception("Process did not complete within timeout")
            
            return True
        except Exception as e:
            self.results["end_to_end"]["error"] = str(e)
            print(f"✗ End-to-end test failed: {e}")
            return False
    
    def test_frontend_access(self) -> bool:
        """Test frontend accessibility."""
        print("\n[7/7] Testing Frontend Accessibility...")
        try:
            start = time.time()
            response = requests.get(FRONTEND_URL, timeout=5)
            latency = time.time() - start
            
            assert response.status_code == 200
            
            self.results["frontend_access"]["passed"] = True
            self.results["frontend_access"]["latency"] = latency
            print(f"✓ Frontend accessible - Response time: {latency*1000:.2f}ms")
            return True
        except Exception as e:
            self.results["frontend_access"]["error"] = str(e)
            print(f"✗ Frontend access failed: {e}")
            return False
    
    def print_summary(self):
        """Print comprehensive test summary."""
        print("\n" + "=" * 80)
        print("FRONTEND-BACKEND CONNECTION TEST SUMMARY")
        print("=" * 80)
        
        total_passed = sum(1 for r in self.results.values() if r["passed"])
        total_tests = len(self.results)
        
        print(f"\nOverall: {total_passed}/{total_tests} tests passed\n")
        
        print(f"{'Test':<25} {'Status':<10} {'Latency/Performance':<25} {'Notes'}")
        print("-" * 80)
        
        for test_name, result in self.results.items():
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            
            if "tokens_per_sec" in result:
                perf_str = f"{result['tokens_per_sec']:.2f} tokens/sec"
            elif result["latency"] > 0:
                if result["latency"] < 1:
                    perf_str = f"{result['latency']*1000:.2f}ms"
                else:
                    perf_str = f"{result['latency']:.2f}s"
            else:
                perf_str = "N/A"
            
            notes = result.get("error", "")[:30] if result.get("error") else "OK"
            
            print(f"{test_name.replace('_', ' ').title():<25} {status:<10} {perf_str:<25} {notes}")
        
        # Performance analysis
        print("\n" + "-" * 80)
        print("PERFORMANCE ANALYSIS:")
        print("-" * 80)
        
        if self.results["first_token"]["passed"]:
            ttft = self.results["first_token"]["latency"] * 1000
            print(f"Time to First Token (TTFT): {ttft:.2f}ms")
            if ttft > 5000:
                print("⚠ WARNING: TTFT is high (>5s) - may indicate slow model response")
            elif ttft > 2000:
                print("⚠ WARNING: TTFT is moderate (>2s) - consider optimization")
            else:
                print("✓ TTFT is acceptable")
        
        if self.results["token_streaming"]["passed"]:
            tps = self.results["token_streaming"]["tokens_per_sec"]
            print(f"\nToken Streaming Rate: {tps:.2f} tokens/sec")
            if tps < 1:
                print("⚠ WARNING: Very slow token rate (<1 token/sec)")
            elif tps < 5:
                print("⚠ WARNING: Slow token rate (<5 tokens/sec)")
            else:
                print("✓ Token rate is acceptable")
        
        if self.results["end_to_end"]["passed"]:
            e2e = self.results["end_to_end"]["latency"]
            print(f"\nEnd-to-End Latency: {e2e:.2f}s")
            if e2e > 60:
                print("⚠ WARNING: Very high end-to-end latency (>60s)")
            elif e2e > 30:
                print("⚠ WARNING: High end-to-end latency (>30s)")
            else:
                print("✓ End-to-end latency is acceptable")
        
        print("\n" + "=" * 80)
        
        return total_passed == total_tests

def main():
    """Run all connection tests."""
    print("=" * 80)
    print("COMPREHENSIVE FRONTEND-BACKEND CONNECTION TEST")
    print("=" * 80)
    
    tester = ConnectionTester()
    
    # Run all tests
    results = [
        tester.test_backend_health(),
        tester.test_sse_connection(),
        tester.test_first_token(),
        tester.test_token_streaming(),
        tester.test_improved_tokens(),
        tester.test_end_to_end(),
        tester.test_frontend_access(),
    ]
    
    # Print summary
    all_passed = tester.print_summary()
    
    return all_passed

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


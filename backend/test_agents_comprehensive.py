"""Comprehensive test suite for all backend agents with latency measurements."""
import asyncio
import time
import sys
from typing import Dict, List
from orchestrator import Orchestrator
from agents import Yantra, Sutra, Agni, Smriti
from rag.retriever import SimpleRAGRetriever
from evaluation.evaluator import Evaluator

class AgentTester:
    """Comprehensive agent testing with latency measurements."""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.results = {
            "yantra": {"passed": False, "latency": 0, "error": None},
            "sutra": {"passed": False, "latency": 0, "error": None},
            "agni": {"passed": False, "latency": 0, "error": None},
            "smriti": {"passed": False, "latency": 0, "error": None},
            "rag": {"passed": False, "latency": 0, "error": None},
            "evaluator": {"passed": False, "latency": 0, "error": None},
            "orchestrator": {"passed": False, "latency": 0, "error": None},
        }
    
    async def test_yantra(self) -> bool:
        """Test Yantra agent with latency measurement."""
        print("\n[1/7] Testing Yantra (Generation Agent)...")
        try:
            start = time.time()
            result = await self.orchestrator.yantra.process(
                task="Write a Python function to add two numbers",
                context=None,
                rag_chunks=None,
                past_examples=None
            )
            latency = time.time() - start
            
            assert "output" in result
            assert len(result["output"]) > 0
            
            self.results["yantra"]["passed"] = True
            self.results["yantra"]["latency"] = latency
            print(f"✓ Yantra working - {len(result['output'])} chars in {latency:.2f}s")
            return True
        except Exception as e:
            self.results["yantra"]["error"] = str(e)
            print(f"✗ Yantra failed: {e}")
            return False
    
    async def test_sutra(self) -> bool:
        """Test Sutra agent with latency measurement."""
        print("\n[2/7] Testing Sutra (Critique Agent)...")
        try:
            test_output = "def add(a, b): return a + b"
            start = time.time()
            result = await self.orchestrator.sutra.process(
                yantra_output=test_output,
                original_task="Write a function to add two numbers",
                rag_chunks=None
            )
            latency = time.time() - start
            
            assert "critique" in result
            assert len(result["critique"]) > 0
            
            self.results["sutra"]["passed"] = True
            self.results["sutra"]["latency"] = latency
            print(f"✓ Sutra working - {len(result['critique'])} chars in {latency:.2f}s")
            return True
        except Exception as e:
            self.results["sutra"]["error"] = str(e)
            print(f"✗ Sutra failed: {e}")
            return False
    
    async def test_agni(self) -> bool:
        """Test Agni agent with latency measurement."""
        print("\n[3/7] Testing Agni (Improvement Agent)...")
        try:
            test_output = "def add(a, b): return a + b"
            test_critique = "Add docstring and type hints"
            start = time.time()
            result = await self.orchestrator.agni.process(
                original_output=test_output,
                critique=test_critique,
                task="Write a function to add two numbers",
                rag_chunks=None
            )
            latency = time.time() - start
            
            assert "improved_output" in result
            assert len(result["improved_output"]) > 0
            
            self.results["agni"]["passed"] = True
            self.results["agni"]["latency"] = latency
            print(f"✓ Agni working - {len(result['improved_output'])} chars in {latency:.2f}s")
            return True
        except Exception as e:
            self.results["agni"]["error"] = str(e)
            print(f"✗ Agni failed: {e}")
            return False
    
    def test_smriti(self) -> bool:
        """Test Smriti (Memory) agent."""
        print("\n[4/7] Testing Smriti (Memory Agent)...")
        try:
            start = time.time()
            # Store a solution
            self.orchestrator.smriti.store(
                task="test task",
                solution="test solution",
                quality_score=0.8,
                metadata={"test": True}
            )
            
            # Retrieve similar
            similar = self.orchestrator.smriti.retrieve_similar("test task", limit=1)
            latency = time.time() - start
            
            self.results["smriti"]["passed"] = True
            self.results["smriti"]["latency"] = latency
            print(f"✓ Smriti working - Retrieved {len(similar)} similar in {latency:.4f}s")
            return True
        except Exception as e:
            self.results["smriti"]["error"] = str(e)
            print(f"✗ Smriti failed: {e}")
            return False
    
    def test_rag(self) -> bool:
        """Test RAG retriever."""
        print("\n[5/7] Testing RAG Retriever...")
        try:
            start = time.time()
            chunks = self.orchestrator.rag.retrieve("test query", top_k=3)
            latency = time.time() - start
            
            self.results["rag"]["passed"] = True
            self.results["rag"]["latency"] = latency
            print(f"✓ RAG working - Retrieved {len(chunks)} chunks in {latency:.4f}s")
            return True
        except Exception as e:
            self.results["rag"]["error"] = str(e)
            print(f"✗ RAG failed: {e}")
            return False
    
    def test_evaluator(self) -> bool:
        """Test Evaluator."""
        print("\n[6/7] Testing Evaluator...")
        try:
            start = time.time()
            result = self.orchestrator.evaluator.evaluate(
                solution="def add(a, b):\n    '''Adds two numbers'''\n    return a + b",
                task="Write a function to add two numbers",
                is_code=True,
                rag_chunks=None
            )
            latency = time.time() - start
            
            assert "total" in result
            assert 0 <= result["total"] <= 1
            
            self.results["evaluator"]["passed"] = True
            self.results["evaluator"]["latency"] = latency
            print(f"✓ Evaluator working - Score: {result['total']:.2f} in {latency:.4f}s")
            return True
        except Exception as e:
            self.results["evaluator"]["error"] = str(e)
            print(f"✗ Evaluator failed: {e}")
            return False
    
    async def test_orchestrator(self) -> bool:
        """Test full orchestrator with latency measurement."""
        print("\n[7/7] Testing Full Orchestrator Process...")
        try:
            start = time.time()
            result = await self.orchestrator.process(
                task="Write a function to multiply two numbers",
                context=None,
                use_rag=False,
                is_code=True
            )
            latency = time.time() - start
            
            assert "final_solution" in result
            assert "final_score" in result
            assert "iterations" in result
            assert len(result["iterations"]) > 0
            
            self.results["orchestrator"]["passed"] = True
            self.results["orchestrator"]["latency"] = latency
            print(f"✓ Orchestrator working - {result['total_iterations']} iterations, score: {result['final_score']:.2f} in {latency:.2f}s")
            return True
        except Exception as e:
            self.results["orchestrator"]["error"] = str(e)
            print(f"✗ Orchestrator failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def print_summary(self):
        """Print test summary with latency analysis."""
        print("\n" + "=" * 70)
        print("TEST SUMMARY & LATENCY ANALYSIS")
        print("=" * 70)
        
        total_passed = sum(1 for r in self.results.values() if r["passed"])
        total_tests = len(self.results)
        
        print(f"\nOverall: {total_passed}/{total_tests} tests passed\n")
        
        print(f"{'Agent':<15} {'Status':<10} {'Latency':<15} {'Notes'}")
        print("-" * 70)
        
        for agent, result in self.results.items():
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            latency_str = f"{result['latency']:.3f}s" if result["latency"] > 0 else "N/A"
            notes = result.get("error", "")[:30] if result.get("error") else "OK"
            
            print(f"{agent.capitalize():<15} {status:<10} {latency_str:<15} {notes}")
        
        # Latency analysis
        print("\n" + "-" * 70)
        print("LATENCY ANALYSIS:")
        print("-" * 70)
        
        agent_latencies = {k: v["latency"] for k, v in self.results.items() if v["passed"] and v["latency"] > 0}
        
        if agent_latencies:
            total_latency = sum(agent_latencies.values())
            avg_latency = total_latency / len(agent_latencies)
            max_agent = max(agent_latencies.items(), key=lambda x: x[1])
            min_agent = min(agent_latencies.items(), key=lambda x: x[1])
            
            print(f"Total Agent Latency: {total_latency:.3f}s")
            print(f"Average Agent Latency: {avg_latency:.3f}s")
            print(f"Slowest Agent: {max_agent[0]} ({max_agent[1]:.3f}s)")
            print(f"Fastest Agent: {min_agent[0]} ({min_agent[1]:.3f}s)")
            
            # Identify bottlenecks
            print("\nBOTTLENECK ANALYSIS:")
            bottlenecks = [k for k, v in agent_latencies.items() if v > avg_latency * 1.5]
            if bottlenecks:
                print(f"⚠ Potential bottlenecks: {', '.join(bottlenecks)}")
            else:
                print("✓ No significant bottlenecks detected")
        
        print("\n" + "=" * 70)
        
        return total_passed == total_tests

async def main():
    """Run all tests."""
    print("=" * 70)
    print("COMPREHENSIVE BACKEND AGENT TEST SUITE")
    print("=" * 70)
    
    tester = AgentTester()
    
    # Run all tests
    results = await asyncio.gather(
        tester.test_yantra(),
        tester.test_sutra(),
        tester.test_agni(),
        asyncio.to_thread(tester.test_smriti),
        asyncio.to_thread(tester.test_rag),
        asyncio.to_thread(tester.test_evaluator),
        tester.test_orchestrator(),
        return_exceptions=True
    )
    
    # Print summary
    all_passed = tester.print_summary()
    
    return all_passed

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


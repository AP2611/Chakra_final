"""Simple test script to verify agent system setup."""
import asyncio
import sys
from agents import Yantra, Sutra, Agni
from orchestrator import Orchestrator


async def test_single_agent():
    """Test a single agent."""
    print("Testing Yantra agent...")
    yantra = Yantra()
    try:
        result = await yantra.process(task="Write a Python function to calculate factorial")
        print(f"✓ Yantra test passed")
        print(f"Output length: {len(result['output'])} characters")
        return True
    except Exception as e:
        print(f"✗ Yantra test failed: {e}")
        return False


async def test_orchestrator():
    """Test the full orchestrator."""
    print("\nTesting Orchestrator...")
    orchestrator = Orchestrator(max_iterations=1)  # Just one iteration for testing
    try:
        result = await orchestrator.process(
            task="Write a Python function to reverse a string",
            is_code=True
        )
        print(f"✓ Orchestrator test passed")
        print(f"Final score: {result['final_score']:.2f}")
        print(f"Iterations: {result['total_iterations']}")
        return True
    except Exception as e:
        print(f"✗ Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Agent System Test Suite")
    print("=" * 50)
    print("\nMake sure Ollama is running with qwen2.5:1.5b model!")
    print("Run: ollama pull qwen2.5:1.5b\n")
    
    # Test single agent
    agent_ok = await test_single_agent()
    
    if agent_ok:
        # Test orchestrator
        orchestrator_ok = await test_orchestrator()
        
        if orchestrator_ok:
            print("\n" + "=" * 50)
            print("✓ All tests passed!")
            print("=" * 50)
            sys.exit(0)
        else:
            print("\n" + "=" * 50)
            print("✗ Orchestrator test failed")
            print("=" * 50)
            sys.exit(1)
    else:
        print("\n" + "=" * 50)
        print("✗ Agent test failed - check Ollama setup")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


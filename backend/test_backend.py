"""Test script to verify all backend modules are working."""
import asyncio
import sys
from orchestrator import Orchestrator

async def test_backend():
    """Test all backend modules."""
    print("=" * 60)
    print("Testing Chakra Backend Modules")
    print("=" * 60)
    
    orchestrator = Orchestrator()
    
    # Test 1: Health check
    print("\n[1/6] Testing Orchestrator initialization...")
    try:
        assert orchestrator.yantra is not None
        assert orchestrator.sutra is not None
        assert orchestrator.agni is not None
        assert orchestrator.smriti is not None
        assert orchestrator.rag is not None
        assert orchestrator.evaluator is not None
        print("✓ All agents initialized successfully")
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return False
    
    # Test 2: Yantra (Generation)
    print("\n[2/6] Testing Yantra (Generation Agent)...")
    try:
        result = await orchestrator.yantra.process(
            task="Write a simple hello world function in Python",
            context=None,
            rag_chunks=None,
            past_examples=None
        )
        assert "output" in result
        assert len(result["output"]) > 0
        print(f"✓ Yantra working - Generated {len(result['output'])} characters")
    except Exception as e:
        print(f"✗ Yantra test failed: {e}")
        return False
    
    # Test 3: Sutra (Critique)
    print("\n[3/6] Testing Sutra (Critique Agent)...")
    try:
        test_output = "def hello(): print('hello world')"
        result = await orchestrator.sutra.process(
            yantra_output=test_output,
            original_task="Write a hello world function",
            rag_chunks=None
        )
        assert "critique" in result
        assert len(result["critique"]) > 0
        print(f"✓ Sutra working - Generated critique ({len(result['critique'])} chars)")
    except Exception as e:
        print(f"✗ Sutra test failed: {e}")
        return False
    
    # Test 4: Agni (Improvement)
    print("\n[4/6] Testing Agni (Improvement Agent)...")
    try:
        test_output = "def hello(): print('hello world')"
        test_critique = "Add docstring and error handling"
        result = await orchestrator.agni.process(
            original_output=test_output,
            critique=test_critique,
            task="Write a hello world function",
            rag_chunks=None
        )
        assert "improved_output" in result
        assert len(result["improved_output"]) > 0
        print(f"✓ Agni working - Generated improved output ({len(result['improved_output'])} chars)")
    except Exception as e:
        print(f"✗ Agni test failed: {e}")
        return False
    
    # Test 5: Evaluator
    print("\n[5/6] Testing Evaluator...")
    try:
        test_solution = "def hello():\n    '''Prints hello world'''\n    print('hello world')"
        result = orchestrator.evaluator.evaluate(
            solution=test_solution,
            task="Write a hello world function",
            is_code=True,
            rag_chunks=None
        )
        assert "total" in result
        assert 0 <= result["total"] <= 1
        print(f"✓ Evaluator working - Score: {result['total']:.2f}")
    except Exception as e:
        print(f"✗ Evaluator test failed: {e}")
        return False
    
    # Test 6: Full Orchestrator Process
    print("\n[6/6] Testing Full Orchestrator Process...")
    try:
        result = await orchestrator.process(
            task="Write a function to add two numbers",
            context=None,
            use_rag=False,
            is_code=True
        )
        assert "final_solution" in result
        assert "final_score" in result
        assert "iterations" in result
        assert len(result["iterations"]) > 0
        print(f"✓ Full process working - {result['total_iterations']} iterations, score: {result['final_score']:.2f}")
    except Exception as e:
        print(f"✗ Full process test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✓ All backend tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_backend())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


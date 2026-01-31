# Diagnostic Results - Code Assistant & Chatbot Issues

## Issue 1: First Generated Code Changes to JavaScript

### Root Cause Analysis

**Problem**: When refined version is generated, the first generated code changes to JavaScript code.

**Potential Causes**:

1. **Token Routing Issue in `onToken` handler** (CodeAssistant.tsx lines 83-91):
   - The functional update logic checks `currentFirstCode.startsWith(prev)`
   - If `prev` (React state) is stale or doesn't match `currentFirstCode` (closure variable), it falls back to `prev + token`
   - This can cause tokens to be incorrectly appended if state is out of sync

2. **`improved_token` Events Routed Incorrectly**:
   - In `api.ts` line 89, `improved_token` events are routed to `onToken`
   - Even though `onEvent` is called first (line 93), if `isInImprovementPhase` flag is not set in time, tokens might go to `firstGeneratedCode`

3. **Phase Flag Timing Issue**:
   - `isInImprovementPhase` is set in `improving_started` event handler
   - But `improved_token` events might arrive before `improving_started` event is processed
   - This causes tokens to be routed to `firstGeneratedCode` instead of `refinedCode`

### Solution

1. **Fix `onToken` handler** to use closure variable directly instead of functional update for first code
2. **Ensure `improved_token` tokens never go to `firstGeneratedCode`** by checking phase flag before routing
3. **Set phase flag immediately** when `improving_started` or `improved_token` is received

---

## Issue 2: Chatbot Terminates with Error When Tokens Exceed Limit

### Root Cause Analysis

**Problem**: When first LLM output exceeds certain number of tokens, chatbot automatically terminates and says error occurred.

**Potential Causes**:

1. **Ollama Token Limit Behavior**:
   - Ollama's `num_predict` parameter limits output tokens
   - When limit is reached, Ollama stops generating (doesn't error, just stops)
   - But if there's an error in parsing or processing, it might throw an exception

2. **Backend Error Handling**:
   - In `base_agent.py`, if Ollama stream ends abruptly or has parsing errors, exceptions might not be caught
   - In `api.py` line 351, exceptions are caught and sent as error events
   - But if the error occurs during token streaming, it might not be properly handled

3. **Token Limit Too Low**:
   - Fast mode: 512 tokens for chatbot
   - Normal mode: 1024 tokens for chatbot
   - If response needs more tokens, it gets truncated
   - Truncation might cause parsing errors or incomplete responses

4. **Streaming Error Handling**:
   - In `base_agent.py` lines 110-160, streaming errors might not be properly caught
   - If Ollama returns an error response (not just stopping), it might not be handled

### Solution

1. **Increase token limits** for chatbot responses (or make them configurable)
2. **Handle Ollama truncation gracefully** - don't treat it as an error
3. **Catch and handle streaming errors** properly in `base_agent.py`
4. **Add error recovery** - if token limit is reached, send a completion event instead of error

---

## Test Results

Run `test_simple_diagnostic.py` to verify both issues:

```bash
python3 test_simple_diagnostic.py
```

This will:
1. Test code generation and check if first code changes
2. Test chatbot with long prompt and check for token limit errors



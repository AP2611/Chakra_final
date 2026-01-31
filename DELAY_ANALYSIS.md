# Refined Output Delay Analysis

## Problem Identified

After testing with realistic inputs, the following delays were found:

### Test Results Summary

1. **First Generation (Yantra)**: ✅ Working well
   - Time to first token: 0.6-1.4 seconds
   - Complete generation: 2-6 seconds
   - Tokens stream properly

2. **Refined Output (Agni)**: ❌ **MAJOR DELAY**
   - `improving_started` event fires immediately after first generation
   - **NO `improved_token` events are being sent**
   - Only a single `improved` event is sent after 10-11 seconds with the complete solution
   - **Delay: 10-11 seconds** between `improving_started` and `improved` event

### Root Cause

The issue is that **Agni's streaming is not working**. The `async for token in orchestrator.agni._call_ollama_stream(...)` loop is not yielding tokens as they're generated. Instead:

1. Agni waits for Ollama to generate the complete response
2. All tokens are accumulated in `agni_output`
3. Only after completion, a single `improved` event is sent with the full solution

This means:
- Users see the first generation quickly (2-6s)
- Then they wait 10-11 seconds with no feedback
- Finally, the complete improved solution appears all at once

### Evidence

From curl test output:
```
data: {"type": "improving_started", "iteration": 1, "status": "improving"}
[10-11 second gap with NO events]
data: {"type": "improved", "iteration": 1, "solution": "[COMPLETE LONG SOLUTION]"}
```

**No `improved_token` events are present in the stream.**

## Solution

The problem is likely one of these:

1. **Ollama streaming not working**: Ollama might not be streaming tokens properly
2. **Buffer issue**: The async generator might be buffering tokens
3. **Response format**: Ollama's response format might be different than expected

### Recommended Fix

1. **Add immediate feedback**: Send a status event when Agni starts processing
2. **Fix streaming**: Ensure `_call_ollama_stream` actually yields tokens as they arrive
3. **Add timeout/flush**: Force flush tokens if they're being buffered
4. **Fallback**: If streaming fails, at least send progress updates

### Immediate Workaround

Until streaming is fixed, we can:
1. Show a "Improving..." message immediately when `improving_started` fires
2. Add a progress indicator (even if we can't show tokens)
3. Reduce Agni's token limit to speed up completion
4. Consider running Agni in parallel with showing first response

## Performance Impact

- **Current**: 2-6s (first) + 10-11s (wait) + instant (complete) = **12-17 seconds total**
- **Expected with streaming**: 2-6s (first) + 0.5-2s (first improved token) + streaming = **2.5-8 seconds perceived**

The delay is **10-11 seconds** where users see nothing, which is the main UX issue.


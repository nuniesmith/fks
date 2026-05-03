# xAI Grok JSON Structured Output

## Overview

This document describes how the FKS audit system uses xAI Grok's JSON mode to ensure reliable, parseable responses for code analysis.

**Status**: ✅ **Implemented** (2026-01-08)

**Key Features**:
- JSON mode enabled via `response_format: { "type": "json_object" }`
- Explicit JSON schemas in system prompts
- Multi-level JSON extraction fallbacks
- Detailed error logging with response previews

---

## How It Works

### 1. Request Format

The audit system sends requests to xAI's Chat Completions API with JSON mode enabled:

```json
{
  "model": "grok-4-1-fast-reasoning",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert code auditor. Analyze the provided code and respond ONLY with valid JSON..."
    },
    {
      "role": "user",
      "content": "File: src/main.rs\n\n```\nfn main() {...}\n```\n\nProvide a detailed security and quality analysis."
    }
  ],
  "max_tokens": 4096,
  "temperature": 0.7,
  "stream": false,
  "response_format": {
    "type": "json_object"
  }
}
```

**Key Field**: `response_format.type = "json_object"` tells Grok to return valid JSON.

### 2. System Prompt Strategy

Each analysis type includes an **explicit JSON schema** in the system prompt. This ensures Grok knows exactly what structure to return.

#### Example: File Analysis Schema

```text
You are an expert code auditor. Analyze the provided code and respond ONLY with valid JSON.
Do not include any text before or after the JSON. The JSON must have these exact fields:

{
  "security_rating": "A-F letter grade",
  "importance": 0.0-1.0 decimal number,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "message": "description",
      "line": optional_number
    }
  ],
  "summary": "brief analysis summary"
}
```

**Why This Works**:
- Clear, unambiguous structure
- Type hints for each field
- Examples of valid values
- Explicit instruction to return ONLY JSON

### 3. Response Parsing Strategy

The audit system uses a **multi-level fallback** approach to extract JSON from responses:

```rust
// Level 1: Try parsing response directly as JSON
if let Ok(result) = serde_json::from_str::<LlmAnalysisResult>(response) {
    return Ok(result);
}

// Level 2: Extract from markdown code blocks (```json ... ```)
if let Some(json_str) = self.extract_json_from_markdown(response) {
    if let Ok(result) = serde_json::from_str::<LlmAnalysisResult>(&json_str) {
        return Ok(result);
    }
}

// Level 3: Find first JSON object anywhere in text ({ ... })
if let Some(json_str) = self.extract_json_object(response) {
    if let Ok(result) = serde_json::from_str::<LlmAnalysisResult>(&json_str) {
        return Ok(result);
    }
}

// Level 4: Fallback with warning
warn!("Failed to parse LLM response as JSON, using fallback. Response preview: {}", preview);
```

**Benefits**:
- Handles various response formats gracefully
- Logs issues for debugging without failing the audit
- Provides detailed error messages with response previews

---

## Analysis Types and Schemas

### 1. File Analysis (`LlmAnalysisResult`)

**Use Case**: Analyze individual code files for security, quality, and importance.

**Schema**:
```json
{
  "security_rating": "A",
  "importance": 0.8,
  "issues": [
    {
      "severity": "high",
      "message": "Use of unsafe block without documentation",
      "line": 42
    }
  ],
  "summary": "Core trading logic component with high risk exposure"
}
```

**Fields**:
- `security_rating` (string): Letter grade A-F
- `importance` (float): 0.0-1.0 decimal
- `issues` (array): List of found issues
  - `severity`: "critical" | "high" | "medium" | "low"
  - `message`: Description of the issue
  - `line` (optional): Line number
- `summary` (string): Brief analysis summary

---

### 2. Codebase Analysis (`CodebaseAnalysisResult`)

**Use Case**: High-level analysis of entire codebase structure.

**Schema**:
```json
{
  "deprecated_files": ["src/legacy/old_module.rs"],
  "missing_types": [
    {
      "file": "src/trading.rs",
      "issue": "Missing type annotations on public API"
    }
  ],
  "security_concerns": [
    {
      "severity": "critical",
      "file": "src/config.rs",
      "message": "Hardcoded API key detected"
    }
  ],
  "architecture_issues": [
    {
      "file": "src/forward/executor.rs",
      "issue": "Blocking I/O in async context"
    }
  ],
  "recommended_tags": [
    {
      "file": "src/legacy/module.rs",
      "tag": "@audit-tag: legacy"
    }
  ]
}
```

**Fields**:
- `deprecated_files`: List of file paths
- `missing_types`: Array of type annotation issues
- `security_concerns`: Array of security findings with severity
- `architecture_issues`: Array of architectural violations
- `recommended_tags`: Array of suggested audit tags

---

### 3. Deep Analysis (`DeepAnalysisResult`)

**Use Case**: Comprehensive analysis using full 2M context window.

**Schema**:
```json
{
  "logic_drift": [
    "Forward service contains business logic that should be in Janus core"
  ],
  "dead_code": [
    "src/old_strategy.rs",
    "src/deprecated_indicators.rs"
  ],
  "safety_issues": [
    {
      "file": "src/trading/executor.rs",
      "line": 123,
      "severity": "critical",
      "message": "unwrap() in hot path can cause panic under load"
    }
  ],
  "mathematical_errors": [
    {
      "file": "src/indicators/gaf.rs",
      "line": 456,
      "paper_reference": "Part II, Section 3.2, Eq. 7",
      "error": "GAF normalization missing tanh activation"
    }
  ],
  "incomplete_code": [
    "src/strategies/incomplete_strategy.rs"
  ],
  "tasks": [
    {
      "file": "src/trading/executor.rs",
      "line": 123,
      "priority": "Critical",
      "category": "SAFETY",
      "paper_reference": null,
      "description": "Replace unwrap() with proper error handling",
      "suggested_fix": "Use .map_err() and propagate errors to CNS monitoring"
    }
  ]
}
```

---

### 4. Standard Questionnaire (`Vec<FileAuditResult>`)

**Use Case**: Run standardized audit questionnaire on multiple files.

**Schema**:
```json
{
  "file_audits": [
    {
      "file": "src/forward/executor.rs",
      "reachable": true,
      "brain_region": "Basal Ganglia",
      "service_boundary": "Forward",
      "compliance_issues": [
        {
          "type": "PERFORMANCE",
          "description": "Blocking I/O detected in async function",
          "paper_reference": null
        }
      ],
      "incomplete": false,
      "suggested_tags": ["neuromorphic", "forward-path", "hot-path"],
      "improvement": "Convert blocking file I/O to async using tokio::fs",
      "priority": "High"
    }
  ]
}
```

---

## Implementation Details

### Code Location

- **Main implementation**: `fks/src/audit/src/llm.rs`
- **Request structure**: `ChatCompletionRequest` struct (lines ~875-885)
- **Response format**: `ResponseFormat` struct (lines ~890-895)
- **Parsing functions**:
  - `parse_analysis_response()` (lines ~830-855)
  - `parse_codebase_response()` (lines ~895-930)
  - `parse_deep_analysis_response()` (lines ~436-470)
  - `parse_questionnaire_response()` (lines ~473-530)

### JSON Extraction Helpers

#### `extract_json_from_markdown()`
Extracts JSON from markdown code blocks:
```markdown
```json
{ "key": "value" }
```
```

#### `extract_json_object()`
Finds first complete JSON object `{ ... }` anywhere in text:
- Handles nested braces
- Respects string escaping
- Counts brace depth to find matching closing brace

---

## Testing

### Local Testing

1. Set debug directory:
   ```bash
   export AUDIT_DEBUG_DIR=./debug
   mkdir -p debug
   ```

2. Run audit:
   ```bash
   cargo run --bin fks-audit -- analyze --file src/main.rs
   ```

3. Check debug files if parsing fails:
   - `debug/llm-response-structure.json` - Full API response
   - `debug/llm-error-response.json` - Error details
   - `debug/questionnaire-failed-response.txt` - Raw response text

### CI Testing

GitHub Actions workflow automatically runs audits. Check logs for:

```
✅ Success indicators:
- "XAI usage: prompt=... completion=... total=..."
- "Analyzed file: ..."
- No "Failed to parse LLM response" warnings

⚠️ Warning indicators:
- "Failed to parse LLM response as JSON, using fallback"
- "Response preview: ..." (shows first 500 chars)
```

---

## Troubleshooting

### Issue: "Failed to parse LLM response as JSON"

**Symptoms**: Warning logs with response preview showing non-JSON text.

**Causes**:
1. Grok returned explanation text instead of pure JSON
2. JSON wrapped in markdown but extraction failed
3. Malformed JSON (missing quotes, trailing commas)

**Solutions**:

1. **Check response preview in logs**:
   ```
   WARN Failed to parse LLM response as JSON, using fallback. Response preview: Here is the analysis:...
   ```
   → Response starts with text, not JSON

2. **Verify `response_format` is set**:
   ```rust
   response_format: Some(ResponseFormat {
       format_type: "json_object".to_string(),
   })
   ```

3. **Check system prompt clarity**:
   - Should start with "RESPOND ONLY WITH VALID JSON"
   - Must include complete schema example
   - Should explicitly say "Do not include any text before or after"

4. **Enable debug mode**:
   ```bash
   export AUDIT_DEBUG_DIR=./debug
   export RUST_LOG=debug
   ```
   Then inspect `debug/llm-response-structure.json`

---

### Issue: JSON mode not supported error

**Symptoms**: API error "json_object format not supported"

**Cause**: Model or API version doesn't support JSON mode.

**Solution**: Check xAI documentation for JSON mode compatibility:
- `grok-4-1-fast-reasoning` - ✅ Supported
- `grok-2-latest` - ✅ Supported
- Older models - May not support

---

### Issue: Partial JSON in response

**Symptoms**: Response contains valid JSON but also explanatory text.

**Example**:
```
The analysis results are:
{
  "security_rating": "B",
  ...
}
I hope this helps!
```

**Solution**: The `extract_json_object()` fallback should handle this. If not:
1. Check that extraction is enabled in parsing function
2. Verify the JSON object is complete (matching braces)
3. Strengthen system prompt to emphasize "ONLY JSON, no other text"

---

### Issue: Schema mismatch

**Symptoms**: JSON parses but has wrong fields or types.

**Example**:
```json
{
  "rating": "B",  // Should be "security_rating"
  "score": 0.8    // Should be "importance"
}
```

**Solution**:
1. Update system prompt to show exact field names
2. Add examples with correct field names
3. Consider adding a validation step before parsing

---

## Cost Optimization

### Token Usage

JSON mode can increase token usage slightly because:
- Schema examples in system prompt add ~100-200 tokens
- Grok may use internal reasoning tokens to structure output

**Current rates** (grok-4-1-fast-reasoning):
- Input: $0.20 per 1M tokens
- Cached input: $0.05 per 1M tokens
- Output: $0.50 per 1M tokens
- Reasoning tokens: Counted as output

### Monitoring Costs

Check logs for usage stats:
```
XAI usage: prompt=1234 (cached=567), completion=890 (reasoning=123), total=2124
XAI cost: input=$0.0001, cached=$0.0000, output=$0.0004, total=$0.0006
```

### Tips to Reduce Costs

1. **Use caching**: System prompts are stable, Grok caches them automatically
2. **Batch files**: Analyze multiple files in one request when possible
3. **Lower max_tokens**: Set to minimum needed for response
4. **Adjust temperature**: Lower values (0.3-0.5) may produce more consistent JSON faster

---

## Future Enhancements

### Considered Improvements

1. **Strict Schema Validation**:
   - Use JSON Schema to validate responses
   - Reject invalid responses with retry

2. **Re-prompting on Parse Failure**:
   - If parsing fails, send response back to Grok
   - Ask: "Please reformat the above as valid JSON matching this schema: {...}"
   - Auto-retry once

3. **Structured Outputs API**:
   - When xAI adds schema-enforcement API
   - Define schemas in request, get guaranteed-valid JSON
   - Eliminates need for fallback parsing

4. **Response Caching**:
   - Cache analysis results by file hash
   - Skip LLM call if file unchanged

---

## References

- **xAI API Documentation**: https://docs.x.ai/api
- **OpenAI Chat Completions**: https://platform.openai.com/docs/api-reference/chat
- **JSON Mode Guide**: https://platform.openai.com/docs/guides/json-mode
- **Implementation Fix**: `docs/implementation/xai_integration_fix.md`
- **Quick Reference**: `docs/implementation/xai_quick_reference.md`

---

## Changelog

### 2026-01-08
- ✅ Added `response_format: { "type": "json_object" }` to requests
- ✅ Updated all system prompts with explicit JSON schemas
- ✅ Implemented `extract_json_object()` fallback parser
- ✅ Added detailed error logging with response previews
- ✅ Improved all parsing functions with multi-level fallbacks
- 📝 Created this documentation

### Next Steps
- [ ] Add integration tests with mock xAI server
- [ ] Implement re-prompting on parse failure
- [ ] Add JSON Schema validation
- [ ] Monitor parse success rate in CI metrics
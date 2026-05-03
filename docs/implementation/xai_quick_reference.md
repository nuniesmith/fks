# xAI Grok API - Quick Reference

**Status:** ✅ Ready for Production  
**Last Updated:** 2026-01-08

## 🚀 Quick Start

### 1. Set API Key
```bash
export XAI_API_KEY="xai-your-api-key-here"
```

### 2. Run LLM Audit
```bash
cd src/audit
cargo run --release --bin audit-cli -- llm-audit \
    ../../src/janus \
    --mode full \
    --provider xai \
    --output audit-results.json
```

## 📋 API Essentials

### Endpoint
```
POST https://api.x.ai/v1/chat/completions
```

### Headers
```
Content-Type: application/json
Authorization: Bearer $XAI_API_KEY
```

### Request Body
```json
{
  "model": "grok-4-1-fast-reasoning",
  "messages": [
    {
      "role": "system",
      "content": "You are a code auditor..."
    },
    {
      "role": "user",
      "content": "Analyze this code..."
    }
  ],
  "max_tokens": 4096,
  "temperature": 0.7,
  "stream": false
}
```

### Response Format
```json
{
  "id": "chatcmpl-...",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Analysis results..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 567,
    "total_tokens": 1801,
    "prompt_tokens_details": {
      "cached_tokens": 100
    },
    "completion_tokens_details": {
      "reasoning_tokens": 50
    }
  }
}
```

## 💰 Pricing (grok-4-1-fast-reasoning)

| Token Type | Price per Million | Notes |
|------------|-------------------|-------|
| Input | $0.20 | Standard prompt tokens |
| Cached Input | $0.05 | 75% discount on repeated prompts |
| Output | $0.50 | Response tokens |
| Reasoning | $0.50 | Included in output pricing |

### Cost Example
```
Prompt: 1,000 tokens (100 cached)
Response: 500 tokens (50 reasoning)

Cost = ((1000-100)/1M × $0.20) + (100/1M × $0.05) + (500/1M × $0.50)
     = $0.00018 + $0.000005 + $0.00025
     = $0.000435 per request
```

## 🎯 Available Models

| Model | Best For | Context | Cost |
|-------|----------|---------|------|
| `grok-4-1-fast-reasoning` | Complex analysis, coding | 128K | $0.20/$0.50 |
| `grok-4-1-fast` | Speed-critical tasks | 128K | Lower |
| `grok-4` | Highest quality | 128K | Higher |
| `grok-vision-4` | Image analysis | 128K | Variable |

## 🔧 Code Integration

### Rust (Our Implementation)
```rust
use crate::llm::LlmClient;

let client = LlmClient::new(
    api_key,
    "grok-4-1-fast-reasoning".to_string(),
    4096,  // max_tokens
    0.7,   // temperature
)?;

let result = client.analyze_file(
    &path,
    &content,
    category
).await?;
```

### Python (xAI SDK)
```python
from xai_sdk import Client
from xai_sdk.chat import user, system

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(model="grok-4-1-fast-reasoning")
chat.append(system("You are a code auditor."))
chat.append(user("Analyze this code..."))
response = chat.sample()
```

### Python (OpenAI SDK)
```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

response = client.chat.completions.create(
    model="grok-4-1-fast-reasoning",
    messages=[
        {"role": "system", "content": "You are a code auditor."},
        {"role": "user", "content": "Analyze this code..."}
    ]
)
```

### cURL
```bash
curl https://api.x.ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
    "model": "grok-4-1-fast-reasoning",
    "messages": [
      {"role": "system", "content": "You are a code auditor."},
      {"role": "user", "content": "Analyze this code..."}
    ],
    "max_tokens": 4096,
    "temperature": 0.7
  }'
```

## ⚙️ Configuration

### Environment Variables
```bash
# Required
export XAI_API_KEY="xai-..."

# Optional
export AUDIT_DEBUG_DIR="./debug"          # Save debug logs
export RUST_LOG="audit=debug,info"        # Detailed logging
```

### Config File (audit.toml)
```toml
[llm]
provider = "xai"
model = "grok-4-1-fast-reasoning"
max_tokens = 4096
temperature = 0.7
```

## 📊 Rate Limits

| Tier | Requests/min | Tokens/min | Daily Limit |
|------|--------------|------------|-------------|
| Free | 60 | 100K | 1M tokens |
| Pro | 500 | 2M | 20M tokens |
| Enterprise | Custom | Custom | Custom |

## 🐛 Troubleshooting

### Common Issues

#### "Failed to parse LLM response"
**Fixed!** Ensure you're using `/chat/completions` endpoint, not `/responses`.

#### "401 Unauthorized"
```bash
# Check API key
echo $XAI_API_KEY

# Verify it starts with "xai-"
```

#### "429 Rate Limit"
```
Reduce request frequency or upgrade tier.
Current limits visible at: https://console.x.ai/team/default/usage
```

#### "Model not found"
```
Verify model name exactly:
✅ "grok-4-1-fast-reasoning"
❌ "grok-4.1-fast-reasoning"
❌ "grok4-1-fast-reasoning"
```

## 📈 Monitoring

### Check Usage
```bash
# Via API
curl https://api.x.ai/v1/usage \
  -H "Authorization: Bearer $XAI_API_KEY"

# Via Console
open https://console.x.ai/team/default/usage
```

### Debug Logging
```bash
# Enable debug output
export RUST_LOG=audit::llm=debug

# Run audit with debug
cargo run --release --bin audit-cli -- llm-audit \
    path/to/code --provider xai 2>&1 | grep "XAI usage"
```

Expected output:
```
DEBUG audit::llm: XAI usage: prompt=1234 (cached=100), completion=567 (reasoning=50), total=1801
DEBUG audit::llm: XAI cost: input=$0.0002, cached=$0.0000, output=$0.0003, total=$0.0005
```

## 🔒 Security

### API Key Storage
```bash
# ✅ Good: Environment variable
export XAI_API_KEY="xai-..."

# ✅ Good: Secret management
aws secretsmanager get-secret-value --secret-id xai-api-key

# ❌ Bad: Hardcoded in code
let api_key = "xai-abc123...";  // NEVER DO THIS

# ❌ Bad: Committed to git
echo "XAI_API_KEY=xai-abc123" >> .env
git add .env  // NEVER DO THIS
```

### Best Practices
- Rotate keys every 90 days
- Use separate keys for dev/staging/prod
- Monitor usage for anomalies
- Set billing alerts at console.x.ai

## 📚 Resources

### Official Documentation
- API Docs: https://docs.x.ai
- Console: https://console.x.ai
- Status: https://status.x.ai
- Discord: https://discord.gg/x-ai

### Our Documentation
- Full Implementation Guide: `docs/implementation/xai_integration_fix.md`
- xAI Notes: `docs/audit/notes_xai.md`
- Source Code: `src/audit/src/llm.rs`

### Support
- Email: support@x.ai
- Discord: #help channel
- GitHub: nuniesmith/fks/issues

## 🎓 Tips & Tricks

### Optimize Costs
1. **Use caching**: Repeat system prompts get 75% discount
2. **Set max_tokens**: Prevent runaway responses
3. **Batch requests**: Group multiple analyses
4. **Monitor usage**: Set alerts at $10, $50, $100

### Improve Quality
1. **Specific prompts**: "Find security issues in this Rust code" vs "Analyze this"
2. **Provide context**: Include function signatures, dependencies
3. **Use temperature**: 0.0 for factual, 0.7 for creative, 1.0 for diverse
4. **Iterate**: Refine prompts based on results

### Debugging
```bash
# Save all responses for analysis
export AUDIT_DEBUG_DIR="./debug"

# Check response structure
cat debug/llm-response-structure.json | jq .

# Check for errors
cat debug/llm-error-response.json | jq .error
```

## ✅ Verification Checklist

Before deploying:
- [ ] API key set in environment
- [ ] Using `/chat/completions` endpoint
- [ ] Request has `messages` (not `input`)
- [ ] Parsing `/choices/0/message/content`
- [ ] Logging token usage and costs
- [ ] Error handling in place
- [ ] Rate limiting respected
- [ ] Billing alerts configured

---

**Version:** 1.0.0  
**Maintained by:** FKS Trading Platform Team  
**Last Audit:** 2026-01-08
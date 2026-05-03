# Implementation Guides

This directory contains detailed implementation guides and technical documentation for the FKS Trading Platform.

## 📚 Available Guides

### xAI Grok API Integration

**Status:** ✅ Complete (2026-01-08)

| Document | Description | Audience |
|----------|-------------|----------|
| [xai_integration_fix.md](xai_integration_fix.md) | Complete technical fix documentation with before/after comparison | Developers |
| [xai_quick_reference.md](xai_quick_reference.md) | Quick reference card for daily use | All users |
| [xai_json_structured_output.md](xai_json_structured_output.md) | JSON mode implementation with schemas and troubleshooting | Developers |

#### What Was Fixed

The LLM audit system was failing to correctly parse xAI Grok API responses. Fixed by:

1. ✅ Changed endpoint from `/responses` → `/chat/completions`
2. ✅ Updated request format: `input` → `messages`
3. ✅ Simplified response parsing to use OpenAI-compatible format
4. ✅ Enhanced error logging and debugging support
5. ✅ Added accurate token usage and cost tracking
6. ✅ Implemented JSON mode with `response_format: { "type": "json_object" }`
7. ✅ Added explicit JSON schemas to all system prompts
8. ✅ Implemented multi-level JSON extraction fallbacks

#### Quick Test

```bash
# Set your API key
export XAI_API_KEY="xai-your-key-here"

# Run a test audit
cd src/audit
cargo run --release --bin audit-cli -- llm-audit \
    ../../src/janus \
    --mode full \
    --provider xai \
    --output test-results.json
```

#### Expected Output

```
INFO audit::llm: LLM client initialized: provider=xai, model=grok-4-1-fast-reasoning
INFO audit::llm: Analyzing file with LLM: ../../src/janus/services/api/src/lib.rs
DEBUG audit::llm: XAI usage: prompt=1234 (cached=0), completion=567 (reasoning=50), total=1801
DEBUG audit::llm: XAI cost: input=$0.0002, cached=$0.0000, output=$0.0003, total=$0.0005
```

**No more "Failed to parse LLM response" warnings!** 🎉

## 🔍 Verification Checklist

Before deploying any changes:

- [ ] All code compiles without errors
- [ ] Tests pass: `cargo test`
- [ ] Documentation is updated
- [ ] API keys are not hardcoded
- [ ] Environment variables are documented
- [ ] Error handling is comprehensive
- [ ] Logging provides useful debug info
- [ ] Cost tracking is accurate

## 📖 Related Documentation

### Core Documentation
- [Project README](../../../README.md) - Project overview
- [xAI API Notes](../audit/notes_xai.md) - Complete xAI API documentation
- [LLM Implementation](../../src/audit/src/llm.rs) - Source code

### External Resources
- [xAI API Docs](https://docs.x.ai)
- [xAI Console](https://console.x.ai)
- [xAI Discord](https://discord.gg/x-ai) - #help channel

## 🚀 Getting Started

### For Developers

1. Read [xai_integration_fix.md](xai_integration_fix.md) for technical details
2. Review source code changes in `src/audit/src/llm.rs`
3. Test locally before pushing changes
4. Monitor CI/CD for integration issues

### For Operators

1. Use [xai_quick_reference.md](xai_quick_reference.md) for daily operations
2. Set up API keys in environment
3. Configure billing alerts at console.x.ai
4. Monitor usage and costs

### For Auditors

1. Check [xAI API Notes](../audit/notes_xai.md) for pricing and limits
2. Review audit outputs in `docs/audit/`
3. Verify compliance with trading regulations
4. Track cost per analysis

## 💡 Best Practices

### API Integration
- Always use OpenAI-compatible endpoints for xAI
- Parse responses using `/choices/0/message/content` path
- Log token usage for cost tracking
- Handle errors gracefully with retries

### Security
- Store API keys in environment variables only
- Rotate keys every 90 days
- Use separate keys for dev/staging/prod
- Monitor for unauthorized usage

### Cost Optimization
- Leverage cached prompts (75% discount)
- Set appropriate `max_tokens` limits
- Batch related analyses together
- Monitor usage at console.x.ai

### Debugging
```bash
# Enable debug logging
export RUST_LOG=audit::llm=debug
export AUDIT_DEBUG_DIR="./debug"

# Run with verbose output
cargo run --release --bin audit-cli -- llm-audit \
    path/to/code --provider xai 2>&1 | tee audit.log
```

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution | Reference |
|-------|----------|-----------|
| Failed to parse response | Fixed in v1.0.0 with JSON mode | [xai_json_structured_output.md](xai_json_structured_output.md) |
| 401 Unauthorized | Check `$XAI_API_KEY` | [Quick Ref](xai_quick_reference.md#troubleshooting) |
| 429 Rate Limit | Upgrade tier or slow down | [xAI Console](https://console.x.ai/team/default/usage) |
| High costs | Enable caching, reduce max_tokens | [Quick Ref](xai_quick_reference.md#optimize-costs) |
| JSON schema mismatch | Check system prompt schemas | [xai_json_structured_output.md](xai_json_structured_output.md#troubleshooting) |

### Getting Help

1. Check documentation in this directory
2. Review [xAI API Notes](../audit/notes_xai.md)
3. Search GitHub issues
4. Ask in xAI Discord #help channel
5. Email support@x.ai

## 📊 Metrics & Monitoring

### Track These Metrics

```bash
# Token usage per request
grep "XAI usage" audit.log

# Cost per analysis
grep "XAI cost" audit.log

# Cache hit rate
grep "cached_tokens" audit.log | awk '{sum+=$1; count++} END {print sum/count}'
```

### Set Alerts

At [xAI Console](https://console.x.ai):
- Alert at $10 daily spend
- Alert at $50 daily spend
- Alert at 80% of monthly quota
- Alert on error rate > 5%

## 🔄 CI/CD Integration

The LLM audit runs automatically on CI/CD:

```yaml
# .github/workflows/llm-audit.yml
- name: Run LLM Audit
  env:
    XAI_API_KEY: ${{ secrets.XAI_API_KEY }}
  run: |
    cargo run --release --bin audit-cli -- llm-audit \
      ../../src/janus \
      --mode full \
      --provider xai \
      --output llm-audit-results.json
```

## 📝 Contributing

When adding new implementation guides:

1. Create a new `.md` file in this directory
2. Follow the existing format and structure
3. Include code examples and verification steps
4. Update this README with a link
5. Add to the table of contents
6. Test all commands and code snippets

## 📅 Changelog

### 2026-01-08 - xAI Integration Fix & JSON Mode
- Fixed critical API endpoint issue
- Implemented OpenAI-compatible request/response format
- Added JSON mode with `response_format` field
- Updated all system prompts with explicit JSON schemas
- Implemented multi-level JSON extraction fallbacks
- Added comprehensive debugging and logging
- Enhanced cost tracking and reporting
- Documentation: 100% coverage

---

**Maintained by:** FKS Trading Platform Team  
**Last Updated:** 2026-01-08  
**Status:** Active Development
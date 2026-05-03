# FKS Promptfoo Evaluations

LLM prompt evaluation configs for the FKS trading system.

## Running Evals

```bash
# Start the promptfoo server
docker compose --profile tools up -d promptfoo

# View UI
open http://localhost:4000

# Run an eval from the CLI (point results at our self-hosted instance)
PROMPTFOO_REMOTE_API_BASE_URL=http://localhost:4000 \
  npx promptfoo eval --config infrastructure/promptfoo/evals/rc-system-prompts.yaml --share

# Or run via docker exec
docker exec fks_promptfoo promptfoo eval --config /home/promptfoo/evals/rc-system-prompts.yaml --share
```

## Eval Files

| File | What it tests |
|------|---------------|
| `evals/rc-system-prompts.yaml` | RUSTCODE LLM prompt quality (scaffold, code review, arch) |
| `evals/trading-analysis.yaml` | Ruby trading analysis prompt accuracy |
| `evals/rc-routing.yaml` | ModelRouter classification correctness |
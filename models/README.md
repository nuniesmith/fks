# Models

Trained PyTorch checkpoints for the Futures CNN trading system.

## File Layout

```
models/
├── cnn_btc.pt           # PerAssetCNN weights for BTC
├── cnn_btc.json         # BTC model metadata (accuracy, date, hyperparams)
├── cnn_eth.pt
├── cnn_eth.json
├── cnn_sol.pt
├── cnn_sol.json
├── cnn_doge.pt
├── cnn_doge.json
├── cnn_pepe.pt
├── cnn_pepe.json
├── cnn_master.pt        # MasterCNN weights (portfolio risk aggregator)
└── cnn_master.json      # MasterCNN metadata
```

## Naming Convention

| Pattern            | Model class    | Description                                      |
|--------------------|----------------|--------------------------------------------------|
| `cnn_{asset}.pt`   | `PerAssetCNN`  | Per-asset entry/exit signal classifier (3-class) |
| `cnn_{asset}.json` | —              | Sidecar metadata for the per-asset model         |
| `cnn_master.pt`    | `MasterCNN`    | Portfolio-level risk score aggregator            |
| `cnn_master.json`  | —              | Sidecar metadata for the master model            |

Valid `{asset}` keys: `btc`, `eth`, `sol`, `doge`, `pepe`, `avax`, `sui`, `wif`, `fart`

## JSON Sidecar Fields

Each `.json` file sits alongside its `.pt` and is written automatically by the
training script. Example:

```json
{
  "asset": "btc",
  "trained_at": "2025-01-15T03:42:11+00:00",
  "val_accuracy": 0.6213,
  "val_precision": 0.5891,
  "val_recall": 0.5734,
  "epochs": 60,
  "bars": 15000,
  "timeframe": "1m",
  "window": 60,
  "tp_pct": 0.004,
  "sl_pct": 0.0035,
  "n_features": 15,
  "n_classes": 3,
  "embedding_dim": 64,
  "param_count": 47235
}
```

## Loading a Model

```python
from src.ml.model import PerAssetCNN, MasterCNN

# Load per-asset model
model = PerAssetCNN.load("models/cnn_btc.pt")
meta  = PerAssetCNN.load_meta("models/cnn_btc.pt")

# Load master model
master = MasterCNN.load("models/cnn_master.pt")
```

## Training & Promotion

`scripts/train.sh` runs the complete pipeline end-to-end:

```sh
./scripts/train.sh                           # full pipeline — all 10 assets + master + promote
./scripts/train.sh --assets btc eth sol      # specific assets only
./scripts/train.sh --epochs 100 --bars 20000 # custom hyperparams
./scripts/train.sh --dry-run                 # data + labels only, no training or promotion
./scripts/train.sh --no-promote              # train but skip git commit
./scripts/train.sh --min-accuracy 0.55       # raise the promotion threshold
```

**What the pipeline does:**

| Step | Description |
|------|-------------|
| **Tier 1** | Trains one `PerAssetCNN` per coin independently |
| **Tier 2** | Trains `MasterCNN` portfolio risk aggregator on all assets |
| **Promote** | Force-adds every checkpoint ≥ threshold to git and commits |

## Git Workflow

Model files (`*.pt`, `*.json`) are excluded from automatic git tracking by
`models/.gitignore`. The train script promotes champions automatically via
`git add -f`. You can also do it manually:

```sh
# Force-add specific files (bypasses .gitignore)
git add -f models/cnn_btc.pt models/cnn_btc.json
git commit -m "model: promote cnn_btc — val_acc=0.621 (60 epochs, 15 000 bars)"
```

### Removing a model from git

```sh
git rm models/cnn_btc.pt models/cnn_btc.json
git commit -m "model: retire cnn_btc (replaced by retrained version)"
```

### No model = CNN disabled

If no `.pt` file is found for an asset at startup, `CNNInference` silently
returns `enabled=False` and that asset falls back to the rule-based EMA +
order-book signal pipeline unchanged. The `MasterCNN` risk gate is similarly
disabled if `cnn_master.pt` is absent. You can deploy the bot at any time
before training is complete.

## Size Reference

These are small 1-D CNNs — each checkpoint is well under 1 MB, making
plain git tracking practical without Git LFS.

| Model         | Parameters | Approx. size |
|---------------|-----------|--------------|
| `PerAssetCNN` | ~47 K     | ~185 KB      |
| `MasterCNN`   | ~110 K    | ~430 KB      |
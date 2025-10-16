"""
Hybrid HMM + Transformer model for regime-aware time series forecasting.

Components:
- GaussianHMM (hmmlearn) to infer hidden market regimes from returns/volatility.
- PyTorch Transformer encoder to forecast future returns/prices using
  original features concatenated with HMM regime probabilities.

This module provides a minimal, self-contained implementation suitable for
initial experiments and service integration. It focuses on clarity and
portability rather than SOTA performance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Any

import numpy as np
import torch
from torch import nn

try:
    from hmmlearn.hmm import GaussianHMM as _GaussianHMM  # type: ignore
    HAS_HMMLEARN = True
except Exception:  # pragma: no cover - optional dependency
    _GaussianHMM = None
    HAS_HMMLEARN = False


def _device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 1000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(1))  # [max_len, 1, d_model]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [seq_len, batch, d_model]
        seq_len = x.size(0)
        return x + self.pe[:seq_len]


@dataclass
class HMMConfig:
    n_states: int = 3
    covariance_type: str = "full"
    n_iter: int = 200
    random_state: int = 42


@dataclass
class TransformerConfig:
    d_model: int = 64
    nhead: int = 4
    num_layers: int = 2
    dim_feedforward: int = 128
    dropout: float = 0.1
    seq_length: int = 64
    pred_horizon: int = 1


class HMMTransformer(nn.Module):
    """
    End-to-end module wrapping a fitted HMM and a Transformer for forecasting.

    Inputs during forward(): raw feature sequences X of shape [batch, seq, feat].
    The model internally computes HMM regime posteriors for each time step and
    concatenates them to X before passing through the Transformer encoder.
    """

    def __init__(
        self,
        in_features: int,
        hmm_cfg: Optional[HMMConfig] = None,
        tf_cfg: Optional[TransformerConfig] = None,
        out_features: int = 1,
    ) -> None:
        super().__init__()
        self.hmm_cfg = hmm_cfg or HMMConfig()
        self.tf_cfg = tf_cfg or TransformerConfig()

        if not HAS_HMMLEARN:
            raise ImportError("hmmlearn is required for HMMTransformer")

        # HMM runs on CPU (hmmlearn), returns numpy arrays
        self.hmm = None  # type: Optional[Any]

        # Input projection: original feats + regime probs
        self.regime_dim = self.hmm_cfg.n_states
        self.input_dim = in_features + self.regime_dim
        self.input_proj = nn.Linear(self.input_dim, self.tf_cfg.d_model)
        self.pos = PositionalEncoding(self.tf_cfg.d_model, max_len=4096)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.tf_cfg.d_model,
            nhead=self.tf_cfg.nhead,
            dim_feedforward=self.tf_cfg.dim_feedforward,
            dropout=self.tf_cfg.dropout,
            batch_first=False,  # we use [S, B, E]
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, self.tf_cfg.num_layers)
        self.head = nn.Sequential(
            nn.Linear(self.tf_cfg.d_model, self.tf_cfg.d_model),
            nn.ReLU(),
            nn.Linear(self.tf_cfg.d_model, out_features),
        )

        self.to(_device())

    # ---------------------------- HMM utils ----------------------------
    def fit_hmm(self, obs: np.ndarray) -> None:
        """
        Fit HMM on observation series (e.g., returns, volatility).
        obs: shape [N, D] where D could be 1-3 (returns, vol, etc).
        """
        if obs.ndim == 1:
            obs = obs.reshape(-1, 1)
        if _GaussianHMM is None:
            raise ImportError("hmmlearn not available")
        hmm = _GaussianHMM(
            n_components=self.hmm_cfg.n_states,
            covariance_type=self.hmm_cfg.covariance_type,
            n_iter=self.hmm_cfg.n_iter,
            random_state=self.hmm_cfg.random_state,
        )  # type: ignore[call-arg]
        hmm.fit(obs)
        self.hmm = hmm

    def regime_posteriors(self, obs: np.ndarray) -> np.ndarray:
        """Return P(state|obs) for each time step. Shape [N, n_states]."""
        if self.hmm is None:
            raise RuntimeError("HMM must be fitted before calling regime_posteriors")
        if obs.ndim == 1:
            obs = obs.reshape(-1, 1)
        logprob, post = self.hmm.score_samples(obs)
        return post  # [N, n_states]

    # --------------------------- Torch forward --------------------------
    def forward(self, x: torch.Tensor, regime_probs: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        x: [B, S, F] raw features
        regime_probs: optional [B, S, K] if already computed externally
        returns: [B, S, out_features] predictions aligned to each time step
        """
        B, S, F = x.shape
        if regime_probs is None:
            raise ValueError("regime_probs must be provided to forward() in service mode")
        if regime_probs.shape[:2] != (B, S):
            raise ValueError("regime_probs must match batch and seq dims of x")

        x_cat = torch.cat([x, regime_probs], dim=-1)  # [B, S, F+K]
        x_proj = self.input_proj(x_cat)  # [B, S, d_model]
        x_proj = x_proj.transpose(0, 1)  # [S, B, d_model]
        x_pe = self.pos(x_proj)
        enc = self.encoder(x_pe)  # [S, B, d_model]
        out = self.head(enc)  # [S, B, out]
        return out.transpose(0, 1)  # [B, S, out]

    # ----------------------------- Inference ----------------------------
    @torch.no_grad()
    def predict_sequence(
        self,
        x_seq: np.ndarray,
        obs_for_hmm: np.ndarray,
    ) -> np.ndarray:
        """
        Predict for a single sequence.
        x_seq: [S, F]
        obs_for_hmm: [S, D] observations for HMM posterior computation
        returns: [S, out]
        """
        self.eval()
        if x_seq.ndim == 2:
            x_seq = x_seq[None, ...]  # [1, S, F]
        if obs_for_hmm.ndim == 1:
            obs_for_hmm = obs_for_hmm.reshape(-1, 1)

        # HMM on CPU -> torch tensor on correct device
        post = self.regime_posteriors(obs_for_hmm)  # [S, K]
        x_t = torch.from_numpy(x_seq).float().to(_device())
        post_t = torch.from_numpy(post).float().unsqueeze(0).to(_device())  # [1,S,K]

        y = self.forward(x_t, post_t).cpu().numpy()[0]
        return y


def train_step(
    model: HMMTransformer,
    batch_x: torch.Tensor,
    batch_obs: torch.Tensor,
    batch_y: torch.Tensor,
    optimizer: torch.optim.Optimizer,
    loss_fn: nn.Module,
) -> Tuple[float, float]:
    """Single training step. Returns (loss, mae)."""
    model.train()
    optimizer.zero_grad()
    # Compute regime posteriors for each item in batch on CPU
    B, S, Dobs = batch_obs.shape
    regime_list = []
    for b in range(B):
        post = model.regime_posteriors(batch_obs[b].cpu().numpy())  # [S, K]
        regime_list.append(torch.from_numpy(post).float())
    regime_probs = torch.stack(regime_list, dim=0).to(_device())  # [B, S, K]

    preds = model(batch_x.to(_device()), regime_probs)
    loss = loss_fn(preds, batch_y.to(_device()))
    loss.backward()
    optimizer.step()
    with torch.no_grad():
        mae = torch.mean(torch.abs(preds - batch_y.to(_device()))).item()
    return float(loss.item()), float(mae)

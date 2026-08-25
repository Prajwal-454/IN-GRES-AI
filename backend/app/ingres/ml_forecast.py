"""Deep-learning groundwater forecasting (Phase 21, optional dependency).

LSTM and Transformer forecaster implementations in PyTorch. PyTorch is an
*optional* dependency: install ``requirements-ml.txt`` to enable them.
Every function here degrades gracefully when ``torch`` is missing:

- :func:`ml_available` returns ``False`` and
- :func:`fit_predict` raises :class:`RuntimeError`, which ``predict.forecast``
  catches and turns into a graceful statistical-model fallback.

Transfer learning follows the basin-wide recipe from the modelling roadmap:
one model is pre-trained on a *pool* series (e.g. the whole state) and then
fine-tuned on the target scope (a district/village) with far fewer epochs.

Everything produced here is a statistical estimate of the current dataset and
is clearly labelled as such — never an official IN-GRES/CGWB forecast.
"""

from __future__ import annotations

import hashlib
import io
import math
import pickle
import random
from functools import lru_cache

_TORCH = None
try:  # pragma: no cover - exercised only when torch is installed
    import torch
    import torch.nn as nn

    _TORCH = (torch, nn)
except Exception:  # pragma: no cover
    _TORCH = None

_DEFAULT_WINDOW = 8
_DEFAULT_HIDDEN = 24
_DEFAULT_D_MODEL = 16
_PRETRAIN_EPOCHS = 200
_FINETUNE_EPOCHS = 60


def ml_available() -> bool:
    """True when PyTorch is importable."""
    return _TORCH is not None


def ml_methods() -> list[str]:
    """Deep-learning methods available to the forecast API."""
    if not ml_available():
        return []
    return ["lstm", "transformer", "ml"]


def _torch() -> tuple:
    if _TORCH is None:
        raise RuntimeError(
            "torch is not installed; pip install -r requirements-ml.txt to "
            "enable deep-learning groundwater forecasting."
        )
    return _TORCH


def _zscore(values: list[float]) -> tuple[list[float], float, float]:
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(var) or 1.0
    return [(v - mean) / std for v in values], mean, std


def _build_windows(values: list[float], window: int) -> tuple[list[list[float]], list[float]]:
    x, y = [], []
    for i in range(window, len(values)):
        x.append(values[i - window : i])
        y.append(values[i])
    return x, y


def _make_model(model_type: str, window: int):
    torch, nn = _torch()

    class LSTMForecaster(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(1, _DEFAULT_HIDDEN, batch_first=True)
            self.head = nn.Linear(_DEFAULT_HIDDEN, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :])

    class TransformerForecaster(nn.Module):
        def __init__(self):
            super().__init__()
            self.in_proj = nn.Linear(1, _DEFAULT_D_MODEL)
            self.pos = nn.Parameter(torch.randn(window, _DEFAULT_D_MODEL) * 0.02)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=_DEFAULT_D_MODEL,
                nhead=2,
                dim_feedforward=_DEFAULT_D_MODEL * 2,
                batch_first=True,
                activation="gelu",
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=2)
            self.head = nn.Linear(_DEFAULT_D_MODEL, 1)

        def forward(self, x):
            x = self.in_proj(x) + self.pos.unsqueeze(0)
            x = self.encoder(x)
            return self.head(x[:, -1, :])

    if model_type == "transformer":
        return TransformerForecaster()
    return LSTMForecaster()


def _train_model(model, x: list[list[float]], y: list[float], epochs: int, seed: int):
    torch, nn = _torch()
    if not x:
        return
    torch.manual_seed(seed)
    xt = torch.tensor(x, dtype=torch.float32).unsqueeze(-1)
    yt = torch.tensor(y, dtype=torch.float32).unsqueeze(-1)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(model(xt), yt)
        loss.backward()
        opt.step()


def _forecast_path(model, values_z: list[float], window: int, horizon: int):
    torch, _nn = _torch()
    model.eval()
    with torch.no_grad():
        seq = list(values_z[-(window):])
        out: list[float] = []
        for _ in range(horizon):
            x = torch.tensor([seq[-window:]], dtype=torch.float32).unsqueeze(-1)
            pred = float(model(x).item())
            out.append(pred)
            seq.append(pred)
    return out


def _pool_key(model_type: str, pool: tuple[float, ...], epochs: int, seed: int) -> str:
    raw = repr((model_type, pool, epochs, seed))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@lru_cache(maxsize=32)
def _pretrained_state(model_type: str, pool: tuple[float, ...], epochs: int, seed: int) -> bytes:
    """Train a model on the pooled series and return its state dict (bytes).

    Cached in-process keyed by (model type, pool, epochs, seed) so repeat
    forecasts for the same basin/state re-use the basin-wide pre-trained model.
    """
    torch, _nn = _torch()
    z, _mean, _std = _zscore(list(pool))
    window = min(_DEFAULT_WINDOW, len(z) - 1)
    x, y = _build_windows(z, window)
    model = _make_model(model_type, window)
    _train_model(model, x, y, epochs, seed)
    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return buf.getvalue()


def _residual_std(values_z: list[float], model, window: int) -> float:
    """In-sample residual scatter (normalised units)."""
    torch, _nn = _torch()
    if len(values_z) <= window:
        return 1.0
    resid = []
    with torch.no_grad():
        for i in range(window, len(values_z)):
            x = torch.tensor([values_z[i - window : i]], dtype=torch.float32).unsqueeze(-1)
            pred = float(model(x).item())
            resid.append(values_z[i] - pred)
    if len(resid) < 2:
        return 1.0
    mean = sum(resid) / len(resid)
    var = sum((r - mean) ** 2 for r in resid) / (len(resid) - 1)
    return math.sqrt(var) or 1.0


def fit_predict(
    values: list[float],
    horizon: int,
    model_type: str = "lstm",
    epochs: int = 150,
    transfer: list[float] | None = None,
    metric_name: str = "stage",
    scope: str = "",
    seed: int = 42,
    band: str = "normal",
    info: dict | None = None,
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    """Fit an LSTM/Transformer and produce an ``horizon``-step forecast.

    ``transfer`` is an optional *pool* series (e.g. the containing state/basin)
    used to pre-train the model basin-wide before fine-tuning on ``values``.

    Returns ``(slope, r2, [(pred, upper, lower), ...])`` where the confidence
    band is either an analytic residual band (``band="normal"``) or a small
    residual block-bootstrap fan (``band="bootstrap"``). ``info`` is filled
    with training metadata for the API / UI.
    """
    if not ml_available():
        raise RuntimeError("torch is not installed")
    if model_type not in ("lstm", "transformer"):
        model_type = "lstm"
    if len(values) < 4:
        raise ValueError("At least four observations are required for deep-learning forecasting.")
    horizon = max(1, min(int(horizon), 10))
    epochs = max(20, min(int(epochs), 2000))

    z, mean, std = _zscore(values)
    window = min(_DEFAULT_WINDOW, len(z) - 1)

    model = _make_model(model_type, window)
    pretrained = False
    if transfer and len(transfer) >= 4:
        key = _pool_key(model_type, tuple(round(v, 4) for v in transfer), _PRETRAIN_EPOCHS, seed)
        state_bytes = _pretrained_state(model_type, tuple(round(v, 4) for v in transfer), _PRETRAIN_EPOCHS, seed)
        torch, _nn = _torch()
        model.load_state_dict(torch.load(io.BytesIO(state_bytes)))
        pretrained = True

    x, y = _build_windows(z, window)
    fine_epochs = _FINETUNE_EPOCHS if pretrained else max(epochs, _FINETUNE_EPOCHS)
    _train_model(model, x, y, fine_epochs, seed)

    path_z = _forecast_path(model, z, window, horizon)
    resid_std = _residual_std(z, model, window)

    if band == "bootstrap":
        med_z, low_z, high_z = _bootstrap_fan_z(z, model, window, horizon, seed)
        preds = [
            (med_z[k] * std + mean, high_z[k] * std + mean, low_z[k] * std + mean)
            for k in range(horizon)
        ]
    else:
        preds = []
        for k in range(1, horizon + 1):
            val = path_z[k - 1] * std + mean
            se = resid_std * std * math.sqrt(k)
            preds.append((val, val + 1.96 * se, val - 1.96 * se))

    slope = (values[-1] - values[0]) / max(len(values) - 1, 1)
    if info is not None:
        info.update(
            {
                "model": model_type,
                "transfer": pretrained,
                "pretrained_scope": "pool" if pretrained else None,
                "epochs": fine_epochs,
                "window": window,
                "residual_std": round(resid_std * std, 3),
                "device": "cpu",
            }
        )
    return slope, None, preds


def _bootstrap_fan_z(
    model,
    values_z: list[float],
    window: int,
    horizon: int,
    seed: int,
    n_iter: int = 80,
) -> tuple[list[float], list[float], list[float]]:
    """Block-bootstrap residual fan around the ML path (normalised units)."""
    torch, _nn = _torch()
    n = len(values_z)
    resid = []
    with torch.no_grad():
        for i in range(window, n):
            x = torch.tensor([values_z[i - window : i]], dtype=torch.float32).unsqueeze(-1)
            resid.append(values_z[i] - float(model(x).item()))
    rng = random.Random(seed)
    block = max(1, min(n, 3))
    base = _forecast_path(model, values_z, window, horizon)
    paths: list[list[float]] = []
    for _ in range(n_iter):
        path = list(base)
        offset = 0.0
        for k in range(horizon):
            offset += resid[rng.randrange(0, len(resid))] if resid else 0.0
            path[k] += offset
        paths.append(path)
    med, low, high = [], [], []
    for k in range(horizon):
        col = sorted(p[k] for p in paths)
        idx = len(col) - 1
        med.append(col[int(0.5 * idx)])
        low.append(col[int(0.05 * idx)])
        high.append(col[int(0.95 * idx)])
    return med, low, high

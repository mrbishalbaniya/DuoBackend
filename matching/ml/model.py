"""Duo's own match model: L2-regularised logistic regression in numpy.

Small, fast and explainable on purpose: with a few hundred labelled swipes a
linear model generalises better than anything deeper, trains in milliseconds,
and every prediction splits into per-feature contributions that the Match
insights screen turns into plain-language reasons.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from matching.ml.features import ALL_NAMES

MODEL_NAME = "duo-match"


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def auc(y: np.ndarray, scores: np.ndarray) -> float | None:
    """ROC AUC via the rank-sum formula; None when only one class is present."""
    y = np.asarray(y, dtype=float)
    pos, neg = y == 1, y == 0
    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    s = np.asarray(scores)
    for val in np.unique(s):
        idx = s == val
        if idx.sum() > 1:
            ranks[idx] = ranks[idx].mean()
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


@dataclass
class MatchModel:
    weights: list[float]
    bias: float
    mean: list[float]
    std: list[float]
    feature_names: list[str] = field(default_factory=lambda: list(ALL_NAMES))
    # quantiles of training predictions -> turns a probability into a 1-99 score
    quantiles: list[float] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    starter_stats: dict = field(default_factory=dict)
    version: int = 1

    # ---------------------------------------------------------------- training
    @classmethod
    def fit(
        cls,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: np.ndarray | None = None,
        *,
        l2: float = 1.0,
        lr: float = 0.1,
        epochs: int = 3000,
    ) -> "MatchModel":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        n, d = X.shape
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std[std < 1e-6] = 1.0
        Z = (X - mean) / std

        # balance classes so the ~80% "like" base rate doesn't swamp the signal
        pos = max(y.sum(), 1.0)
        neg = max(n - y.sum(), 1.0)
        cw = np.where(y == 1, n / (2 * pos), n / (2 * neg))
        w_s = cw * (sample_weight if sample_weight is not None else 1.0)
        w_s = w_s / w_s.mean()

        w = np.zeros(d)
        b = float(np.log(pos / neg))
        for _ in range(epochs):
            p = _sigmoid(Z @ w + b)
            err = (p - y) * w_s
            grad_w = Z.T @ err / n + l2 * w / n
            grad_b = err.mean()
            w -= lr * grad_w
            b -= lr * grad_b

        model = cls(weights=w.tolist(), bias=b, mean=mean.tolist(), std=std.tolist())
        preds = model.predict_proba_matrix(X)
        model.quantiles = np.quantile(preds, np.linspace(0, 1, 101)).tolist()
        return model

    # ---------------------------------------------------------------- inference
    def _z(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, dtype=float) - np.asarray(self.mean)) / np.asarray(self.std)

    def predict_proba_matrix(self, X: np.ndarray) -> np.ndarray:
        return _sigmoid(self._z(X) @ np.asarray(self.weights) + self.bias)

    def predict_proba(self, x: list[float]) -> float:
        return float(self.predict_proba_matrix(np.asarray([x]))[0])

    def score_100(self, prob: float) -> int:
        """Percentile of this prediction among training pairs, as 1..99."""
        if not self.quantiles:
            return int(round(prob * 100))
        pct = float(np.searchsorted(np.asarray(self.quantiles), prob, side="right")) - 1
        return int(max(1, min(99, round(pct))))

    def contributions(self, x: list[float]) -> dict[str, float]:
        """Per-feature push on the log-odds relative to an average pair."""
        z = self._z(np.asarray([x]))[0]
        return {name: float(wi * zi) for name, wi, zi in zip(self.feature_names, self.weights, z)}

    # ---------------------------------------------------------------- persistence
    def to_payload(self) -> dict:
        return {
            "name": MODEL_NAME,
            "version": self.version,
            "weights": self.weights,
            "bias": self.bias,
            "mean": self.mean,
            "std": self.std,
            "feature_names": self.feature_names,
            "quantiles": self.quantiles,
            "metrics": self.metrics,
            "starter_stats": self.starter_stats,
        }

    @classmethod
    def from_payload(cls, data: dict) -> "MatchModel | None":
        if not data or data.get("feature_names") != list(ALL_NAMES):
            return None  # features changed since training: retrain
        return cls(
            weights=data["weights"],
            bias=data["bias"],
            mean=data["mean"],
            std=data["std"],
            feature_names=data["feature_names"],
            quantiles=data.get("quantiles", []),
            metrics=data.get("metrics", {}),
            starter_stats=data.get("starter_stats", {}),
            version=data.get("version", 1),
        )


def cross_validate(X: np.ndarray, y: np.ndarray, sw: np.ndarray, *, folds: int = 5, seed: int = 7, **kw) -> dict:
    """Stratified k-fold AUC / accuracy for the model."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    fold_of = np.empty(len(y), dtype=int)
    for cls_val in (0, 1):
        idx = np.where(y == cls_val)[0]
        rng.shuffle(idx)
        fold_of[idx] = np.arange(len(idx)) % folds
    probs = np.zeros(len(y))
    for f in range(folds):
        tr, te = fold_of != f, fold_of == f
        if len(np.unique(y[tr])) < 2 or te.sum() == 0:
            continue
        m = MatchModel.fit(X[tr], y[tr], sw[tr], **kw)
        probs[te] = m.predict_proba_matrix(X[te])
    acc = float(((probs >= 0.5) == (y == 1)).mean())
    return {"cv_auc": auc(y, probs), "cv_accuracy": round(acc, 3)}

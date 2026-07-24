"""SHAP explainability for tree-based regression models."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from config.logging_config import get_logger
from config.settings import TREE_MODEL_NAMES

logger = get_logger(__name__)


def compute_shap_values(
    model: Any,
    model_name: str,
    X: np.ndarray,
    feature_names: Optional[list[str]] = None,
) -> Optional[pd.DataFrame]:
    """
    Compute mean absolute SHAP values for a fitted tree-based model.

    Args:
        model: Fitted sklearn-compatible estimator.
        model_name: Display name; SHAP skipped for non-tree models.
        X: Feature matrix used for explanation.
        feature_names: Column labels for features.

    Returns:
        DataFrame with columns [feature, mean_abs_shap] or None if unavailable.
    """
    if model_name not in TREE_MODEL_NAMES:
        return None

    try:
        import shap
    except ImportError:
        logger.warning("SHAP not installed — skipping explainability for %s", model_name)
        return None

    feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        mean_abs = np.abs(shap_values).mean(axis=0)
        return pd.DataFrame({"feature": feature_names, "mean_abs_shap": mean_abs}).sort_values(
            "mean_abs_shap", ascending=False
        )
    except Exception as exc:
        logger.warning("SHAP failed for %s: %s", model_name, exc)
        try:
            explainer = shap.Explainer(model, X)
            sv = explainer(X)
            mean_abs = np.abs(sv.values).mean(axis=0)
            return pd.DataFrame({"feature": feature_names, "mean_abs_shap": mean_abs}).sort_values(
                "mean_abs_shap", ascending=False
            )
        except Exception as exc2:
            logger.warning("SHAP fallback failed for %s: %s", model_name, exc2)
            return None

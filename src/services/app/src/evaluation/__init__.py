"""
Evaluation Framework for Trading Models

Phase 7: Advanced model evaluation with confusion matrices, statistical testing,
and performance validation.
"""

from .confusion_matrix import ModelEvaluator
from .statistical_tests import apply_bonferroni, apply_benjamini_hochberg

__all__ = [
    "ModelEvaluator",
    "apply_bonferroni",
    "apply_benjamini_hochberg",
]

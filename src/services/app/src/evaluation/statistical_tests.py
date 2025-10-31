"""
Statistical Testing and P-value Corrections

Implements Bonferroni and Benjamini-Hochberg corrections for multiple hypothesis testing.
"""

from typing import List, Tuple
import numpy as np


def apply_bonferroni(p_values: List[float], alpha: float = 0.05) -> Tuple[List[bool], List[float]]:
    """
    Apply Bonferroni correction for multiple hypothesis testing.
    
    Conservative correction that controls family-wise error rate (FWER).
    Adjusted significance level: α_adj = α / n_tests
    
    Args:
        p_values: List of p-values from multiple tests
        alpha: Significance level (default: 0.05)
    
    Returns:
        Tuple of (significant_flags, adjusted_p_values)
        - significant_flags: Boolean list indicating which tests are significant
        - adjusted_p_values: Bonferroni-corrected p-values
    
    Example:
        >>> p_values = [0.01, 0.04, 0.03, 0.50]
        >>> significant, adjusted = apply_bonferroni(p_values)
        >>> print(adjusted)  # [0.04, 0.16, 0.12, 2.0]
    """
    n_tests = len(p_values)
    
    # Bonferroni correction: multiply each p-value by number of tests
    adjusted_p_values = [min(p * n_tests, 1.0) for p in p_values]
    
    # Determine which tests are still significant
    significant = [p < alpha for p in adjusted_p_values]
    
    return significant, adjusted_p_values


def apply_benjamini_hochberg(
    p_values: List[float],
    alpha: float = 0.05,
) -> Tuple[List[bool], List[float]]:
    """
    Apply Benjamini-Hochberg procedure for controlling false discovery rate (FDR).
    
    Less conservative than Bonferroni, controls the expected proportion of false
    discoveries among rejected hypotheses.
    
    Args:
        p_values: List of p-values from multiple tests
        alpha: Significance level (default: 0.05)
    
    Returns:
        Tuple of (significant_flags, adjusted_p_values)
        - significant_flags: Boolean list indicating which tests are significant
        - adjusted_p_values: BH-corrected p-values (q-values)
    
    Example:
        >>> p_values = [0.01, 0.04, 0.03, 0.50]
        >>> significant, adjusted = apply_benjamini_hochberg(p_values)
        >>> print(adjusted)  # [0.04, 0.08, 0.06, 0.50]
    """
    n_tests = len(p_values)
    
    # Create array with original indices
    p_array = np.array(p_values)
    indices = np.arange(n_tests)
    
    # Sort p-values and keep track of original order
    sorted_indices = np.argsort(p_array)
    sorted_p_values = p_array[sorted_indices]
    
    # Calculate adjusted p-values (q-values)
    # q_i = min(p_i * n / i, q_{i+1}) for i = n, n-1, ..., 1
    adjusted_p_values = np.zeros(n_tests)
    
    # Start from the largest p-value
    adjusted_p_values[sorted_indices[-1]] = sorted_p_values[-1]
    
    # Work backwards
    for i in range(n_tests - 2, -1, -1):
        rank = i + 1  # Rank starts from 1
        adjusted = min(
            sorted_p_values[i] * n_tests / rank,
            adjusted_p_values[sorted_indices[i + 1]]
        )
        adjusted_p_values[sorted_indices[i]] = min(adjusted, 1.0)
    
    # Determine significance
    # BH procedure: find largest i where p_(i) <= i * alpha / n
    significant = np.zeros(n_tests, dtype=bool)
    
    for i in range(n_tests - 1, -1, -1):
        rank = i + 1
        if sorted_p_values[i] <= (rank * alpha / n_tests):
            # Reject this and all smaller p-values
            significant[sorted_indices[:rank]] = True
            break
    
    return significant.tolist(), adjusted_p_values.tolist()


def compare_corrections(
    p_values: List[float],
    alpha: float = 0.05,
) -> dict:
    """
    Compare Bonferroni and Benjamini-Hochberg corrections side-by-side.
    
    Args:
        p_values: List of p-values from multiple tests
        alpha: Significance level
    
    Returns:
        Dictionary with comparison results
    """
    bonf_sig, bonf_adj = apply_bonferroni(p_values, alpha)
    bh_sig, bh_adj = apply_benjamini_hochberg(p_values, alpha)
    
    results = {
        "original_p_values": p_values,
        "bonferroni": {
            "adjusted_p_values": bonf_adj,
            "significant": bonf_sig,
            "n_significant": sum(bonf_sig),
        },
        "benjamini_hochberg": {
            "adjusted_p_values": bh_adj,
            "significant": bh_sig,
            "n_significant": sum(bh_sig),
        },
        "alpha": alpha,
        "n_tests": len(p_values),
    }
    
    return results


if __name__ == "__main__":
    # Example usage
    print("Testing P-value Corrections...\n")
    
    # Example: Testing 4 different trading strategies
    p_values = [0.01, 0.04, 0.03, 0.50]
    print(f"Original p-values: {p_values}")
    print(f"Significance level (α): 0.05\n")
    
    # Bonferroni correction
    print("=== Bonferroni Correction ===")
    bonf_sig, bonf_adj = apply_bonferroni(p_values)
    for i, (orig, adj, sig) in enumerate(zip(p_values, bonf_adj, bonf_sig)):
        status = "✓ Significant" if sig else "✗ Not significant"
        print(f"Test {i+1}: p={orig:.4f} → adjusted={adj:.4f} {status}")
    
    print(f"\nSignificant tests: {sum(bonf_sig)}/{len(p_values)}")
    
    # Benjamini-Hochberg correction
    print("\n=== Benjamini-Hochberg Correction ===")
    bh_sig, bh_adj = apply_benjamini_hochberg(p_values)
    for i, (orig, adj, sig) in enumerate(zip(p_values, bh_adj, bh_sig)):
        status = "✓ Significant" if sig else "✗ Not significant"
        print(f"Test {i+1}: p={orig:.4f} → q={adj:.4f} {status}")
    
    print(f"\nSignificant tests: {sum(bh_sig)}/{len(p_values)}")
    
    # Comparison
    print("\n=== Comparison ===")
    print(f"Bonferroni: {sum(bonf_sig)} significant (more conservative)")
    print(f"Benjamini-Hochberg: {sum(bh_sig)} significant (less conservative)")
    print("\nBH controls false discovery rate (FDR)")
    print("Bonferroni controls family-wise error rate (FWER)")

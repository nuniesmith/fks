"""
Unit Tests for Statistical Testing and P-value Corrections
"""

import pytest
import numpy as np
from evaluation.statistical_tests import (
    apply_bonferroni,
    apply_benjamini_hochberg,
    compare_corrections,
)


class TestBonferroniCorrection:
    """Test suite for Bonferroni correction"""
    
    def test_basic_correction(self):
        """Test basic Bonferroni correction"""
        p_values = [0.01, 0.04, 0.03, 0.50]
        significant, adjusted = apply_bonferroni(p_values, alpha=0.05)
        
        # With 4 tests, adjusted = original * 4
        assert adjusted[0] == 0.04  # 0.01 * 4
        assert adjusted[1] == 0.16  # 0.04 * 4
        assert adjusted[2] == 0.12  # 0.03 * 4
        assert adjusted[3] == 1.0   # min(0.50 * 4, 1.0)
        
        # Only first test should be significant (0.04 < 0.05)
        assert significant[0] is True
        assert significant[1] is False
        assert significant[2] is False
        assert significant[3] is False
    
    def test_all_significant(self):
        """Test when all p-values are very small"""
        p_values = [0.001, 0.002, 0.003]
        significant, adjusted = apply_bonferroni(p_values, alpha=0.05)
        
        # All should remain significant
        assert all(significant)
        assert all(p < 0.05 for p in adjusted)
    
    def test_none_significant(self):
        """Test when no p-values are significant"""
        p_values = [0.1, 0.2, 0.3, 0.4]
        significant, adjusted = apply_bonferroni(p_values, alpha=0.05)
        
        # None should be significant
        assert not any(significant)
    
    def test_capping_at_one(self):
        """Test that adjusted p-values are capped at 1.0"""
        p_values = [0.5, 0.6, 0.7]
        significant, adjusted = apply_bonferroni(p_values)
        
        # All adjusted values should be 1.0
        assert all(p == 1.0 for p in adjusted)
    
    def test_single_test(self):
        """Test with single test (no correction needed)"""
        p_values = [0.03]
        significant, adjusted = apply_bonferroni(p_values, alpha=0.05)
        
        # Single test: adjusted = original
        assert adjusted[0] == 0.03
        assert significant[0] is True


class TestBenjaminiHochbergCorrection:
    """Test suite for Benjamini-Hochberg correction"""
    
    def test_basic_correction(self):
        """Test basic BH correction"""
        p_values = [0.01, 0.04, 0.03, 0.50]
        significant, adjusted = apply_benjamini_hochberg(p_values, alpha=0.05)
        
        # BH is less conservative than Bonferroni
        assert len(adjusted) == 4
        assert all(0 <= p <= 1 for p in adjusted)
        
        # Adjusted p-values should be in non-decreasing order when sorted
        sorted_adjusted = sorted(adjusted)
        assert sorted_adjusted == sorted(sorted_adjusted)
    
    def test_ordered_p_values(self):
        """Test with already sorted p-values"""
        p_values = [0.001, 0.01, 0.02, 0.05]
        significant, adjusted = apply_benjamini_hochberg(p_values, alpha=0.05)
        
        # More should be significant compared to Bonferroni
        n_sig_bh = sum(significant)
        _, bonf_sig = apply_bonferroni(p_values, alpha=0.05)
        n_sig_bonf = sum(bonf_sig)
        
        assert n_sig_bh >= n_sig_bonf
    
    def test_monotonicity(self):
        """Test that q-values are monotonic when sorted by p-values"""
        p_values = [0.05, 0.01, 0.03, 0.02, 0.04]
        significant, adjusted = apply_benjamini_hochberg(p_values)
        
        # Sort by original p-values
        sorted_indices = np.argsort(p_values)
        sorted_adjusted = [adjusted[i] for i in sorted_indices]
        
        # Q-values should be non-decreasing
        for i in range(len(sorted_adjusted) - 1):
            assert sorted_adjusted[i] <= sorted_adjusted[i + 1]
    
    def test_all_significant(self):
        """Test when all p-values are very small"""
        p_values = [0.001, 0.002, 0.003, 0.004]
        significant, adjusted = apply_benjamini_hochberg(p_values, alpha=0.05)
        
        # All should be significant
        assert all(significant)
    
    def test_none_significant(self):
        """Test when no p-values should be significant"""
        p_values = [0.9, 0.85, 0.95, 0.99]
        significant, adjusted = apply_benjamini_hochberg(p_values, alpha=0.05)
        
        # None should be significant
        assert not any(significant)


class TestCompareCorrections:
    """Test suite for comparing correction methods"""
    
    def test_comparison_output(self):
        """Test comparison returns expected structure"""
        p_values = [0.01, 0.04, 0.03, 0.50]
        results = compare_corrections(p_values, alpha=0.05)
        
        assert "original_p_values" in results
        assert "bonferroni" in results
        assert "benjamini_hochberg" in results
        assert "alpha" in results
        assert "n_tests" in results
        
        assert results["alpha"] == 0.05
        assert results["n_tests"] == 4
    
    def test_bh_less_conservative(self):
        """Test that BH is generally less conservative than Bonferroni"""
        # Use p-values where difference is clear
        p_values = [0.01, 0.02, 0.03, 0.04]
        results = compare_corrections(p_values, alpha=0.05)
        
        n_bonf = results["bonferroni"]["n_significant"]
        n_bh = results["benjamini_hochberg"]["n_significant"]
        
        # BH should find at least as many significant results
        assert n_bh >= n_bonf
    
    def test_equal_at_extremes(self):
        """Test that both methods agree at extremes"""
        # All very significant
        p_values = [0.0001, 0.0002, 0.0003]
        results = compare_corrections(p_values, alpha=0.05)
        
        assert results["bonferroni"]["n_significant"] == 3
        assert results["benjamini_hochberg"]["n_significant"] == 3
        
        # All very insignificant
        p_values = [0.9, 0.95, 0.99]
        results = compare_corrections(p_values, alpha=0.05)
        
        assert results["bonferroni"]["n_significant"] == 0
        assert results["benjamini_hochberg"]["n_significant"] == 0


class TestEdgeCases:
    """Test edge cases for statistical corrections"""
    
    def test_empty_list(self):
        """Test with empty p-value list"""
        p_values = []
        
        # Should not crash
        bonf_sig, bonf_adj = apply_bonferroni(p_values)
        bh_sig, bh_adj = apply_benjamini_hochberg(p_values)
        
        assert bonf_sig == []
        assert bonf_adj == []
        assert bh_sig == []
        assert bh_adj == []
    
    def test_single_value(self):
        """Test with single p-value"""
        p_values = [0.03]
        
        bonf_sig, bonf_adj = apply_bonferroni(p_values, alpha=0.05)
        bh_sig, bh_adj = apply_benjamini_hochberg(p_values, alpha=0.05)
        
        # Both should give same result for single test
        assert bonf_sig == bh_sig
        assert bonf_adj[0] == 0.03
        assert bh_adj[0] == 0.03
    
    def test_all_zeros(self):
        """Test with all p-values = 0 (impossible but edge case)"""
        p_values = [0.0, 0.0, 0.0]
        
        bonf_sig, bonf_adj = apply_bonferroni(p_values, alpha=0.05)
        
        # All should be significant
        assert all(bonf_sig)
        assert all(p == 0.0 for p in bonf_adj)
    
    def test_all_ones(self):
        """Test with all p-values = 1.0"""
        p_values = [1.0, 1.0, 1.0]
        
        bonf_sig, bonf_adj = apply_bonferroni(p_values, alpha=0.05)
        bh_sig, bh_adj = apply_benjamini_hochberg(p_values, alpha=0.05)
        
        # None should be significant
        assert not any(bonf_sig)
        assert not any(bh_sig)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

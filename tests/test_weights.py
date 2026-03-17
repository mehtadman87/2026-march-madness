"""Unit tests for prediction weight configuration and redistribution.

Requirements: 8.1, 8.4
"""

import pytest
from src.utils.weights import PREDICTION_WEIGHTS, redistribute_weights


class TestPredictionWeights:
    def test_weights_sum_to_one(self):
        """PREDICTION_WEIGHTS must sum to exactly 1.0 (Requirement 8.1)."""
        total = sum(PREDICTION_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_weights_has_exactly_eight_categories(self):
        """PREDICTION_WEIGHTS must define exactly 8 categories (Requirement 8.1)."""
        assert len(PREDICTION_WEIGHTS) == 8

    def test_expected_categories_present(self):
        """All 8 named categories from Requirement 8.1 must be present."""
        expected = {
            "efficiency_margin",
            "matchup_factors",
            "momentum_form",
            "seed_history",
            "location_advantage",
            "player_injury",
            "experience_pedigree",
            "qualitative",
        }
        assert set(PREDICTION_WEIGHTS.keys()) == expected


class TestRedistributeWeights:
    def test_all_categories_returns_same_proportions_summing_to_one(self):
        """Passing all categories should return weights that still sum to 1.0."""
        all_cats = list(PREDICTION_WEIGHTS.keys())
        result = redistribute_weights(all_cats)
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_subset_of_categories_sums_to_one(self):
        """Any subset of categories should redistribute to sum to 1.0."""
        subset = ["efficiency_margin", "matchup_factors", "momentum_form"]
        result = redistribute_weights(subset)
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_proportional_redistribution_when_qualitative_removed(self):
        """Removing 'qualitative' (0.05) should scale remaining weights proportionally.

        Original remaining total = 1.0 - 0.05 = 0.95.
        Each remaining weight should be original / 0.95.
        """
        remaining = [k for k in PREDICTION_WEIGHTS if k != "qualitative"]
        result = redistribute_weights(remaining)

        original_total = sum(PREDICTION_WEIGHTS[k] for k in remaining)  # 0.95
        for cat in remaining:
            expected = PREDICTION_WEIGHTS[cat] / original_total
            assert abs(result[cat] - expected) < 1e-9, (
                f"Category '{cat}': expected {expected}, got {result[cat]}"
            )

    def test_single_category_returns_weight_of_one(self):
        """A single available category should receive the full weight of 1.0."""
        result = redistribute_weights(["efficiency_margin"])
        assert result == {"efficiency_margin": 1.0}

    def test_empty_list_raises_or_returns_empty(self):
        """An empty category list should raise ZeroDivisionError or return {}."""
        try:
            result = redistribute_weights([])
            assert result == {}
        except ZeroDivisionError:
            pass  # also acceptable

    def test_result_contains_only_requested_categories(self):
        """Result keys must match the requested subset exactly."""
        subset = ["seed_history", "location_advantage", "player_injury"]
        result = redistribute_weights(subset)
        assert set(result.keys()) == set(subset)

    def test_all_redistributed_weights_are_positive(self):
        """Every redistributed weight must be strictly positive."""
        subset = ["efficiency_margin", "qualitative"]
        result = redistribute_weights(subset)
        for cat, w in result.items():
            assert w > 0, f"Weight for '{cat}' should be positive, got {w}"

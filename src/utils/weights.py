"""Prediction weighting configuration for the bracket predictor.

Defines the weighted framework used by the Prediction Agent to synthesize
all sub-agent outputs into a single matchup prediction.
"""

# Weights for each prediction category. Must sum to 1.0.
# Requirements: 8.1
PREDICTION_WEIGHTS: dict[str, float] = {
    "efficiency_margin": 0.25,
    "matchup_factors": 0.20,
    "momentum_form": 0.15,
    "seed_history": 0.10,
    "location_advantage": 0.10,
    "player_injury": 0.10,
    "experience_pedigree": 0.05,
    "qualitative": 0.05,
}


def redistribute_weights(available_categories: list[str]) -> dict[str, float]:
    """Proportionally redistribute weights across available categories.

    When data for one or more categories is missing, this function scales
    the weights of the available categories so they still sum to 1.0.

    Args:
        available_categories: List of category names that have data available.

    Returns:
        A dict mapping each available category to its redistributed weight.

    Requirements: 8.4
    """
    available = {k: v for k, v in PREDICTION_WEIGHTS.items() if k in available_categories}
    total = sum(available.values())
    return {k: v / total for k, v in available.items()}

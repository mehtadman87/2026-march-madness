"""Property-based tests for Prediction round-trip serialization.

**Validates: Requirements 16.4**

Tests that FOR ALL valid Prediction objects, serializing to JSON then deserializing
back SHALL produce an equivalent Prediction object (round-trip property).
"""

from hypothesis import given, settings, strategies as st

from src.models.enums import Region, RoundName
from src.models.team import Team
from src.models.prediction import Prediction


# --- Hypothesis Strategies ---

# Team name strategy: non-empty text strings
team_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Seed strategy: integers 1-16
seed_strategy = st.integers(min_value=1, max_value=16)

# Region strategy: sampled from Region enum
region_strategy = st.sampled_from(list(Region))

# Round name strategy: sampled from RoundName enum
round_name_strategy = st.sampled_from(list(RoundName))

# Confidence strategy: integers 50-99
confidence_strategy = st.integers(min_value=50, max_value=99)

# Key factor strategy: non-empty text strings
key_factor_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Key factors list strategy: list of 1-5 key factors
key_factors_strategy = st.lists(key_factor_strategy, min_size=1, max_size=5)

# Weight adjustment key strategy
weight_key_strategy = st.sampled_from([
    "efficiency_margin",
    "matchup_factors",
    "momentum_form",
    "seed_history",
    "location_advantage",
    "player_injury",
    "experience_pedigree",
    "qualitative",
])

# Weight adjustment value strategy: floats between 0 and 1
weight_value_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Weight adjustments strategy: optional dict of string to float
weight_adjustments_strategy = st.one_of(
    st.none(),
    st.dictionaries(weight_key_strategy, weight_value_strategy, min_size=1, max_size=8),
)


@st.composite
def team_strategy(draw: st.DrawFn) -> Team:
    """Generate a valid Team object."""
    name = draw(team_name_strategy)
    seed = draw(seed_strategy)
    region = draw(region_strategy)
    return Team(name=name, seed=seed, region=region)


@st.composite
def sentence_strategy(draw: st.DrawFn) -> str:
    """Generate a single sentence (text ending with a period)."""
    # Generate text without periods, then add one at the end
    text = draw(st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
        min_size=3,
        max_size=50,
    ).filter(lambda s: s.strip() and '.' not in s))
    return text.strip()


@st.composite
def rationale_strategy(draw: st.DrawFn) -> str:
    """Generate a valid rationale with at least 2 sentences.
    
    A valid rationale must have at least 2 sentences separated by periods.
    """
    # Generate 2-4 sentences
    num_sentences = draw(st.integers(min_value=2, max_value=4))
    sentences = []
    for _ in range(num_sentences):
        sentence = draw(sentence_strategy())
        sentences.append(sentence)
    
    # Join with periods and add final period
    return ". ".join(sentences) + "."


@st.composite
def prediction_strategy(draw: st.DrawFn) -> Prediction:
    """Generate a valid Prediction object."""
    team_a = draw(team_strategy())
    team_b = draw(team_strategy())
    
    # Winner must be one of the two team names
    winner = draw(st.sampled_from([team_a.name, team_b.name]))
    
    confidence = draw(confidence_strategy)
    rationale = draw(rationale_strategy())
    key_factors = draw(key_factors_strategy)
    round_name = draw(round_name_strategy)
    weight_adjustments = draw(weight_adjustments_strategy)
    
    # upset_alert will be auto-calculated in __post_init__
    return Prediction(
        team_a=team_a,
        team_b=team_b,
        winner=winner,
        confidence=confidence,
        rationale=rationale,
        key_factors=key_factors,
        upset_alert=False,  # Will be recalculated
        round_name=round_name,
        weight_adjustments=weight_adjustments,
    )


# --- Property Tests ---


class TestPredictionRoundTripSerialization:
    """Property tests for Prediction round-trip serialization.

    **Validates: Requirements 16.4**
    """

    @given(prediction=prediction_strategy())
    @settings(max_examples=100, deadline=None)
    def test_prediction_round_trip_consistency(self, prediction: Prediction) -> None:
        """Property 2: Prediction round-trip consistency.

        FOR ALL valid Prediction objects, serializing to JSON then deserializing
        back SHALL produce an equivalent Prediction object.

        **Validates: Requirements 16.4**
        """
        # Serialize to dict
        serialized = prediction.to_dict()

        # Deserialize back
        deserialized = Prediction.from_dict(serialized)

        # Assert equivalence for team_a
        assert deserialized.team_a.name == prediction.team_a.name
        assert deserialized.team_a.seed == prediction.team_a.seed
        assert deserialized.team_a.region == prediction.team_a.region

        # Assert equivalence for team_b
        assert deserialized.team_b.name == prediction.team_b.name
        assert deserialized.team_b.seed == prediction.team_b.seed
        assert deserialized.team_b.region == prediction.team_b.region

        # Assert equivalence for prediction fields
        assert deserialized.winner == prediction.winner
        assert deserialized.confidence == prediction.confidence
        assert deserialized.rationale == prediction.rationale
        assert deserialized.key_factors == prediction.key_factors
        assert deserialized.upset_alert == prediction.upset_alert
        assert deserialized.round_name == prediction.round_name
        assert deserialized.weight_adjustments == prediction.weight_adjustments

    @given(prediction=prediction_strategy())
    @settings(max_examples=50, deadline=None)
    def test_double_round_trip_consistency(self, prediction: Prediction) -> None:
        """Property: Double round-trip produces same result.

        Serializing and deserializing twice should produce the same result
        as doing it once.

        **Validates: Requirements 16.4**
        """
        # First round-trip
        first_serialized = prediction.to_dict()
        first_deserialized = Prediction.from_dict(first_serialized)

        # Second round-trip
        second_serialized = first_deserialized.to_dict()
        second_deserialized = Prediction.from_dict(second_serialized)

        # Both serialized forms should be identical
        assert first_serialized == second_serialized

        # Both deserialized forms should be equivalent
        assert second_deserialized.team_a.name == first_deserialized.team_a.name
        assert second_deserialized.team_a.seed == first_deserialized.team_a.seed
        assert second_deserialized.team_a.region == first_deserialized.team_a.region
        assert second_deserialized.team_b.name == first_deserialized.team_b.name
        assert second_deserialized.team_b.seed == first_deserialized.team_b.seed
        assert second_deserialized.team_b.region == first_deserialized.team_b.region
        assert second_deserialized.winner == first_deserialized.winner
        assert second_deserialized.confidence == first_deserialized.confidence
        assert second_deserialized.rationale == first_deserialized.rationale
        assert second_deserialized.key_factors == first_deserialized.key_factors
        assert second_deserialized.upset_alert == first_deserialized.upset_alert
        assert second_deserialized.round_name == first_deserialized.round_name
        assert second_deserialized.weight_adjustments == first_deserialized.weight_adjustments

    @given(prediction=prediction_strategy())
    @settings(max_examples=50, deadline=None)
    def test_upset_alert_preserved_after_round_trip(self, prediction: Prediction) -> None:
        """Property: Upset alert is correctly preserved after round-trip.

        The upset_alert field should be consistent after serialization
        and deserialization.

        **Validates: Requirements 16.4**
        """
        # Serialize and deserialize
        serialized = prediction.to_dict()
        deserialized = Prediction.from_dict(serialized)

        # Verify upset_alert is preserved
        assert deserialized.upset_alert == prediction.upset_alert

        # Verify upset_alert is correctly calculated based on seeds
        if prediction.winner == prediction.team_a.name:
            winner_seed = prediction.team_a.seed
            opponent_seed = prediction.team_b.seed
        else:
            winner_seed = prediction.team_b.seed
            opponent_seed = prediction.team_a.seed

        expected_upset = winner_seed > opponent_seed
        assert deserialized.upset_alert == expected_upset

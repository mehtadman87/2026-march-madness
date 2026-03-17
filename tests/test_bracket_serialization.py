"""Property-based tests for Bracket round-trip serialization.

**Validates: Requirements 16.3**

Tests that FOR ALL valid Bracket objects, serializing to JSON then deserializing
back SHALL produce an equivalent Bracket object (round-trip property).
"""

from hypothesis import given, settings, strategies as st

from src.models.enums import Region, RoundName
from src.models.team import Bracket, Matchup, RegionBracket, Team


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

# Venue strategy: non-empty text strings
venue_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Game number strategy: positive integers
game_number_strategy = st.integers(min_value=1, max_value=100)

# Season year strategy: reasonable range 2020-2030
season_strategy = st.integers(min_value=2020, max_value=2030)


@st.composite
def team_strategy(draw: st.DrawFn, region: Region, seed: int) -> Team:
    """Generate a Team with a specific region and seed."""
    name = draw(team_name_strategy)
    return Team(name=name, seed=seed, region=region)


@st.composite
def matchup_strategy(
    draw: st.DrawFn, team_a: Team, team_b: Team, game_number: int
) -> Matchup:
    """Generate a Matchup between two teams."""
    venue = draw(venue_strategy)
    return Matchup(
        team_a=team_a,
        team_b=team_b,
        round_name=RoundName.ROUND_OF_64,  # First-round matchups
        venue=venue,
        game_number=game_number,
    )


@st.composite
def region_bracket_strategy(draw: st.DrawFn, region: Region) -> RegionBracket:
    """Generate a RegionBracket with exactly 16 teams and 8 first-round matchups."""
    # Generate 16 teams with seeds 1-16
    teams = []
    for seed in range(1, 17):
        team = draw(team_strategy(region=region, seed=seed))
        teams.append(team)

    # Generate 8 first-round matchups (1v16, 2v15, 3v14, 4v13, 5v12, 6v11, 7v10, 8v9)
    seed_pairings = [(1, 16), (2, 15), (3, 14), (4, 13), (5, 12), (6, 11), (7, 10), (8, 9)]
    matchups = []
    for game_num, (seed_a, seed_b) in enumerate(seed_pairings, start=1):
        team_a = teams[seed_a - 1]  # seed 1 is at index 0
        team_b = teams[seed_b - 1]
        matchup = draw(matchup_strategy(team_a=team_a, team_b=team_b, game_number=game_num))
        matchups.append(matchup)

    return RegionBracket(region=region, teams=teams, matchups=matchups)


@st.composite
def bracket_strategy(draw: st.DrawFn) -> Bracket:
    """Generate a valid Bracket with exactly 64 teams, 4 regions, and 32 matchups."""
    season = draw(season_strategy)

    # Generate 4 region brackets, one for each region
    regions = []
    for region in Region:
        region_bracket = draw(region_bracket_strategy(region=region))
        regions.append(region_bracket)

    return Bracket(regions=regions, season=season)


# --- Property Tests ---


class TestBracketRoundTripSerialization:
    """Property tests for Bracket round-trip serialization.

    **Validates: Requirements 16.3**
    """

    @given(bracket=bracket_strategy())
    @settings(max_examples=100, deadline=None)
    def test_bracket_round_trip_consistency(self, bracket: Bracket) -> None:
        """Property 1: Bracket round-trip consistency.

        FOR ALL valid Bracket objects, serializing to JSON then deserializing
        back SHALL produce an equivalent Bracket object.

        **Validates: Requirements 16.3**
        """
        # Serialize to dict
        serialized = bracket.to_dict()

        # Deserialize back
        deserialized = Bracket.from_dict(serialized)

        # Assert equivalence
        assert deserialized.season == bracket.season
        assert len(deserialized.regions) == len(bracket.regions)

        for orig_region, deser_region in zip(bracket.regions, deserialized.regions):
            assert deser_region.region == orig_region.region
            assert len(deser_region.teams) == len(orig_region.teams)
            assert len(deser_region.matchups) == len(orig_region.matchups)

            # Check teams
            for orig_team, deser_team in zip(orig_region.teams, deser_region.teams):
                assert deser_team.name == orig_team.name
                assert deser_team.seed == orig_team.seed
                assert deser_team.region == orig_team.region

            # Check matchups
            for orig_matchup, deser_matchup in zip(orig_region.matchups, deser_region.matchups):
                assert deser_matchup.team_a.name == orig_matchup.team_a.name
                assert deser_matchup.team_a.seed == orig_matchup.team_a.seed
                assert deser_matchup.team_a.region == orig_matchup.team_a.region
                assert deser_matchup.team_b.name == orig_matchup.team_b.name
                assert deser_matchup.team_b.seed == orig_matchup.team_b.seed
                assert deser_matchup.team_b.region == orig_matchup.team_b.region
                assert deser_matchup.round_name == orig_matchup.round_name
                assert deser_matchup.venue == orig_matchup.venue
                assert deser_matchup.game_number == orig_matchup.game_number

        # Verify bracket structure constraints are maintained
        assert len(deserialized.get_all_teams()) == 64
        assert len(deserialized.get_first_round_matchups()) == 32
        assert len(deserialized.regions) == 4

    @given(bracket=bracket_strategy())
    @settings(max_examples=50, deadline=None)
    def test_double_round_trip_consistency(self, bracket: Bracket) -> None:
        """Property: Double round-trip produces same result.

        Serializing and deserializing twice should produce the same result
        as doing it once.

        **Validates: Requirements 16.3**
        """
        # First round-trip
        first_serialized = bracket.to_dict()
        first_deserialized = Bracket.from_dict(first_serialized)

        # Second round-trip
        second_serialized = first_deserialized.to_dict()
        second_deserialized = Bracket.from_dict(second_serialized)

        # Both serialized forms should be identical
        assert first_serialized == second_serialized

        # Both deserialized forms should be equivalent
        assert second_deserialized.season == first_deserialized.season
        assert len(second_deserialized.regions) == len(first_deserialized.regions)

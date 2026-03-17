"""Agent output dataclasses for March Madness Bracket Predictor.

Defines data structures for outputs from specialized sub-agents:
- TeamStats: Quantitative team statistics from structured APIs
- QualitativeReport: Qualitative team insights from web research
- AdvancedMetrics: Tempo-free efficiency metrics and analytics
- MatchupReport: Head-to-head matchup analysis
- PlayerInfo: Individual player statistics and injury status
- PlayerAssessment: Team roster composition and player evaluation
"""

from dataclasses import dataclass, field


@dataclass
class TeamStats:
    """Quantitative team statistics from structured data APIs.
    
    Validates: Requirements 3.1
    """
    team_name: str
    season_record: str              # e.g. "28-5"
    conference_record: str
    scoring_offense: float          # PPG
    scoring_defense: float          # Opp PPG
    rebounding_margin: float
    turnover_margin: float
    free_throw_pct: float
    three_point_pct: float
    field_goal_pct: float
    tournament_history: list[dict]  # Last 5 years
    conference_tourney_result: str
    strength_of_schedule: float
    quadrant_record: dict[str, str]  # {"Q1": "8-3", "Q2": "5-1", ...}
    data_sources: list[str]         # Which APIs provided data
    missing_fields: list[str]       # Fields that couldn't be retrieved

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "team_name": self.team_name,
            "season_record": self.season_record,
            "conference_record": self.conference_record,
            "scoring_offense": self.scoring_offense,
            "scoring_defense": self.scoring_defense,
            "rebounding_margin": self.rebounding_margin,
            "turnover_margin": self.turnover_margin,
            "free_throw_pct": self.free_throw_pct,
            "three_point_pct": self.three_point_pct,
            "field_goal_pct": self.field_goal_pct,
            "tournament_history": self.tournament_history,
            "conference_tourney_result": self.conference_tourney_result,
            "strength_of_schedule": self.strength_of_schedule,
            "quadrant_record": self.quadrant_record,
            "data_sources": self.data_sources,
            "missing_fields": self.missing_fields,
        }


@dataclass
class QualitativeReport:
    """Qualitative team insights from web research.
    
    Validates: Requirements 4.1, 4.2
    """
    team_name: str
    coach_tournament_record: str
    program_pedigree: str
    conference_strength: str
    current_momentum: str
    transfer_portal_impact: str
    style_identity: str
    sources: list[str]
    unavailable_factors: list[str]

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "team_name": self.team_name,
            "coach_tournament_record": self.coach_tournament_record,
            "program_pedigree": self.program_pedigree,
            "conference_strength": self.conference_strength,
            "current_momentum": self.current_momentum,
            "transfer_portal_impact": self.transfer_portal_impact,
            "style_identity": self.style_identity,
            "sources": self.sources,
            "unavailable_factors": self.unavailable_factors,
        }


@dataclass
class AdvancedMetrics:
    """Tempo-free efficiency metrics and advanced analytics.
    
    Validates: Requirements 5.1
    """
    team_name: str
    adj_offensive_efficiency: float   # Points per 100 possessions
    adj_defensive_efficiency: float
    net_ranking: int
    tempo: float                      # Possessions per 40 min
    effective_fg_pct: float
    turnover_rate: float
    offensive_rebound_pct: float
    free_throw_rate: float
    three_point_pct: float
    three_point_defense_pct: float
    close_game_record: str            # Games decided by ≤5 pts
    last_10_trend: str                # e.g. "8-2"
    data_sources: dict[str, str]      # metric -> source

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "team_name": self.team_name,
            "adj_offensive_efficiency": self.adj_offensive_efficiency,
            "adj_defensive_efficiency": self.adj_defensive_efficiency,
            "net_ranking": self.net_ranking,
            "tempo": self.tempo,
            "effective_fg_pct": self.effective_fg_pct,
            "turnover_rate": self.turnover_rate,
            "offensive_rebound_pct": self.offensive_rebound_pct,
            "free_throw_rate": self.free_throw_rate,
            "three_point_pct": self.three_point_pct,
            "three_point_defense_pct": self.three_point_defense_pct,
            "close_game_record": self.close_game_record,
            "last_10_trend": self.last_10_trend,
            "data_sources": self.data_sources,
        }


@dataclass
class MatchupReport:
    """Head-to-head matchup analysis between two teams.
    
    Validates: Requirements 6.1
    """
    team_a: str
    team_b: str
    venue: str
    team_a_proximity_km: float
    team_b_proximity_km: float
    location_advantage_score: dict[str, float]  # {team_a: 0.7, team_b: 0.3}
    pace_matchup: str                # Analysis of tempo compatibility
    style_matchup: str               # Offensive strengths vs defensive strengths
    size_athleticism: str
    head_to_head_record: str
    seed_baseline_win_rate: float    # From seed_history.json
    factors: list[dict]              # [{name, score_or_assessment}]

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "team_a": self.team_a,
            "team_b": self.team_b,
            "venue": self.venue,
            "team_a_proximity_km": self.team_a_proximity_km,
            "team_b_proximity_km": self.team_b_proximity_km,
            "location_advantage_score": self.location_advantage_score,
            "pace_matchup": self.pace_matchup,
            "style_matchup": self.style_matchup,
            "size_athleticism": self.size_athleticism,
            "head_to_head_record": self.head_to_head_record,
            "seed_baseline_win_rate": self.seed_baseline_win_rate,
            "factors": self.factors,
        }


@dataclass
class PlayerInfo:
    """Individual player statistics and injury status.
    
    Validates: Requirements 7.1, 7.4, 7.5
    """
    name: str
    ppg: float
    rpg: float
    apg: float
    usage_rate: float
    injury_status: str              # "healthy", "questionable", "out", "unknown"
    injury_details: str | None
    estimated_impact: str | None    # Impact if missing

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "name": self.name,
            "ppg": self.ppg,
            "rpg": self.rpg,
            "apg": self.apg,
            "usage_rate": self.usage_rate,
            "injury_status": self.injury_status,
            "injury_details": self.injury_details,
            "estimated_impact": self.estimated_impact,
        }


@dataclass
class PlayerAssessment:
    """Team roster composition and player evaluation.
    
    Validates: Requirements 7.1, 7.4, 7.5
    """
    team_name: str
    key_players: list[PlayerInfo]   # Top 3-4 players
    experience_factor: float        # Upperclassmen-to-freshmen minutes ratio
    bench_depth: str
    star_tournament_experience: str
    player_matchup_dynamics: str    # vs opposing key players
    injury_impact_summary: str

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "team_name": self.team_name,
            "key_players": [player.to_dict() for player in self.key_players],
            "experience_factor": self.experience_factor,
            "bench_depth": self.bench_depth,
            "star_tournament_experience": self.star_tournament_experience,
            "player_matchup_dynamics": self.player_matchup_dynamics,
            "injury_impact_summary": self.injury_impact_summary,
        }

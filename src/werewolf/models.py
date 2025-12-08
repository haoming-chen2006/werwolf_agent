from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

PhaseType = Literal["day", "night"]
RoleName = Literal["werewolf", "detective", "doctor", "peasant", "villager"]
Alignment = Literal["wolves", "town"]


class PlayerCard(BaseModel):
    id: str
    name: str
    url: Optional[str] = None
    alias: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    initial_elo: Optional[Dict[str, int]] = None


class MatchRequest(BaseModel):
    players: List[PlayerCard]
    seed: int = 0
    config: Dict[str, Any] = Field(default_factory=dict)


class PlayerProfile(BaseModel):
    id: str
    alias: Optional[str] = None
    role_private: Optional[RoleName] = None
    alignment: Optional[Alignment] = None
    alive: bool = True
    provider: Optional[str] = None
    model: Optional[str] = None
    url: Optional[str] = None
    initial_elo: Dict[str, int] = Field(
        default_factory=lambda: {"overall": 1500, "wolf": 1500, "villager": 1500}
    )


class DayDiscussionConstraints(BaseModel):
    max_words: int
    no_role_reveal: bool = True
    json_only: bool = True


class DayDiscussionPrompt(BaseModel):
    phase: Literal["day"] = "day"
    day_number: int
    you: Dict[str, Any]
    players: List[Dict[str, Any]]
    public_history: List[Dict[str, Any]]
    role_statement: Optional[str] = None
    private_thoughts_history: Optional[List[Dict[str, Any]]] = None
    public_speech_history: Optional[List[Dict[str, Any]]] = None
    history_text: Optional[str] = None
    instruction: str = "Output strictly JSON with 'thought' and 'speech'."
    constraints: DayDiscussionConstraints


class DayDiscussionResponse(BaseModel):
    thought: str
    speech: str
    speech: str


class DiscussionTurn(BaseModel):
    player_id: str
    day_discussion_prompt: DayDiscussionPrompt
    private_thought: Any
    day_discussion_response: DayDiscussionResponse


class DayPublicState(BaseModel):
    alive_players: List[str]
    public_history: List[Dict[str, Any]]


class VoteConstraints(BaseModel):
    json_only: bool = True


class DayVotePrompt(BaseModel):
    phase: Literal["vote"]
    day_number: int
    you: Dict[str, Any]
    options: List[str]
    public_summary: str
    public_history: Optional[List[Dict[str, Any]]] = None
    private_thoughts_history: Optional[List[Dict[str, Any]]] = None
    public_speech_history: Optional[List[Dict[str, Any]]] = None
    history_text: Optional[str] = None
    constraints: VoteConstraints = Field(default_factory=VoteConstraints)


class VoteResponse(BaseModel):
    speech: str
    vote: str
    one_sentence_reason: str


class VotePromptRecord(BaseModel):
    player_id: str
    day_vote_prompt: DayVotePrompt


class VoteResponseRecord(BaseModel):
    player_id: str
    vote_response: VoteResponse


class VoteResolution(BaseModel):
    tally: Dict[str, int]
    eliminated: Optional[Dict[str, Any]] = None
    runoff: Optional[List[str]] = None


class DayVotingRecord(BaseModel):
    prompts: List[VotePromptRecord]
    responses: List[VoteResponseRecord]
    resolution: VoteResolution
    private_reactions: Dict[str, Any] = Field(default_factory=dict)


class DayPhaseRecord(BaseModel):
    phase_type: Literal["day"] = "day"
    day_number: int
    public_state: DayPublicState
    discussion: Dict[str, Any]
    voting: DayVotingRecord
    end_of_day_summary: Optional[Dict[str, Any]] = None


class NightConstraints(BaseModel):
    json_only: bool = True


class NightRolePrompt(BaseModel):
    phase: Literal["night"]
    night_number: int
    role: RoleName
    you: Dict[str, Any]
    options: Dict[str, Any]
    public_history_summary: str
    role_statement: Optional[str] = None
    private_thoughts_history: Optional[List[Dict[str, Any]]] = None
    public_speech_history: Optional[List[Dict[str, Any]]] = None
    history_text: Optional[str] = None
    constraints: NightConstraints = Field(default_factory=NightConstraints)


class NightPromptRecord(BaseModel):
    player_id: str
    night_role_prompt: NightRolePrompt
    private_thought: Any


class NightResponseRecord(BaseModel):
    player_id: str
    night_action_response: Dict[str, Any]


class WolfChatEntry(BaseModel):
    speaker: str
    content: str


class NightResolution(BaseModel):
    wolf_team_decision: Dict[str, Any]
    detective_result: Optional[Dict[str, Any]] = None
    doctor_protect: Optional[Dict[str, Any]] = None
    night_outcome: Dict[str, Any] = Field(default_factory=dict)
    night_kill: Dict[str, Any] = Field(default_factory=dict)
    public_update: str


class NightPhaseRecord(BaseModel):
    phase_type: Literal["night"] = "night"
    night_number: int
    public_state: Dict[str, Any]
    wolves_private_chat: List[WolfChatEntry]
    prompts: List[NightPromptRecord]
    responses: List[NightResponseRecord]
    resolution: NightResolution


PhaseRecord = Union[DayPhaseRecord, NightPhaseRecord]


class FinalResult(BaseModel):
    winning_side: Alignment
    reason: str
    survivors: List[Dict[str, Any]]
    elimination_order: List[Dict[str, Any]]


class AgentMetrics(BaseModel):
    alias: Optional[str]
    role: RoleName
    alignment: Alignment
    won: bool
    days_survived: int
    votes_cast: List[Dict[str, Any]]
    received_votes: List[Dict[str, Any]]
    eliminated_on_day: Optional[int] = None
    inspections: Optional[List[Dict[str, Any]]] = None
    protections: Optional[List[Dict[str, Any]]] = None


class RoleSummary(BaseModel):
    games_played: int
    wins: int
    losses: int
    win_rate: float
    average_initial_elo: Optional[float] = None


class MetricsSummary(BaseModel):
    town_win: bool
    wolves_eliminated_days: List[int]
    mis_eliminations: List[Dict[str, Any]]
    mis_elim_rate: float
    total_days: int


class AgentDecisionQuality(BaseModel):
    votes_on_enemies_rate: float
    wolves_voted: int
    town_voted: int
    bus_rate: Optional[float] = None


class DayDecisionQuality(BaseModel):
    day_number: int
    town_precision: float
    town_recall: float
    mis_elimination: bool


class AgentInfluence(BaseModel):
    swing_votes: int
    early_final_wagon_votes: int


class DaySwingEvent(BaseModel):
    day_number: int
    swing_voter: Optional[str]
    target: Optional[str]


class DecisionQualityMetrics(BaseModel):
    per_agent: Dict[str, AgentDecisionQuality]
    per_day: List[DayDecisionQuality]


class InfluenceMetrics(BaseModel):
    per_agent: Dict[str, AgentInfluence]
    swing_events: List[DaySwingEvent]


class PostGameMetrics(BaseModel):
    per_agent: Dict[str, AgentMetrics]
    per_role: Dict[RoleName, RoleSummary]
    summary: MetricsSummary
    decision_quality: Optional[DecisionQualityMetrics] = None
    influence: Optional[InfluenceMetrics] = None
    # Advanced metrics
    persuasion: Optional["PersuasionMetrics"] = None
    resistance: Optional["ResistanceMetrics"] = None
    early_signals: Optional["EarlySignalMetrics"] = None
    strategy_alignment: Optional["StrategyAlignmentMetrics"] = None
    coordination: Optional["CoordinationMetrics"] = None
    counterfactual_impact: Optional["CounterfactualImpact"] = None
    rating_robustness: Optional["RatingRobustness"] = None
    style: Optional["StyleMetrics"] = None
    centrality: Optional["CentralityMetrics"] = None


# Advanced metrics containers

class PersuasionAgentStats(BaseModel):
    swings_caused: int
    speeches_count: int
    swings_per_speech: float
    avg_wagon_delta: Optional[float] = None


class PersuasionMetrics(BaseModel):
    per_agent: Dict[str, PersuasionAgentStats]
    attributions: List[Dict[str, Any]] = Field(default_factory=list)


class ResistanceAgentStats(BaseModel):
    exposures: int
    resisted: int
    resistance_rate: float


class ResistanceMetrics(BaseModel):
    per_agent: Dict[str, ResistanceAgentStats]


class EarlySignalMetrics(BaseModel):
    day1_wolf_elim: bool
    day1_precision: float
    day1_recall: float
    villager_mentions_of_wolves: int
    total_mentions_day1: int


class StrategyAlignmentAgent(BaseModel):
    private_to_public_alignment: Optional[float] = None
    private_to_vote_alignment: Optional[float] = None
    deception_delta: Optional[float] = None


class StrategyAlignmentMetrics(BaseModel):
    per_agent: Dict[str, StrategyAlignmentAgent]


class CoordinationMetrics(BaseModel):
    wolf_argument_similarity: Optional[float] = None
    sequential_support_events: int
    coordinated_push_score: Optional[float] = None


class PivotalVote(BaseModel):
    day_number: int
    voter: str
    target: str


class CounterfactualImpact(BaseModel):
    pivotal_votes: List[PivotalVote] = Field(default_factory=list)
    per_agent_pivotal_count: Dict[str, int] = Field(default_factory=dict)


class RatingRobustness(BaseModel):
    elo_ci_overall: Optional[List[float]] = None
    elo_ci_wolf: Optional[List[float]] = None
    elo_ci_villager: Optional[List[float]] = None
    volatility_index: Optional[float] = None


class StyleAgentMetrics(BaseModel):
    hedging_rate: float
    certainty_rate: float
    toxicity_flag_count: int
    avg_words_vs_limit: Optional[float] = None


class StyleMetrics(BaseModel):
    per_agent: Dict[str, StyleAgentMetrics]


class CentralityAgent(BaseModel):
    in_degree: int
    out_degree: int
    leadership_index: Optional[float] = None


class CentralityMetrics(BaseModel):
    per_agent: Dict[str, CentralityAgent]


# PostGameMetrics extensions for advanced metrics

class AdvancedPostGame(BaseModel):
    persuasion: Optional[PersuasionMetrics] = None
    resistance: Optional[ResistanceMetrics] = None
    early_signals: Optional[EarlySignalMetrics] = None
    strategy_alignment: Optional[StrategyAlignmentMetrics] = None
    coordination: Optional[CoordinationMetrics] = None
    counterfactual_impact: Optional[CounterfactualImpact] = None
    rating_robustness: Optional[RatingRobustness] = None
    style: Optional[StyleMetrics] = None
    centrality: Optional[CentralityMetrics] = None


class GameRecord(BaseModel):
    schema_version: str
    game_id: str
    created_at_utc: datetime
    seed: int
    config: Dict[str, Any]
    players: List[PlayerProfile]
    role_assignment: Dict[str, RoleName]
    phase_sequence: List[str] = Field(default_factory=list)
    phases: List[PhaseRecord]
    final_result: FinalResult


class Assessment(BaseModel):
    record: GameRecord
    metrics: PostGameMetrics


# Night Phase API Models
class NightActionRequest(BaseModel):
    player_id: str
    action_type: str  # "kill", "inspect", "protect", "heal", "kill_potion"
    target: Optional[str] = None
    reasoning: Optional[str] = None
    message: Optional[str] = None  # For wolf chat


class NightActionResponse(BaseModel):
    success: bool
    message: str
    action_id: Optional[str] = None


class NightContextRequest(BaseModel):
    player_id: str
    role: str


class NightContextResponse(BaseModel):
    role: str
    night_number: int
    available_actions: List[str]
    targets: List[str]
    private_info: Dict[str, Any]
    public_info: Dict[str, Any]


class NightPhaseStartRequest(BaseModel):
    game_id: str
    night_number: int


class NightPhaseStartResponse(BaseModel):
    success: bool
    message: str
    night_number: int
    phase_id: str


class NightPhaseResolveRequest(BaseModel):
    phase_id: str


class NightPhaseResolveResponse(BaseModel):
    success: bool
    message: str
    outcomes: Dict[str, Any]
    public_announcement: str

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import GameRecord


def extract_message_timeline(record: GameRecord) -> List[Dict[str, Any]]:
    """Flatten day discussions into an ordered message timeline with metadata.

    Each entry contains: {day, order, player_id, text}
    """
    timeline: List[Dict[str, Any]] = []
    for phase in record.phases:
        if phase.phase_type != "day":
            continue
        order = 0
        turns = phase.discussion.get("turns", []) if isinstance(phase.discussion, dict) else []
        for t in turns:
            timeline.append(
                {
                    "day": phase.day_number,
                    "order": order,
                    "player_id": t.player_id,
                    "text": t.day_discussion_response.talk if t.day_discussion_response else "",
                    "private": t.private_thought,
                }
            )
            order += 1
    return timeline


def build_vote_timeline(record: GameRecord) -> Dict[int, List[Tuple[str, str]]]:
    """Return per-day ordered list of (voter, target) from vote responses."""
    per_day: Dict[int, List[Tuple[str, str]]] = {}
    for phase in record.phases:
        if phase.phase_type != "day":
            continue
        votes: List[Tuple[str, str]] = []
        for resp in phase.voting.responses:
            votes.append((resp.player_id, resp.vote_response.vote))
        per_day[phase.day_number] = votes
    return per_day


def intent_edges(record: GameRecord) -> List[Tuple[str, str, int]]:
    """Heuristically infer (speaker -> target) edges when a speech names a player.

    Returns list of (speaker_id, target_id, day).
    """
    # Simple heuristic: if a speech contains an exact player id token, register an edge.
    player_ids = {p.id for p in record.players}
    edges: List[Tuple[str, str, int]] = []
    for phase in record.phases:
        if phase.phase_type != "day":
            continue
        for t in phase.discussion.get("turns", []) if isinstance(phase.discussion, dict) else []:
            text = (t.day_discussion_response.talk or "").upper()
            for pid in player_ids:
                if pid.upper() in text:
                    edges.append((t.player_id, pid, phase.day_number))
    return edges



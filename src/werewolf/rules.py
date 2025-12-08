from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, Optional, Tuple


def resolve_vote(votes: Dict[str, str], alive_players: Iterable[str]) -> Tuple[Dict[str, int], Optional[str], Optional[Iterable[str]]]:
    """Resolve a vote among alive players.

    Returns a tally mapping, the eliminated player if any, and a list of runoff finalists when tied.
    """
    alive_set = set(alive_players)
    filtered = {voter: target for voter, target in votes.items() if target in alive_set}
    tally = Counter(filtered.values())
    if not tally:
        return {}, None, None
    max_votes = max(tally.values())
    leaders = [pid for pid, count in tally.items() if count == max_votes]
    if len(leaders) == 1:
        return dict(tally), leaders[0], None
    return dict(tally), None, leaders


def night_kill_resolution(
    target: Optional[str],
    protect_target: Optional[str],
    doctor_id: Optional[str],
) -> Dict[str, Optional[str]]:
    """Return structured info about a night kill attempt."""
    if target is None:
        return {"target": None, "success": False, "saved_by": None}
    if protect_target and target == protect_target:
        return {"target": target, "success": False, "saved_by": doctor_id}
    return {"target": target, "success": True, "saved_by": None}

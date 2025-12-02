from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from .models import Alignment, RoleName


class GameState:
    def __init__(self, players: List[str], roles: Dict[str, RoleName], alignments: Dict[str, Alignment]):
        if set(players) != set(roles):
            raise ValueError("Role assignment must cover the same players")
        self.players = players
        self.roles = roles
        self.alignments = alignments
        self.alive: Dict[str, bool] = {pid: True for pid in players}
        self.night_number = 1
        self.day_number = 1
        self.public_history: List[Dict[str, Any]] = []
        self.graveyard: List[Dict[str, Any]] = []
        self.vote_cast_log: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in players}
        self.vote_received_log: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in players}
        self.inspection_log: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in players}
        self.protection_log: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in players}
        self.elimination_order: List[Dict[str, Any]] = []

    def is_alive(self, pid: str) -> bool:
        return self.alive.get(pid, False)

    def living_players(self) -> List[str]:
        return [pid for pid, alive in self.alive.items() if alive]

    def wolves(self) -> List[str]:
        return [pid for pid, role in self.roles.items() if role == "werewolf"]

    def alignment_of(self, pid: str) -> Alignment:
        return self.alignments[pid]

    def record_vote(self, voter: str, target: str, day_number: int, reason: str) -> None:
        self.vote_cast_log[voter].append({"day": day_number, "target": target, "reason": reason})
        self.vote_received_log[target].append({"day": day_number, "from": voter})

    def record_inspection(self, seer: str, target: str, night_number: int, is_wolf: bool) -> None:
        self.inspection_log[seer].append({"night": night_number, "target": target, "is_werewolf": is_wolf})

    def record_protection(self, doctor: str, target: Optional[str], night_number: int, saved: bool) -> None:
        self.protection_log[doctor].append({"night": night_number, "target": target, "saved": saved})

    def eliminate(self, pid: Optional[str], cause: str, phase: str, index: int) -> None:
        if not pid or not self.is_alive(pid):
            return
        self.alive[pid] = False
        payload = {
            "phase": phase,
            "cause": cause,
            "index": index,
            "player_id": pid,
            "role": self.roles[pid],
            "alignment": self.alignments[pid],
        }
        if phase == "day":
            payload["day"] = index
        else:
            payload["night"] = index
        self.graveyard.append({"player": pid, "cause": cause, "phase": phase, "index": index})
        self.public_history.append(payload)
        self.elimination_order.append(payload.copy())

    def record_night_event(self, night_number: int, event: str, extra: Optional[Dict[str, Any]] = None) -> None:
        entry: Dict[str, Any] = {"phase": "night", "night": night_number, "event": event}
        if extra:
            entry.update(extra)
        self.public_history.append(entry)

    def last_graveyard_entry(self) -> Optional[Dict[str, Any]]:
        return self.graveyard[-1] if self.graveyard else None

    def wolves_remaining(self) -> int:
        return sum(1 for pid in self.wolves() if self.is_alive(pid))

    def town_remaining(self) -> int:
        return sum(1 for pid, alive in self.alive.items() if alive and self.alignments[pid] == "town")

    def is_terminal(self) -> bool:
        return self.wolves_remaining() == 0 or self.wolves_remaining() >= self.town_remaining()

    def winner(self) -> Alignment | Literal["ongoing"]:
        if self.wolves_remaining() == 0:
            return "town"
        if self.wolves_remaining() >= self.town_remaining():
            return "wolves"
        return "ongoing"

"""Night phase prompt generation for different roles."""

from typing import Dict, List, Any, Optional
from .models import NightRolePrompt, NightConstraints
from .state import GameState


def generate_wolf_night_prompt(
    state: GameState,
    wolf_id: str,
    night_number: int,
    wolf_partners: List[str],
    wolf_chat_history: List[Dict[str, str]],
    history_text: str = ""
) -> NightRolePrompt:
    """Generate night prompt for werewolf role."""

    # Get potential targets (non-wolf players)
    kill_targets = [pid for pid in state.living_players() if state.roles[pid] != "werewolf"]

    # Build wolf-specific context
    wolf_context = {
        "your_role": "werewolf",
        "wolf_partners": wolf_partners,
        "wolf_chat_history": wolf_chat_history,
        "kill_targets": kill_targets,
        "night_number": night_number,
        "game_state": {
            "alive_players": state.living_players(),
            "public_history": state.public_history[-3:] if state.public_history else []
        }
    }

    # Format history for natural language
    history_section = ""
    if history_text:
        history_section = f"""
YOUR PAST HISTORY:
{history_text}

"""

    prompt_text = f"""You are playing a game of Werewolf.
Werewolf is a social deduction game where players are divided into two teams: the villagers (who want to identify and eliminate the werewolves) and the werewolves (who want to eliminate the villagers without being caught).
The game setup includes 7 players: 2 Werewolves, 1 Detective, 1 Doctor, and 3 Villagers.

YOUR ROLE:
You are a WEREWOLF (Player ID: {wolf_id}).
Your goal is to eliminate villagers until the number of werewolves equals or exceeds the number of villagers.
Your wolf partners are: {', '.join(wolf_partners) if wolf_partners else 'You are the only wolf'}.

{history_section}CURRENT SITUATION:
- It is Night {night_number}
- Alive players: {', '.join(state.living_players())}

AVAILABLE ACTIONS:
You must choose ONE target to kill tonight from the following players:
{', '.join(kill_targets)}

INSTRUCTIONS:
- Reply with ONLY the player ID of your target (e.g. 'p1').
- Do NOT output JSON. Do NOT output thoughts. Just the ID.

Response:"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="werewolf",
        you={"id": wolf_id, "role": "werewolf"},
        options=wolf_context,
        public_history_summary=_get_history_summary(state),
        role_statement=prompt_text,
        constraints=NightConstraints(json_only=False)
    )


def generate_detective_night_prompt(
    state: GameState,
    detective_id: str,
    night_number: int,
    previous_inspections: List[Dict[str, Any]],
    history_text: str = ""
) -> NightRolePrompt:
    """Generate night prompt for detective/seer role."""

    # Get potential targets (can't inspect self)
    inspect_targets = [pid for pid in state.living_players() if pid != detective_id]

    detective_context = {
        "your_role": "detective",
        "inspect_targets": inspect_targets,
        "previous_inspections": previous_inspections,
        "night_number": night_number,
        "game_state": {
            "alive_players": state.living_players(),
            "public_history": state.public_history[-3:] if state.public_history else []
        }
    }

    # Format history for natural language
    history_section = ""
    if history_text:
        history_section = f"""
YOUR PAST HISTORY:
{history_text}

"""

    inspection_info = _format_inspection_history(previous_inspections)

    prompt_text = f"""You are playing a game of Werewolf.
Werewolf is a social deduction game where players are divided into two teams: the villagers (who want to identify and eliminate the werewolves) and the werewolves (who want to eliminate the villagers without being caught).
The game setup includes 7 players: 2 Werewolves, 1 Detective, 1 Doctor, and 3 Villagers.

YOUR ROLE:
You are the DETECTIVE (Seer) (Player ID: {detective_id}).
Your goal is to help the village by identifying werewolves. Each night, you can inspect one player to learn their true role.

{history_section}YOUR PREVIOUS INSPECTIONS:
{inspection_info}

CURRENT SITUATION:
- It is Night {night_number}
- Alive players: {', '.join(state.living_players())}

AVAILABLE ACTIONS:
You can inspect ONE of the following players tonight:
{', '.join(inspect_targets)}

INSTRUCTIONS:
- Reply with ONLY the player ID to inspect (e.g. 'p2').
- Do NOT output JSON. Do NOT output thoughts. Just the ID.

Response:"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="detective",
        you={"id": detective_id, "role": "detective"},
        options=detective_context,
        public_history_summary=_get_history_summary(state),
        role_statement=prompt_text,
        constraints=NightConstraints(json_only=False)
    )


def generate_doctor_night_prompt(
    state: GameState,
    doctor_id: str,
    night_number: int,
    potion_status: Dict[str, bool],
    attacked_player: Optional[str] = None,
    history_text: str = ""
) -> NightRolePrompt:
    """Generate night prompt for doctor/witch role."""

    doctor_context = {
        "your_role": "doctor",
        "potion_status": potion_status,
        "night_number": night_number,
        "attacked_player": attacked_player,
        "game_state": {
            "alive_players": state.living_players(),
            "public_history": state.public_history[-3:] if state.public_history else []
        }
    }

    has_save = not potion_status.get('heal_potion_used', False)

    # Format history for natural language
    history_section = ""
    if history_text:
        history_section = f"""
YOUR PAST HISTORY:
{history_text}

"""

    if attacked_player and has_save:
        prompt_text = f"""You are playing a game of Werewolf.
The game setup includes 7 players: 2 Werewolves, 1 Detective, 1 Doctor, and 3 Villagers.

YOUR ROLE:
You are the DOCTOR (Witch) (Player ID: {doctor_id}).
Your goal is to protect villagers. You have ONE healing potion for the entire game.

{history_section}CURRENT SITUATION:
- It is Night {night_number}
- Alive players: {', '.join(state.living_players())}

CRITICAL EVENT:
Player {attacked_player} was attacked by werewolves tonight!

DECISION:
You have a healing potion available. Do you want to use it to SAVE {attacked_player}?
Remember: This is your ONLY save for the entire game. Choose wisely.

INSTRUCTIONS:
- Reply 'YES' to save {attacked_player}.
- Reply 'NO' to let them die and save your potion.
- Reply with ONLY 'YES' or 'NO'. Do NOT output JSON.

Response:"""
    elif not has_save:
        prompt_text = f"""You are playing a game of Werewolf.
YOUR ROLE:
You are the DOCTOR (Witch) (Player ID: {doctor_id}).

{history_section}CURRENT SITUATION:
- It is Night {night_number}
- You have already used your healing potion. You cannot save anyone tonight.

INSTRUCTIONS:
- Reply 'NO' to acknowledge.
- Reply with ONLY 'NO'.

Response:"""
    else:
        # No attack (shouldn't happen if we only prompt on attack) or some other state
        prompt_text = f"""You are playing a game of Werewolf.
YOUR ROLE:
You are the DOCTOR (Witch) (Player ID: {doctor_id}).

{history_section}CURRENT SITUATION:
- It is Night {night_number}
- No one was attacked tonight (or you cannot act).

INSTRUCTIONS:
- Reply 'NO'.

Response:"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="doctor",
        you={"id": doctor_id, "role": "doctor"},
        options=doctor_context,
        public_history_summary=_get_history_summary(state),
        role_statement=prompt_text,
        constraints=NightConstraints(json_only=False)
    )


def generate_villager_night_prompt(
    state: GameState,
    villager_id: str,
    night_number: int,
    history_text: str = ""
) -> NightRolePrompt:
    """Generate night prompt for villager role."""

    villager_context = {
        "your_role": "villager",
        "night_number": night_number,
        "game_state": {
            "alive_players": state.living_players(),
            "public_history": state.public_history[-3:] if state.public_history else []
        }
    }

    # Format history for natural language
    history_section = ""
    if history_text:
        history_section = f"""
YOUR PAST HISTORY:
{history_text}

"""

    prompt_text = f"""You are playing a game of Werewolf.
YOUR ROLE:
You are a VILLAGER (Player ID: {villager_id}).
You have no special powers during the night.

{history_section}CURRENT SITUATION:
- It is Night {night_number}
- You are sleeping and have no actions available.

INSTRUCTIONS:
- Reply 'SLEEP'.
- Reply with ONLY 'SLEEP'.

Response:"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="villager",
        you={"id": villager_id, "role": "villager"},
        options=villager_context,
        public_history_summary=_get_history_summary(state),
        role_statement=prompt_text,
        constraints=NightConstraints(json_only=False)
    )


def _format_chat_history(chat_history: List[Dict[str, str]]) -> str:
    """Format wolf chat history for display."""
    if not chat_history:
        return "No previous wolf chat messages."
    
    formatted = []
    for msg in chat_history[-5:]:  # Show last 5 messages
        formatted.append(f"- {msg.get('speaker', 'Unknown')}: {msg.get('content', '')}")
    
    return "\n".join(formatted)


def _format_inspection_history(inspections: List[Dict[str, Any]]) -> str:
    """Format inspection history for display."""
    if not inspections:
        return "No previous inspections."
    
    formatted = []
    for insp in inspections:
        target = insp.get('target', 'Unknown')
        is_wolf = insp.get('is_werewolf', False)
        result = "WEREWOLF" if is_wolf else "VILLAGER"
        formatted.append(f"- {target}: {result}")
    
    return "\n".join(formatted)


def _get_history_summary(state: GameState) -> str:
    """Get a summary of recent game history."""
    if not state.public_history:
        return "This is the first night of the game."
    
    recent_events = []
    for event in state.public_history[-3:]:
        if event.get("phase") == "night":
            if event.get("event") == "night_kill":
                target = event.get("player_id") or event.get("target")
                recent_events.append(f"Night {event.get('night')}: {target} was killed")
            elif event.get("event") == "no_kill":
                recent_events.append(f"Night {event.get('night')}: no one was killed")
        elif event.get("phase") == "day" and event.get("cause") == "vote":
            recent_events.append(f"Day {event.get('day')}: {event.get('player_id')} was eliminated")
    
    return "; ".join(recent_events) if recent_events else "No recent events."

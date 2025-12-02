"""Night phase prompt generation for different roles."""

from typing import Dict, List, Any, Optional
from .models import NightRolePrompt, NightConstraints
from .state import GameState


def generate_wolf_night_prompt(
    state: GameState, 
    wolf_id: str, 
    night_number: int,
    wolf_partners: List[str],
    wolf_chat_history: List[Dict[str, str]]
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
    
    prompt_text = f"""You are a WEREWOLF in a game of Werewolf.

GAME STATE:
- Night {night_number}
- Alive players: {', '.join(state.living_players())}
- Your wolf partners: {', '.join(wolf_partners)}

YOUR OBJECTIVE:
Eliminate villagers to achieve parity with the town. You must work with your wolf partners to choose a target to kill tonight.

AVAILABLE ACTIONS:
1. KILL - Choose a villager to eliminate tonight
2. WOLF_CHAT - Communicate with your wolf partners

TARGETS FOR KILLING:
{', '.join(kill_targets)}

WOLF CHAT HISTORY:
{_format_chat_history(wolf_chat_history)}

INSTRUCTIONS:
- You may use wolf_chat to coordinate with your partners
- You must choose ONE target to kill tonight
- Consider who would be most strategic to eliminate
- Think about who might be protected by the doctor
- Consider the mayor and other power roles

Respond with JSON format:
{{
    "action": "kill" or "wolf_chat",
    "target": "player_id" (if action is kill),
    "message": "your message" (if action is wolf_chat),
    "reasoning": "your strategic reasoning"
}}"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="werewolf",
        you={"id": wolf_id, "role": "werewolf"},
        options=wolf_context,
        public_history_summary=_get_history_summary(state),
        constraints=NightConstraints(json_only=True)
    )


def generate_detective_night_prompt(
    state: GameState,
    detective_id: str,
    night_number: int,
    previous_inspections: List[Dict[str, Any]]
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
    
    prompt_text = f"""You are the DETECTIVE (Seer) in a game of Werewolf.

GAME STATE:
- Night {night_number}
- Alive players: {', '.join(state.living_players())}

YOUR OBJECTIVE:
Use your detective powers to identify werewolves. Each night, you can inspect one player to learn their true role.

AVAILABLE ACTIONS:
1. INSPECT - Choose a player to investigate tonight

TARGETS FOR INSPECTION:
{', '.join(inspect_targets)}

PREVIOUS INSPECTIONS:
{_format_inspection_history(previous_inspections)}

INSTRUCTIONS:
- Choose ONE player to inspect tonight
- You will learn if they are a werewolf or not
- Use this information strategically during day phases
- Be careful not to reveal your role too early
- Consider who might be most suspicious or important

Respond with JSON format:
{{
    "action": "inspect",
    "target": "player_id",
    "reasoning": "why you chose this target"
}}"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="detective",
        you={"id": detective_id, "role": "detective"},
        options=detective_context,
        public_history_summary=_get_history_summary(state),
        constraints=NightConstraints(json_only=True)
    )


def generate_doctor_night_prompt(
    state: GameState,
    doctor_id: str,
    night_number: int,
    potion_status: Dict[str, bool]
) -> NightRolePrompt:
    """Generate night prompt for doctor/witch role."""
    
    # All living players can be protected
    protect_targets = state.living_players()
    
    doctor_context = {
        "your_role": "doctor",
        "protect_targets": protect_targets,
        "potion_status": potion_status,
        "night_number": night_number,
        "game_state": {
            "alive_players": state.living_players(),
            "public_history": state.public_history[-3:] if state.public_history else []
        }
    }
    
    prompt_text = f"""You are the DOCTOR (Witch) in a game of Werewolf.

GAME STATE:
- Night {night_number}
- Alive players: {', '.join(state.living_players())}

YOUR OBJECTIVE:
Protect villagers from werewolf attacks using your healing potion. You can also use a death potion to eliminate a player.

AVAILABLE ACTIONS:
1. PROTECT - Use healing potion to save someone from werewolf attack
2. KILL_POTION - Use death potion to eliminate a player (if available)

TARGETS FOR PROTECTION:
{', '.join(protect_targets)}

POTION STATUS:
- Healing potion: {'Available' if not potion_status.get('heal_potion_used', False) else 'Used'}
- Death potion: {'Available' if not potion_status.get('kill_potion_used', False) else 'Used'}

INSTRUCTIONS:
- You can protect anyone, including yourself
- If you protect the werewolf's target, the kill will be prevented
- Use your death potion strategically to eliminate suspicious players
- Consider who the werewolves might target
- Think about who might be important for the village

Respond with JSON format:
{{
    "action": "protect" or "kill_potion",
    "target": "player_id",
    "reasoning": "why you chose this target"
}}"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="doctor",
        you={"id": doctor_id, "role": "doctor"},
        options=doctor_context,
        public_history_summary=_get_history_summary(state),
        constraints=NightConstraints(json_only=True)
    )


def generate_villager_night_prompt(
    state: GameState,
    villager_id: str,
    night_number: int
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
    
    prompt_text = f"""You are a VILLAGER in a game of Werewolf.

GAME STATE:
- Night {night_number}
- Alive players: {', '.join(state.living_players())}

YOUR OBJECTIVE:
Help the village identify and eliminate werewolves during day phases. You have no special night actions.

AVAILABLE ACTIONS:
1. SLEEP - You have no night actions as a villager

INSTRUCTIONS:
- You have no special powers during the night
- Use this time to think about the day's events
- Consider who might be suspicious
- Prepare for tomorrow's discussion and voting
- Trust your instincts but look for evidence

Respond with JSON format:
{{
    "action": "sleep",
    "reasoning": "your thoughts about the game so far"
}}"""

    return NightRolePrompt(
        phase="night",
        night_number=night_number,
        role="villager",
        you={"id": villager_id, "role": "villager"},
        options=villager_context,
        public_history_summary=_get_history_summary(state),
        constraints=NightConstraints(json_only=True)
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

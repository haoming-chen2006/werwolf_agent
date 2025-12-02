"""Tool definitions for white agents during night phases."""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class NightActionTool(BaseModel):
    """Tool for submitting night actions."""
    name: str = "submit_night_action"
    description: str = "Submit a night action (kill, inspect, protect, wolf_chat, etc.)"
    parameters: Dict[str, Any] = Field(
        default={
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["kill", "inspect", "protect", "heal", "kill_potion", "wolf_chat", "sleep"],
                    "description": "The type of night action to perform"
                },
                "target": {
                    "type": "string",
                    "description": "The target player ID (required for kill, inspect, protect, heal, kill_potion)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Your strategic reasoning for this action"
                },
                "message": {
                    "type": "string",
                    "description": "Message for wolf chat (only used with wolf_chat action)"
                }
            },
            "required": ["action_type"]
        }
    )


class GetNightContextTool(BaseModel):
    """Tool for getting night phase context."""
    name: str = "get_night_context"
    description: str = "Get your role-specific night phase context and available actions"
    parameters: Dict[str, Any] = Field(
        default={
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["werewolf", "detective", "doctor", "villager"],
                    "description": "Your role in the game"
                }
            },
            "required": ["role"]
        }
    )


class WolfChatTool(BaseModel):
    """Tool for wolf team communication."""
    name: str = "wolf_chat"
    description: str = "Send a message to your wolf team (only available to werewolves)"
    parameters: Dict[str, Any] = Field(
        default={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Your message to the wolf team"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Your strategic reasoning behind this message"
                }
            },
            "required": ["message"]
        }
    )


class SubmitReasoningTool(BaseModel):
    """Tool for submitting private reasoning."""
    name: str = "submit_private_reasoning"
    description: str = "Submit your private thoughts and reasoning for evaluation"
    parameters: Dict[str, Any] = Field(
        default={
            "type": "object",
            "properties": {
                "thoughts": {
                    "type": "string",
                    "description": "Your private thoughts and strategic reasoning"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Your confidence level in this reasoning (0-1)"
                }
            },
            "required": ["thoughts"]
        }
    )


def get_night_tools_for_role(role: str) -> List[Dict[str, Any]]:
    """Get available tools for a specific role during night phase."""
    base_tools = [
        NightActionTool().model_dump(),
        GetNightContextTool().model_dump(),
        SubmitReasoningTool().model_dump()
    ]
    
    if role == "werewolf":
        base_tools.append(WolfChatTool().model_dump())
    
    return base_tools


def validate_night_action(action_data: Dict[str, Any], role: str) -> Dict[str, Any]:
    """Validate a night action based on role and game rules."""
    action_type = action_data.get("action_type")
    target = action_data.get("target")
    message = action_data.get("message")
    
    # Role-specific validation
    if role == "werewolf":
        if action_type not in ["kill", "wolf_chat", "sleep"]:
            return {"valid": False, "error": f"Invalid action type for werewolf: {action_type}"}
        if action_type == "kill" and not target:
            return {"valid": False, "error": "Target is required for kill action"}
        if action_type == "wolf_chat" and not message:
            return {"valid": False, "error": "Message is required for wolf chat"}
    
    elif role == "detective":
        if action_type not in ["inspect", "sleep"]:
            return {"valid": False, "error": f"Invalid action type for detective: {action_type}"}
        if action_type == "inspect" and not target:
            return {"valid": False, "error": "Target is required for inspect action"}
    
    elif role == "doctor":
        if action_type not in ["protect", "kill_potion", "sleep"]:
            return {"valid": False, "error": f"Invalid action type for doctor: {action_type}"}
        if action_type in ["protect", "kill_potion"] and not target:
            return {"valid": False, "error": f"Target is required for {action_type} action"}
    
    elif role == "villager":
        if action_type not in ["sleep"]:
            return {"valid": False, "error": f"Invalid action type for villager: {action_type}"}
    
    else:
        return {"valid": False, "error": f"Unknown role: {role}"}
    
    return {"valid": True, "error": None}


def format_night_action_response(action_data: Dict[str, Any], role: str) -> str:
    """Format a night action for display in game logs."""
    action_type = action_data.get("action_type")
    target = action_data.get("target")
    reasoning = action_data.get("reasoning", "")
    
    if action_type == "kill":
        return f"Wolf {action_data.get('player_id', 'Unknown')} chose to kill {target}. Reasoning: {reasoning}"
    elif action_type == "inspect":
        return f"Detective {action_data.get('player_id', 'Unknown')} inspected {target}. Reasoning: {reasoning}"
    elif action_type == "protect":
        return f"Doctor {action_data.get('player_id', 'Unknown')} protected {target}. Reasoning: {reasoning}"
    elif action_type == "kill_potion":
        return f"Doctor {action_data.get('player_id', 'Unknown')} used death potion on {target}. Reasoning: {reasoning}"
    elif action_type == "wolf_chat":
        message = action_data.get("message", "")
        return f"Wolf {action_data.get('player_id', 'Unknown')} said: '{message}'"
    elif action_type == "sleep":
        return f"{role.title()} {action_data.get('player_id', 'Unknown')} has no night actions (sleeping)"
    else:
        return f"Unknown action: {action_type}"

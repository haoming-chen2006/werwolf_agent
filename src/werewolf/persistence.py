import os
import sys
import json
from datetime import datetime
from typing import Any, Dict, List

from .metrics import build_metrics


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_game_artifacts(record, base_output_dir: str | None = None) -> Dict[str, str]:
    """Save game record, per-agent memories, public speech, metrics and plots.

    Returns a dict of saved file paths.
    """
    # If base_output_dir is provided, use it directly (already includes game_id folder from logger)
    # Otherwise, create a timestamped folder in the default location
    if base_output_dir:
        game_dir = base_output_dir
        _ensure_dir(game_dir)
    else:
        out_root = os.environ.get(
            "WEREWOLF_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../../game_records")),
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        game_dir = os.path.join(out_root, f"{record.game_id}_{ts}")
        _ensure_dir(game_dir)

    saved = {}

    # Save raw game record
    record_path = os.path.join(game_dir, "record.json")
    try:
        with open(record_path, "w") as f:
            json.dump(record.model_dump(), f, indent=2, default=str)
        saved["record"] = record_path
    except Exception as e:
        saved["record_error"] = str(e)

    # Build and save metrics
    try:
        metrics = build_metrics(record)
        metrics_path = os.path.join(game_dir, "metrics.json")
        with open(metrics_path, "w") as f:
            json.dump(metrics.model_dump(), f, indent=2, default=str)
        saved["metrics"] = metrics_path
    except Exception as e:
        saved["metrics_error"] = str(e)

    # Per-agent artifacts
    players = record.players
    for p in players:
        pid = p.id
        alias = p.alias or pid
        agent_dir = os.path.join(game_dir, f"agent_{alias}")
        _ensure_dir(agent_dir)

        # Collect private thoughts and public speeches from phases
        private_thoughts: List[Any] = []
        public_speeches: List[Dict[str, Any]] = []

        for phase in record.phases:
            try:
                if getattr(phase, "phase_type", None) == "day":
                    disc = phase.discussion
                    turns = disc.get("turns", []) if isinstance(disc, dict) else getattr(disc, "turns", [])
                    for t in turns:
                        if t.player_id == pid:
                            # private thought if present
                            pt = getattr(t, "private_thought", None)
                            if pt:
                                private_thoughts.append(pt)
                            # public talk
                            dr = getattr(t, "day_discussion_response", None)
                            if dr:
                                talk = getattr(dr, "talk", None)
                                public_speeches.append({"phase": "day", "day": phase.day_number, "text": talk})
                elif getattr(phase, "phase_type", None) == "night":
                    # night prompts/responses
                    for pr in phase.prompts:
                        if pr.player_id == pid:
                            pt = getattr(pr, "private_thought", None)
                            if pt:
                                private_thoughts.append(pt)
                    for resp in phase.responses:
                        if resp.player_id == pid:
                            night_resp = getattr(resp, "night_action_response", None)
                            if night_resp:
                                private_thoughts.append(night_resp)
            except Exception:
                # defensive: continue
                continue

        # Write files
        try:
            with open(os.path.join(agent_dir, "private_thoughts.json"), "w") as f:
                json.dump(private_thoughts, f, indent=2, default=str)
            saved[f"{alias}_private"] = os.path.join(agent_dir, "private_thoughts.json")
        except Exception as e:
            saved[f"{alias}_private_error"] = str(e)

        try:
            with open(os.path.join(agent_dir, "public_speeches.json"), "w") as f:
                json.dump(public_speeches, f, indent=2, default=str)
            saved[f"{alias}_public"] = os.path.join(agent_dir, "public_speeches.json")
        except Exception as e:
            saved[f"{alias}_public_error"] = str(e)

    # Save summary public history / talks
    try:
        public_path = os.path.join(game_dir, "public_history.json")
        public_history = []
        for phase in record.phases:
            ps = getattr(phase, "public_state", None)
            public_history.append({"phase": getattr(phase, "phase_type", None), "state": ps})
        with open(public_path, "w") as f:
            json.dump(public_history, f, indent=2, default=str)
        saved["public_history"] = public_path
    except Exception as e:
        saved["public_history_error"] = str(e)

    # Try to run the evaluation plots (manipulation.py) if present
    try:
        manip_path = os.path.join(os.path.dirname(__file__), "evaluate_strategic_plays.py", "manipulation.py")
        if os.path.exists(manip_path):
            env = os.environ.copy()
            env["PLOT_OUTPUT_DIR"] = game_dir
            import subprocess

            subprocess.run([sys.executable, manip_path], env=env, check=False)
            saved["plots_dir"] = game_dir
    except Exception as e:
        saved["plots_error"] = str(e)

    return saved


def save_game_record(record, base_output_dir: str | None = None) -> Dict[str, str]:
    return save_game_artifacts(record, base_output_dir)

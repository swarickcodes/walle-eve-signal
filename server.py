import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.environment import POMDPEnvironment
from src.agent import WallEAgent
from src.visualizer import TerminalVisualizer

app = FastAPI(title="WALL-E & EVE Mission Control Backend")

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------
# PYDANTIC SCHEMAS
# ---------------------------------------------------------
class CostConfig(BaseModel):
    move: int
    scan: int
    recharge_rate: int

class ClueConfig(BaseModel):
    pos: List[int]
    type: str
    dist_to_eve: float
    noise_sigma: float

class InitialSignal(BaseModel):
    direction: str
    strength: float

class GroundTruthConfig(BaseModel):
    eve_pos: List[int]
    clues: List[ClueConfig]

class MissionConfig(BaseModel):
    grid_size: List[int]
    start_pos: List[int]
    battery_capacity: int
    costs: CostConfig
    solar_stations: List[List[int]]
    obstacles: List[List[int]]
    initial_signal: InitialSignal
    ground_truth: GroundTruthConfig


global_env: Optional[POMDPEnvironment] = None
global_agent: Optional[WallEAgent] = None
global_traces: List[Dict[str, Any]] = []


def load_config_file(preset: str) -> dict:
    file_map = {
        "default": "config/mission_default.json",
        "step10_deadlock": "config/mission_step10.json",
        "desert": "config/mission_desert.json",
        "walled_target": "config/mission_walled.json"
    }
    path = BASE_DIR / file_map.get(preset, "config/mission_default.json")
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    
    return {
        "grid_size": [10, 10], 
        "start_pos": [0, 0], 
        "battery_capacity": 100,
        "costs": {"move": 2, "scan": 5, "recharge_rate": 25},
        "solar_stations": [[0, 0], [5, 5]], 
        "obstacles": [[2, 2], [2, 3], [6, 7]],
        "initial_signal": {"direction": "SE", "strength": 0.4},
        "ground_truth": {
            "eve_pos": [8, 9],
            "clues": [
                {"pos": [1, 2], "type": "radio_ping", "dist_to_eve": 9.89, "noise_sigma": 0.8},
                {"pos": [4, 5], "type": "energy_residue", "dist_to_eve": 5.65, "noise_sigma": 0.5},
                {"pos": [7, 8], "type": "direct_beacon", "dist_to_eve": 1.41, "noise_sigma": 0.2}
            ]
        }
    }


# ---------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------
@app.post("/api/load-preset")
def load_preset(preset: str):
    cfg_data = load_config_file(preset)
    return initialize_mission(MissionConfig(**cfg_data))


@app.get("/api/config")
def get_current_config():
    if not global_env:
        return load_config_file("default")
    return global_env.cfg


@app.post("/api/init")
def initialize_mission(config: MissionConfig):
    global global_env, global_agent, global_traces
    global_env = POMDPEnvironment(config.dict())
    global_agent = WallEAgent(global_env)

    global_env.reveal_next_nearest_clue(global_env.agent_pos)
    global_traces = []

    eve_pos_list = [int(global_env.eve_pos[0]), int(global_env.eve_pos[1])]

    return {
        "grid_size": global_env.cfg["grid_size"],
        "agent_pos": [int(global_env.agent_pos[0]), int(global_env.agent_pos[1])],
        "battery": global_env.battery,
        "done": False,
        "obstacles": [[int(o[0]), int(o[1])] for o in global_env.obstacles],
        "solar_stations": [[int(s[0]), int(s[1])] for s in global_env.solar_stations],
        "clues": [{"pos": [int(k[0]), int(k[1])], **v} for k, v in global_env.visible_clues.items()],
        "eve_pos": eve_pos_list,
        "eve_visible": False,
        "target_locked": False,
        "initial_logs": []
    }


@app.post("/api/step")
def step_mission():
    global global_env, global_agent, global_traces
    if not global_env or not global_agent:
        raise HTTPException(status_code=400, detail="Initialize the environment first")

    eve_pos_list = [int(global_env.eve_pos[0]), int(global_env.eve_pos[1])]

    if global_env.done:
        success = (tuple(global_env.agent_pos) == tuple(global_env.eve_pos))
        return {
            "done": True,
            "success": success,
            "show_report": success,
            "report_markdown": TerminalVisualizer.format_markdown_report(global_env, global_agent, global_traces) if success else None,
            "battery": global_env.battery,
            "battery_max": global_env.cfg["battery_capacity"],
            "agent_pos": [int(global_env.agent_pos[0]), int(global_env.agent_pos[1])],
            "eve_pos": eve_pos_list,
            "eve_visible": True,
            "clues": [{"pos": [int(k[0]), int(k[1])], **v} for k, v in global_env.visible_clues.items()]
        }

    global_env.step_count += 1
    action, target, reasoning = global_agent.decide_next_action()
    obs = {}

    if action == "HALT":
        global_env.done = True
        trace = {
            "step": global_env.step_count, 
            "position": [int(global_env.agent_pos[0]), int(global_env.agent_pos[1])],
            "battery": global_env.battery, 
            "action": "HALT", 
            "observation": {}, 
            "reasoning": reasoning
        }
        global_traces.append(trace)
        return {
            "done": True, 
            "success": False, 
            "impossible": True, 
            "abort_reason": global_agent.abort_reason,
            "action": "HALT", 
            "battery": global_env.battery, 
            "battery_max": global_env.cfg["battery_capacity"],
            "agent_pos": [int(global_env.agent_pos[0]), int(global_env.agent_pos[1])], 
            "eve_pos": eve_pos_list,
            "eve_visible": False,
            "trace_entry": trace,
            "clues": [{"pos": [int(k[0]), int(k[1])], **v} for k, v in global_env.visible_clues.items()]
        }

    # Action execution
    if action == "MOVE" and target:
        global_env.battery -= global_env.cfg["costs"]["move"]
        global_env.agent_pos = (int(target[0]), int(target[1]))
        obs["status"] = f"Moved to {target}"

    elif action == "SCAN":
        global_env.battery -= global_env.cfg["costs"]["scan"]
        curr_pos = (int(global_env.agent_pos[0]), int(global_env.agent_pos[1]))

        if curr_pos in global_env.visible_clues:
            clue = global_env.visible_clues[curr_pos]
            obs = {
                "clue_found": True,
                "type": clue["type"],
                "dist_to_eve": clue["dist_to_eve"],
                "noise_sigma": clue["noise_sigma"],
            }
            global_agent.process_scan_observation(curr_pos, obs)
            revealed = global_env.reveal_next_nearest_clue(curr_pos)
            if revealed:
                reasoning += f" -> Sensor unlocked landmark at {revealed}."
        else:
            obs = {"clue_found": False}

    elif action == "RECHARGE":
        global_env.battery = min(global_env.cfg["battery_capacity"], global_env.battery + global_env.cfg["costs"]["recharge_rate"])
        obs["status"] = f"Charges to: {global_env.battery}"

    # Evaluate physical arrival
    success = (tuple(global_env.agent_pos) == tuple(global_env.eve_pos))
    if success or global_env.battery <= 0:
        global_env.done = True

    # Check if all clues have been scanned
    scanned_norm = {(int(p[0]), int(p[1])) for p in global_agent.scanned_tiles}
    clues_norm = {(int(k[0]), int(k[1])) for k in global_env.hidden_clues.keys()}
    all_clues_scanned = (len(scanned_norm & clues_norm) >= len(clues_norm))

    # Trigger visibility once all clues are scanned, target is locked, or docked
    eve_visible = (
        all_clues_scanned or 
        (global_agent.inference_confidence >= 0.50 and global_agent.inferred_eve_pos is not None) or
        ("Target locked" in reasoning) or 
        success
    )

    display_eve_pos = [int(global_agent.inferred_eve_pos[0]), int(global_agent.inferred_eve_pos[1])] if global_agent.inferred_eve_pos else eve_pos_list

    trace = {
        "step": global_env.step_count, 
        "position": [int(global_env.agent_pos[0]), int(global_env.agent_pos[1])],
        "battery": global_env.battery, 
        "action": action, 
        "observation": obs, 
        "reasoning": reasoning
    }
    global_traces.append(trace)

    final_report = None
    if success:
        final_report = TerminalVisualizer.format_markdown_report(global_env, global_agent, global_traces)

    return {
        "done": global_env.done,
        "success": success,
        "show_report": success,
        "report_markdown": final_report,
        "target_locked": eve_visible,
        "target_confidence": round(global_agent.inference_confidence * 100, 1),
        "triangulated_pos": display_eve_pos,
        "eve_pos": display_eve_pos,
        "eve_visible": eve_visible,
        "impossible": False,
        "action": action,
        "target": list(target) if target else None,
        "reason": reasoning,
        "observation": obs,
        "battery": global_env.battery,
        "battery_max": global_env.cfg["battery_capacity"],
        "agent_pos": [int(global_env.agent_pos[0]), int(global_env.agent_pos[1])],
        "trace_entry": trace,
        "clues": [{"pos": [int(k[0]), int(k[1])], **v} for k, v in global_env.visible_clues.items()]
    }


@app.get("/api/report")
def generate_report():
    if not global_env or not global_agent:
        return {"report_markdown": "No mission initialized."}
    report_text = TerminalVisualizer.format_markdown_report(global_env, global_agent, global_traces)
    return {"report_markdown": report_text}


@app.get("/eve-image")
def get_eve_image():
    candidates = [
        BASE_DIR / "EVE.jpg",
        BASE_DIR / "EVE.jpeg",
        BASE_DIR / "EVE.png",
        BASE_DIR / "EVE.webp",
        BASE_DIR / "eve.jpg",
        BASE_DIR / "eve.jpeg",
        BASE_DIR / "eve.png",
        BASE_DIR / "eve.webp",
        BASE_DIR / "assets" / "EVE.jpg",
        BASE_DIR / "assets" / "EVE.webp",
    ]
    for p in candidates:
        if p.exists():
            suffix = p.suffix.lower()
            media = "image/jpeg" if suffix in [".jpg", ".jpeg"] else ("image/png" if suffix == ".png" else "image/webp")
            return FileResponse(p, media_type=media)
    raise HTTPException(status_code=404, detail="EVE image file not found on disk")


@app.get("/")
def read_root():
    return FileResponse(BASE_DIR / "index.html")
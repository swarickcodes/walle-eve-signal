import sys
import json
import math
from pathlib import Path
from src.environment import POMDPEnvironment
from src.agent import WallEAgent
from src.visualizer import TerminalVisualizer

def run_simulation(config_path: str):
    with open(config_path, "r") as f:
        cfg = json.load(f)

    env = POMDPEnvironment(cfg)
    agent = WallEAgent(env)
    env.reveal_next_nearest_clue(env.agent_pos)
    traces = []

    print(f"--- STARTING SIMULATION [{config_path}] ---")
    while not env.done:
        env.step_count += 1
        action, target, reasoning = agent.decide_next_action()
        obs = {}

        if action == "HALT":
            env.done = True
            traces.append({"step": env.step_count, "position": list(env.agent_pos), "battery": env.battery, "action": "HALT", "reasoning": reasoning})
            break

        if action == "MOVE" and target:
            env.battery -= env.cfg["costs"]["move"]
            env.agent_pos = target
        elif action == "SCAN":
            env.battery -= env.cfg["costs"]["scan"]
            if env.agent_pos in env.visible_clues:
                env.reveal_next_nearest_clue(env.agent_pos)
        elif action == "RECHARGE":
            env.battery = min(env.cfg["battery_capacity"], env.battery + env.cfg["costs"]["recharge_rate"])

        if env.agent_pos == env.eve_pos or env.battery <= 0:
            env.done = True

        traces.append({
            "step": env.step_count,
            "position": list(env.agent_pos),
            "battery": env.battery,
            "action": action,
            "reasoning": reasoning
        })

    report = TerminalVisualizer.format_markdown_report(env, agent, traces)
    print("\n" + report)

    out_file = Path("reports") / "latest_run.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report)
    print(f"\nReport written to {out_file}")

if __name__ == "__main__":
    cfg_file = sys.argv[1] if len(sys.argv) > 1 else "config/mission_default.json"
    run_simulation(cfg_file)
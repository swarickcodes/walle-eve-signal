from typing import List, Dict, Any

class TerminalVisualizer:
    @staticmethod
    def format_markdown_report(env, agent, traces: List[Dict[str, Any]]) -> str:
        success = (env.agent_pos == env.eve_pos)
        status_msg = "SUCCESS (Docked with EVE!)" if success else "IN PROGRESS"
        if agent.is_impossible:
            status_msg = f"ABORTED / IMPOSSIBLE: {agent.abort_reason}"
        elif env.battery <= 0:
            status_msg = "FAILED (Out of battery)"

        clues_count = len(agent.scanned_tiles & set(env.hidden_clues.keys()))
        triangulated = list(agent.inferred_eve_pos) if agent.inferred_eve_pos else "N/A"
        confidence = round(agent.inference_confidence * 100, 1)

        lines = [
            "# WALL-E Autonomous Reconnaissance Report",
            "=========================================================",
            f"- **Total Steps Elapsed**: {env.step_count}",
            f"- **Simulation Verdict**: {status_msg}",
            f"- **Final Position**: {list(env.agent_pos)}",
            f"- **Triangulated Target**: {triangulated} ({confidence}% Confidence)",
            f"- **Scanned Clues**: {clues_count} of {len(env.hidden_clues)} total clues",
            f"- **Battery Reserve**: {env.battery} / {env.cfg['battery_capacity']}\n",
            "## CHRONOLOGY LOG SUMMARIES"
        ]
        for t in traces:
            lines.append(f"- Step {t['step']} pos {t['position']} -> {t['action']}: {t['reasoning']}")
        return "\n".join(lines)
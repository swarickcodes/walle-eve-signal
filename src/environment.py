import math
from typing import Optional, Dict, Any

class POMDPEnvironment:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.width = cfg["grid_size"][0]
        self.height = cfg["grid_size"][1]
        self.agent_pos = tuple(cfg["start_pos"])
        self.battery = cfg["battery_capacity"]
        self.step_count = 0
        
        self.obstacles = {tuple(p) for p in cfg["obstacles"]}
        self.solar_stations = {tuple(p) for p in cfg["solar_stations"]}
        self.eve_pos = tuple(cfg["ground_truth"]["eve_pos"])
        
        self.hidden_clues = {}
        for c in cfg["ground_truth"]["clues"]:
            self.hidden_clues[tuple(c["pos"])] = {
                "type": c["type"],
                "dist_to_eve": c["dist_to_eve"],
                "noise_sigma": c["noise_sigma"]
            }
            
        self.visible_clues = {}
        self.done = False

    def reveal_next_nearest_clue(self, curr_pos: tuple) -> Optional[tuple]:
        unrevealed = [pos for pos in self.hidden_clues if pos not in self.visible_clues]
        if not unrevealed:
            return None
        unrevealed.sort(key=lambda p: math.hypot(p[0] - curr_pos[0], p[1] - curr_pos[1]))
        target = unrevealed[0]
        self.visible_clues[target] = self.hidden_clues[target]
        return target
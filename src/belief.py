import math
from typing import Tuple, Dict, Any

class BeliefTracker:
    def __init__(self, width: int, height: int, initial_signal: Dict[str, Any]):
        self.width = width
        self.height = height
        self.grid = [[1.0 for _ in range(height)] for _ in range(width)]

        direction = initial_signal.get("direction", "SE").upper()
        strength = float(initial_signal.get("strength", 0.3))

        dir_angles = {
            "E": 0.0,
            "SE": math.pi / 4.0,
            "S": math.pi / 2.0,
            "SW": 3.0 * math.pi / 4.0,
            "W": math.pi,
            "NW": -3.0 * math.pi / 4.0,
            "N": -math.pi / 2.0,
            "NE": -math.pi / 4.0,
        }
        target_angle = dir_angles.get(direction, math.pi / 4.0)

        for x in range(width):
            for y in range(height):
                if x == 0 and y == 0:
                    continue
                cell_angle = math.atan2(x, y)
                angle_diff = cell_angle - target_angle
                alignment = math.cos(angle_diff)
                self.grid[x][y] += strength * alignment

        self._normalize()

    def _normalize(self):
        total = sum(self.grid[x][y] for x in range(self.width) for y in range(self.height))
        if total > 0:
            for x in range(self.width):
                for y in range(self.height):
                    self.belief_val = self.grid[x][y] / total
                    self.grid[x][y] = self.belief_val

    def update_from_observation(self, scan_pos: tuple, dist_reading: float, sigma: float):
        cx, cy = scan_pos
        variance = 2.0 * (sigma ** 2)

        for x in range(self.width):
            for y in range(self.height):
                d = math.hypot(x - cx, y - cy)
                diff = d - dist_reading
                likelihood = math.exp(-(diff * diff) / variance)
                self.grid[x][y] *= likelihood

        self._normalize()

    def get_highest_probability_target(self) -> Tuple[tuple, float]:
        best_coord = (0, 0)
        max_prob = -1.0
        for x in range(self.width):
            for y in range(self.height):
                if self.grid[x][y] > max_prob:
                    max_prob = self.grid[x][y]
                    best_coord = (x, y)
        return best_coord, max_prob
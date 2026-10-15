from collections import deque
from typing import List, Tuple, Optional, Dict, Any
from .environment import POMDPEnvironment
from .belief import BeliefTracker

class WallEAgent:
    def __init__(self, env: POMDPEnvironment):
        self.env = env
        self.visited = {env.agent_pos}
        self.scanned_tiles = set()
        self.mode = "EXPLORE"

        initial_sig = env.cfg.get("initial_signal", {"direction": "SE", "strength": 0.3})
        self.belief = BeliefTracker(env.width, env.height, initial_sig)

        self.inferred_eve_pos: Optional[tuple] = None
        self.inference_confidence: float = 0.0

        self.last_charge_station = None
        self.consecutive_same_station_charges = 0
        self.is_impossible = False
        self.abort_reason = ""

    def find_path(self, start: tuple, goal: tuple) -> List[tuple]:
        if start == goal:
            return [start]
        queue = deque([[start]])
        seen = {start}
        while queue:
            path = queue.popleft()
            curr = path[-1]
            if curr == goal:
                return path
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nxt = (curr[0] + dx, curr[1] + dy)
                if (0 <= nxt[0] < self.env.width and 0 <= nxt[1] < self.env.height
                        and nxt not in self.env.obstacles and nxt not in seen):
                    seen.add(nxt)
                    queue.append(path + [nxt])
        return []

    def get_nearest_solar_station(self, curr: tuple) -> Tuple[Optional[tuple], Optional[List[tuple]]]:
        best_solar = None
        min_path = None
        for s in self.env.solar_stations:
            p = self.find_path(curr, s)
            if p and (min_path is None or len(p) < len(min_path)):
                min_path = p
                best_solar = s
        return best_solar, min_path

    def process_scan_observation(self, curr_pos: tuple, observation: Dict[str, Any]):
        if observation.get("clue_found"):
            dist = observation["dist_to_eve"]
            sigma = observation["noise_sigma"]
            self.belief.update_from_observation(curr_pos, dist, sigma)
            best_pos, conf = self.belief.get_highest_probability_target()
            self.inferred_eve_pos = best_pos
            self.inference_confidence = conf

    def decide_next_action(self) -> Tuple[str, Optional[tuple], str]:
        curr = self.env.agent_pos
        self.visited.add(curr)

        if self.is_impossible:
            return "HALT", None, f"MISSION NOT POSSIBLE: {self.abort_reason}"

        nearest_solar, path_to_solar = self.get_nearest_solar_station(curr)
        move_cost = self.env.cfg["costs"]["move"]
        battery_cap = self.env.cfg["battery_capacity"]

        dist_to_solar = (len(path_to_solar) - 1) if path_to_solar else 999
        return_cost = dist_to_solar * move_cost
        safety_threshold = return_cost + (move_cost * 2)

        # 1. Hysteresis Retreat & Recharge
        if self.mode == "EXPLORE" and self.env.battery <= safety_threshold:
            self.mode = "RETREAT_AND_RECHARGE"

        if self.mode == "RETREAT_AND_RECHARGE" and self.env.battery >= (battery_cap * 0.95):
            self.mode = "EXPLORE"

        if self.mode == "RETREAT_AND_RECHARGE":
            if curr == nearest_solar:
                if self.env.battery < battery_cap:
                    return "RECHARGE", None, f"Refueling battery arrays ({self.env.battery}/{battery_cap})"
            else:
                if path_to_solar and len(path_to_solar) > 1:
                    return "MOVE", path_to_solar[1], f"Battery low ({self.env.battery}); returning to solar station {nearest_solar}"
                else:
                    self.is_impossible = True
                    self.abort_reason = "No path to any solar array available."
                    return "HALT", None, self.abort_reason

        # 2. Clue Scan: If at an unvisited revealed clue, scan it
        if curr in self.env.visible_clues and curr not in self.scanned_tiles:
            self.scanned_tiles.add(curr)
            return "SCAN", None, f"Scanning clue landmark at {curr}"

        # 3. Target Intercept: Either high Bayesian confidence OR all clues scanned
        all_clues_scanned = (len(self.scanned_tiles) >= len(self.env.hidden_clues))
        target_discovered = (self.inference_confidence >= 0.70) or all_clues_scanned

        if target_discovered and self.inferred_eve_pos:
            # If already at EVE's position, we are docked
            if curr == self.inferred_eve_pos:
                return "SCAN", None, f"Docked with EVE at {curr}"

            path_to_target = self.find_path(curr, self.inferred_eve_pos)
            if path_to_target and len(path_to_target) > 1:
                cost_to_target = (len(path_to_target) - 1) * move_cost
                if cost_to_target <= self.env.battery:
                    next_step = path_to_target[1]
                    return "MOVE", next_step, (
                        f"Target locked at {self.inferred_eve_pos} "
                        f"({round(self.inference_confidence * 100, 1)}% confidence); moving to rendezvous"
                    )
                else:
                    if curr != nearest_solar and path_to_solar and len(path_to_solar) > 1:
                        self.mode = "RETREAT_AND_RECHARGE"
                        return "MOVE", path_to_solar[1], f"Recharging before intercept; moving to {nearest_solar}"
                    elif curr == nearest_solar and self.env.battery < battery_cap:
                        return "RECHARGE", None, f"Charging up for intercept ({self.env.battery}/{battery_cap})"

        # 4. Advance to Next Clue Landmark
        unvisited_clues = [c for c in self.env.visible_clues if c not in self.scanned_tiles]
        if unvisited_clues:
            clue_candidates = []
            for c in unvisited_clues:
                p = self.find_path(curr, c)
                if p and len(p) > 1:
                    clue_candidates.append((len(p), c, p))

            if clue_candidates:
                clue_candidates.sort(key=lambda x: x[0])
                _, target_clue, path_to_clue = clue_candidates[0]

                steps_to_clue = len(path_to_clue) - 1
                cost_to_reach_clue = steps_to_clue * move_cost

                clue_solar, p_clue_to_solar = self.get_nearest_solar_station(target_clue)
                steps_clue_to_solar = (len(p_clue_to_solar) - 1) if p_clue_to_solar else 999
                cost_retreat_from_clue = steps_clue_to_solar * move_cost
                total_energy_required = cost_to_reach_clue + cost_retreat_from_clue + (move_cost * 2)

                if self.env.battery >= total_energy_required:
                    return "MOVE", path_to_clue[1], f"Advancing to clue landmark at {target_clue} (Energy: {self.env.battery}/{total_energy_required})"

                if curr in self.env.solar_stations and self.env.battery < battery_cap:
                    return "RECHARGE", None, f"Topping up power before advancing ({self.env.battery}/{battery_cap})"

                candidate_relays = []
                for s in self.env.solar_stations:
                    if s == curr:
                        continue
                    p_to_s = self.find_path(curr, s)
                    if p_to_s and len(p_to_s) > 1:
                        cost_hop = (len(p_to_s) - 1) * move_cost
                        if cost_hop <= self.env.battery:
                            p_from_s_to_clue = self.find_path(s, target_clue)
                            dist_to_clue_from_s = len(p_from_s_to_clue) if p_from_s_to_clue else 999
                            candidate_relays.append((dist_to_clue_from_s, p_to_s, s))

                if candidate_relays:
                    candidate_relays.sort(key=lambda x: x[0])
                    best_dist_from_relay, path_to_relay, best_relay = candidate_relays[0]
                    curr_dist_to_clue = len(path_to_clue)

                    if best_dist_from_relay < curr_dist_to_clue:
                        return "MOVE", path_to_relay[1], f"Clue out of range; island-hopping to solar relay {best_relay}"

                if curr != nearest_solar and path_to_solar and len(path_to_solar) > 1:
                    self.mode = "RETREAT_AND_RECHARGE"
                    return "MOVE", path_to_solar[1], f"Diverting to nearest solar station at {nearest_solar}"

        # 5. Fallback Sweep
        if curr not in self.scanned_tiles:
            self.scanned_tiles.add(curr)
            return "SCAN", None, "Ambient sensor sweep at current location"

        # 6. Deadlock Check
        if curr in self.env.solar_stations and self.env.battery >= (battery_cap * 0.95):
            self.is_impossible = True
            self.abort_reason = "Mission Impossible: Objectives unreachable across operating radius."
            return "HALT", None, self.abort_reason

        return "SCAN", None, "Standby sensor sweeps"
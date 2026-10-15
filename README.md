# WALL-E & EVE: Autonomous POMDP Search & Reconnaissance

An autonomous navigation system and simulation dashboard built with **FastAPI** and a lightweight interactive frontend. The project models an autonomous agent (WALL-E) operating under partial observability (POMDP) to locate a target (EVE) across a grid landscape using directional priors, noisy sensor readings, breadcrumb clue landmark scanning, and energy-constrained battery management.

---

## Project Overview

WALL-E must locate and rendezvous with EVE while adhering to strict operational constraints:
- **Partially Observable Markov Decision Process (POMDP)**: WALL-E does not possess access to ground-truth coordinates. Target localization is driven purely by Bayesian belief updates derived from noisy distance measurements and directional signals.
- **Backend-Driven Architecture**: All decision math, pathfinding (BFS), battery depletion/recharge logic, and visibility determinations reside strictly in the Python backend. The frontend serves solely as a presentation layer.
- **Energy & Survival Management**: The agent monitors battery limits, balances path costs, plans recharge retreats to solar stations, and avoids infinite-loop scenarios or battery depletion.
- **Landmark Sequencing & Discovery**: As sequential clue landmarks are reached and scanned, Bayesian confidence rings converge. Once localization completes, EVE's position is unlocked, and WALL-E navigates directly to execute rendezvous docking.

---

## JSON Config Format Example

{
  "grid_size": [10, 10],
  "start_pos": [0, 0],
  "battery_capacity": 100,
  "costs": {
    "move": 2,
    "scan": 5,
    "recharge_rate": 25
  },
  "solar_stations": [
    [0, 0],
    [5, 5]
  ],
  "obstacles": [
    [2, 2],
    [2, 3],
    [6, 7]
  ],
  "initial_signal": {
    "direction": "SE",
    "strength": 0.4
  },
  "ground_truth": {
    "eve_pos": [8, 9],
    "clues": [
      {
        "pos": [1, 2],
        "type": "radio_ping",
        "dist_to_eve": 9.89,
        "noise_sigma": 0.8
      },
      {
        "pos": [4, 5],
        "type": "energy_residue",
        "dist_to_eve": 5.65,
        "noise_sigma": 0.5
      },
      {
        "pos": [7, 8],
        "type": "direct_beacon",
        "dist_to_eve": 1.41,
        "noise_sigma": 0.2
      }
    ]
  }
}


## Directory Structure

```text
walle-eve-signal/
├── config/                 # Mission configuration presets (JSON)
├── reports/                # Output evaluation and telemetry logs
├── src/
│   ├── __init__.py
│   ├── agent.py            # WALL-E decision policy, pathfinding & logic
│   ├── belief.py           # Bayesian belief grid & Gaussian updates
│   ├── environment.py      # POMDP environment state & ground-truth validation
│   ├── run.py              # CLI evaluation and batch execution
│   └── visualizer.py       # Terminal report and telemetry visualizer
├── EVE.png / EVE.jpg       # Target asset graphic
├── index.html              # Pure presentation web dashboard
├── requirements.txt        # Python package dependencies
├── run.bat                 # One-click startup script for Windows
├── server.py               # FastAPI backend & simulation endpoints
└── README.md               # Documentation & setup instructions

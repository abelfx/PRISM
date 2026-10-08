"""Seeded, explicitly hypothetical stochastic execution of OpenPsi plans.

Only plans previously validated by the fresh PeTTa runner can succeed here.
Every action independently succeeds with a declared probability; failures
end the episode without replanning. This is *not* the repository's real action
executor or an estimate of real-world action reliability.
"""

import argparse
import json
from pathlib import Path
import random


def evaluate(source: dict, probabilities: tuple[float, ...], episodes: int, seed: int) -> dict:
    if episodes <= 0 or not probabilities or any(not 0 <= p <= 1 for p in probabilities):
        raise ValueError("Use positive episodes and probabilities in [0, 1]")
    goals = source["protocol"]["same_goals"]
    by_key = {(item["goal"], item["mode"]): item for item in source["observations"]}
    modes = ("V1", "V2", "PRISM")
    for goal in goals:
        for mode in modes:
            if (goal, mode) not in by_key or "cold" not in by_key[goal, mode]:
                raise ValueError(f"Missing fresh PeTTa plan for {goal}/{mode}")
    results = {}
    for probability in probabilities:
        case = {}
        for mode in modes:
            case[mode] = {"completed": 0, "trials": len(goals) * episodes}
        for goal_index, goal in enumerate(goals):
            for episode in range(episodes):
                # Common random numbers make paired comparisons deterministic.
                rng = random.Random(seed + goal_index * 1_000_003 + episode)
                draws = [rng.random() for _ in range(15)]
                for mode in modes:
                    plan = by_key[goal, mode]["cold"]
                    valid = plan["outcome"] == "Success"
                    count = len(plan["actions"])
                    if count != plan["steps"]:
                        raise ValueError(f"Inconsistent plan length for {goal}/{mode}")
                    if valid and all(draw < probability for draw in draws[:count]):
                        case[mode]["completed"] += 1
        for mode in modes:
            count = case[mode]["completed"]
            trials = case[mode]["trials"]
            case[mode]["completion_rate"] = count / trials
            case[mode]["mean_demand_after"] = 0.1 + 0.45 * count / trials
            case[mode]["analytic_expected_rate"] = sum(
                probability ** by_key[goal, mode]["cold"]["steps"]
                for goal in goals
                if by_key[goal, mode]["cold"]["outcome"] == "Success"
            ) / len(goals)
        results[str(probability)] = case
    return {
        "protocol": {
            "input": "fresh-process, PeTTa-replayed OpenPsi action plans",
            "goal_count": len(goals),
            "episodes_per_goal_per_mode": episodes,
            "seed": seed,
            "independent_per_action_success_probabilities": probabilities,
            "failure": "episode terminates; no replanning or side effects",
            "reward": "on completed route, competence demand 0.1 -> 0.55; otherwise 0.1",
            "warning": "hypothetical simulator, not actual OpenPsi action execution or calibrated action success",
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("benchmarks/results/reference/openpsi_fresh_eval.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261008)
    parser.add_argument("--probabilities", nargs="+", type=float, default=[1.0, 0.9, 0.7])
    args = parser.parse_args()
    source = json.loads(args.input.read_text())
    result = evaluate(source, tuple(args.probabilities), args.episodes, args.seed)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

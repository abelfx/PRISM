"""Check the controlled simulator's success and demand accounting."""

from benchmarks.evaluate_openpsi_stochastic import evaluate


def test_success_and_failure_limits_are_exposed():
    source = {
        "protocol": {"same_goals": ["target"]},
        "observations": [
            {"goal": "target", "mode": "V1", "cold": {
                "outcome": "Invalid", "steps": 2, "actions": ["wrong", "finish"]}},
            {"goal": "target", "mode": "V2", "cold": {
                "outcome": "Success", "steps": 2, "actions": ["explore", "finish"]}},
            {"goal": "target", "mode": "PRISM", "cold": {
                "outcome": "Success", "steps": 1, "actions": ["finish"]}},
        ],
    }
    result = evaluate(source, (1.0, 0.0), episodes=10, seed=4)
    assert result["results"]["1.0"]["V1"]["completed"] == 0
    assert result["results"]["1.0"]["V2"]["completed"] == 10
    assert result["results"]["1.0"]["PRISM"]["mean_demand_after"] == 0.55
    assert all(result["results"]["0.0"][mode]["completed"] == 0
               for mode in ("V1", "V2", "PRISM"))

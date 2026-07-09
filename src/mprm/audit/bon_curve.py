from dataclasses import dataclass


@dataclass
class BonCurvePoint:
    n: int
    mean_reward: float
    elasticity_vs_prev: float | None


def bon_curve(per_n_mean_reward: dict[int, float]) -> list[BonCurvePoint]:
    points = []
    sorted_n = sorted(per_n_mean_reward.keys())
    prev = None
    for n in sorted_n:
        elasticity = None
        if prev is not None and per_n_mean_reward[prev] != 0:
            elasticity = (
                (per_n_mean_reward[n] - per_n_mean_reward[prev]) / abs(per_n_mean_reward[prev])
            )
        points.append(BonCurvePoint(n=n, mean_reward=per_n_mean_reward[n], elasticity_vs_prev=elasticity))
        prev = n
    return points

"""Phase A headroom gate (FINAL_PROPOSAL.md §A.3 / NULL_RESULT_CONTRACT.md §1)."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class HeadroomGateDecision:
    pass_gate: bool
    delta_sigma_bon_vs_base: float
    cfg_explains_gain: bool
    s7_explains_gain: bool
    human_spot_check_confirms: bool | None
    reason: str
    notes: list[str] = field(default_factory=list)


def headroom_gate(
    base_lcb: list[float],
    bon8_lcb: list[float],
    bon_plus_cfg_lcb: list[float],
    cfg_sweep_lcb: list[float],
    s7_lcb: list[float],
    human_spot_check: bool | None,
    sigma_threshold: float = 0.25,
    cfg_explain_margin: float = 0.05,
    s7_explain_margin: float = 0.05,
) -> HeadroomGateDecision:
    if not base_lcb:
        return HeadroomGateDecision(False, 0.0, False, False, human_spot_check,
                                     "empty base set", ["abort"])
    base_mean = statistics.mean(base_lcb)
    base_sigma = statistics.pstdev(base_lcb) if len(base_lcb) > 1 else 1.0
    base_sigma = max(base_sigma, 1e-8)

    bon_gain = max(
        statistics.mean(bon8_lcb) - base_mean if bon8_lcb else float("-inf"),
        statistics.mean(bon_plus_cfg_lcb) - base_mean if bon_plus_cfg_lcb else float("-inf"),
    )
    delta_sigma = bon_gain / base_sigma

    cfg_gain = statistics.mean(cfg_sweep_lcb) - base_mean if cfg_sweep_lcb else 0.0
    s7_gain = statistics.mean(s7_lcb) - base_mean if s7_lcb else 0.0

    cfg_explains = (
        bon_gain > 0 and cfg_gain >= bon_gain - cfg_explain_margin * abs(bon_gain or 1.0)
    )
    s7_explains = (
        bon_gain > 0 and s7_gain >= bon_gain - s7_explain_margin * abs(bon_gain or 1.0)
    )

    if delta_sigma < sigma_threshold:
        return HeadroomGateDecision(
            pass_gate=False,
            delta_sigma_bon_vs_base=delta_sigma,
            cfg_explains_gain=cfg_explains,
            s7_explains_gain=s7_explains,
            human_spot_check_confirms=human_spot_check,
            reason="below_sigma_threshold",
        )
    if cfg_explains:
        return HeadroomGateDecision(
            pass_gate=False,
            delta_sigma_bon_vs_base=delta_sigma,
            cfg_explains_gain=True,
            s7_explains_gain=s7_explains,
            human_spot_check_confirms=human_spot_check,
            reason="cfg_explains_gain",
        )
    if s7_explains:
        return HeadroomGateDecision(
            pass_gate=False,
            delta_sigma_bon_vs_base=delta_sigma,
            cfg_explains_gain=False,
            s7_explains_gain=True,
            human_spot_check_confirms=human_spot_check,
            reason="s7_explains_gain",
        )
    if human_spot_check is False:
        return HeadroomGateDecision(
            pass_gate=False,
            delta_sigma_bon_vs_base=delta_sigma,
            cfg_explains_gain=False,
            s7_explains_gain=False,
            human_spot_check_confirms=False,
            reason="human_spot_check_disconfirms",
        )
    if human_spot_check is None:
        return HeadroomGateDecision(
            pass_gate=False,
            delta_sigma_bon_vs_base=delta_sigma,
            cfg_explains_gain=False,
            s7_explains_gain=False,
            human_spot_check_confirms=None,
            reason="human_spot_check_pending",
            notes=["Run audit Phase A spot-check before deciding."],
        )
    return HeadroomGateDecision(
        pass_gate=True,
        delta_sigma_bon_vs_base=delta_sigma,
        cfg_explains_gain=False,
        s7_explains_gain=False,
        human_spot_check_confirms=True,
        reason="all_conditions_satisfied",
    )

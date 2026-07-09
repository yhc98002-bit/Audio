# ICLR Reviewer-Risk Audit

Generated UTC: `2026-06-03T22:21:12Z`

| Risk | Current Evidence | Missing Evidence | Main-Claim Requirement |
|---|---|---|---|
| Is pruning too naive? | Raw ETP has strong reward retention; learned ETV is evaluated separately. | Human spot-check and failure-case examples remain useful. | Required for main claim: partly. |
| Is this just BoN-4? | ETP@50 reward fraction 0.9864 vs BoN-4 0.9823; verdict passes. | Need emphasize same-compute comparison in paper. | Required for main claim: yes. |
| Is evaluation circular? | Primary pruning uses robust/common reward; cross-axis evaluation after common-selected pruning is available (aesthetic_pq=0.9875; aesthetic_cu=0.9896; semantic_fit=0.8321; section_coherence=0.9922; lyric_intelligibility=0.6820 [EN-vocal n=282]) and separates selection from non-primary axes. | Human spot-check not yet launched. | Required for ICLR: likely. |
| Does it work beyond ACE-Step? | Current evidence is ACE-Step-only. | Cross-backbone validation absent by boundary. | Required for main claim: no if scope is ACE-Step. |
| Why is late sigma not trivial? | Schedules prune at 0.9/0.8/0.7 before final generation and report compute fractions. | Need visualize quality-vs-sigma retention. | Required for main claim: yes. |
| What does learned ETV add? | Learned ridge verifier is compared against raw ETP; if no improvement, raw ETP remains the method and ETV is analysis. | No GBDT/LambdaMART package available in current env. | Required: no, but helps novelty. |
| Does human listening support this? | Packet manifest prepared only; no crowdsourcing launched. | PI spot-check needed before paper claim. | Required for final paper: strongly recommended. |
| Why not RL? | C1 backend worked but common dev eval had no clear win; RL rescue stopped. | None for current inference-time paper. | Required: boundary explanation yes. |
| Failure cases / late bloomers? | False-negative and regret columns identify late-bloomer risk. | Need qualitative packet examples. | Required: yes for reviewer trust. |

## Boundary Note

This audit does not authorize Phase D, human crowdsourcing, pruning+RL, new RL training, reward-definition changes, or a canonical proposal rewrite.

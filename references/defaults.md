# Defaults and tie-breakers

Hard requirements and approved decisions take precedence; these are defaults, not universal bans.

- Prefer the smallest solution that meets today's actual requirements. Do not construct speculative frameworks, roles, or layers.
- Assign one authoritative owner to each behavior, business rule, or mutable state. Make contracts, dependency direction, and side effects explicit.
- Favor local reasoning: a maintainer should understand a change without reconstructing unrelated systems.
- Prefer straightforward concrete functions, data, and composition; add interfaces only for real boundaries or substitutions.
- Keep failures and resource lifecycles visible; validate at trust boundaries. Address safety and correctness, not just happy-path behavior.
- Prefer focused verification of changed behavior over broad ceremonial checklists.
- For brownfield work, preserve established compatible contracts and user-facing behavior. Baseline unrelated legacy problems; do not silently turn them into new standards or widen the task into a rewrite.
- Prefer reversible, conventional, easy-to-change choices when options otherwise meet requirements equally well.
- A choice deserves a new decision only if different answers could materially change required outcomes, contracts, ownership, compatibility, safety, performance, or user experience.
- Escalate indispensable product intent, authorization, and high-impact irreversible tradeoffs; adopt routine, well-supported defaults without repeated approval.

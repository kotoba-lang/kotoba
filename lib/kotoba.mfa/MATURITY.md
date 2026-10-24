# Maturity

**Level: R2 live adapter**

Implemented:
- MFA policy and result models.
- Required-factor set evaluation.
- Policy validation for required factors and phishing-resistant requirements.
- Factor shape validation.
- Datom emitters for policy and result records.
- MFA planner adapter boundary.
- Risk-based MFA planner implementation.
- Live risk signal policy engine wrapper.
- Factor preference ordering and explicit fallback-for policy.
- Runtime orchestration across factor providers.
- Missing-provider and provider-error normalization into failed factor results.
- Contract tests for success, invalid policy/factor rejection, phishing-resistant policy acceptance, planner payload mapping, risk-adaptive factor selection, preference ordering, fallback satisfaction, and provider orchestration.

Not yet R2:
- None.

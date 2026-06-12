# elv_battery_handling — hodoki L2 (R0 scaffold)

Li-ion SoH classification + lead-acid routing.
Per ADR-2605261215 §6 L2. R0 scaffold — `.solve()` raises until R1.

- **Murakumo node**: levi
- **Lexicon (output)**: `com.etzhayyim.hodoki.batteryHandlingRecord`
- **Constraints**: G7 thermal-safety SOP (no puncture / no short / containment enclosure); SoH ≥70% → hikari R2+ second-life; SoH <70% → cell-recycle Wave 2; lead-acid → kanayama Wave 3; G13 cross-actor invariant

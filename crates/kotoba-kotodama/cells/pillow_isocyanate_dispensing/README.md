# pillow_isocyanate_dispensing — makura L1b (R0 scaffold)

Closed-loop MDI / TDI dispensing + worker exposure log.
Per ADR-2605261115 §6 L1b. R0 scaffold — `.solve()` raises until R1.

- **Murakumo node**: naphtali
- **Lexicons (output)**: `com.etzhayyim.makura.foamBatchAttestation` (isocyanate section), `com.etzhayyim.makura.workerExposureRecord`
- **Constraints**: G6 (worker exposure ≤ 5 ppb MDI / ≤ 2 ppb TDI 8h TWA; MDI preferred); G10 (SBT-gated personnel)

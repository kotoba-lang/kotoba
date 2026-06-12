# moushibumi_voter_info — moushibumi (R0 scaffold)

serve NEUTRAL election-mechanics information (voting dates, 期日前/不在者投票
procedure, official 選挙公報 pointers) so a member can participate informed.

Per ADR-2605312400. R0 scaffold — `cell.py` raises at import time until R1.

- **Actor**: moushibumi (申文) — `did:web:moushibumi.etzhayyim.com`
- **Murakumo node (proposed)**: reuben
- **Gates**: G3 (公職選挙法 + political-neutrality — the critical gate) + G8 (non-fabrication)
- **Output**: read-side info only (no member-mutating Lexicon)
- **Ceiling**: INFO-ONLY — NO campaigning / canvassing (§138) / endorsement / ranking / vote-solicitation / GOTV / partisan steering; neutral official-source reference only (protects §1.12 / 1 SBT = 1 vote) · Murakumo-only (ADR-2605215000)

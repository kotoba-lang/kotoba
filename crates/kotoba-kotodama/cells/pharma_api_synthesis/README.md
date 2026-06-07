# pharma_api_synthesis — Pregel cell for API multi-step synthesis

Per **ADR-2605250515 §Decision 2** (3 化合物 synthesis route文献 reference).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **zebulun** (chemistry orchestration).

Synthesis route reference (perpetually off-patent open literature):

- **DSCG** (5 steps): resorcinol → 4,6-diacetylresorcinol → bis-epoxide → diethyl bis-chromone-2-carboxylate → DSCG · 2Na (Fisons 1965)
- **Naphazoline HCl** (3 steps): 1-naphthylacetonitrile → ethyl 1-naphthylacetimidate → 2-(1-naphthylmethyl)-imidazoline → naphazoline · HCl (Ciba 1942)
- **Chlorpheniramine maleate** (4 steps): 4-chlorobenzyl cyanide + 2-bromopyridine → α-arylated nitrile → N-alkyl + decyanation → chlorpheniramine + maleic acid → maleate (Schering 1949)

Hazard awareness:
- DSCG Step 1: acetic anhydride (OPCW Schedule 3) kg-scale → G7 enforcement upstream
- Chlorpheniramine Step 1-2: NaNH₂ / liquid NH₃ → 消防法 危険物 + operator training critical

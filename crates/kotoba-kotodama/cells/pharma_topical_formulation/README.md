# pharma_topical_formulation — Pregel cell for non-sterile topical compounding

Per **ADR-2605250600 Wave 1b** §Decision 2 (new dosage form: topical cream/gel/ointment).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **simeon** (kuni-umi commissioning sibling — container + filling pair).

Scope:
- Topical cream (oil-in-water emulsion)
- Topical gel (carbomer-based hydrogel)
- Topical ointment (hydrophobic petrolatum-based)

Wave 1b API → topical product:
- Clotrimazole 1% cream (antifungal)
- Diclofenac sodium 1% gel (NSAID for musculoskeletal pain)
- (future Wave 2: hydrocortisone 1% cream — steroid bioprocess capability required)

Process: oil phase + aqueous phase preparation (separate vessel heating to 70-75°C) →
emulsification (high-shear homogenizer) → cooling under gentle agitation →
viscosity adjustment → in-process homogeneity check → fill into aluminum tube
or HDPE jar → crimp / seal.

Non-sterile dosage form for **intact skin**. Sterility required only for ophthalmic
(eye ointment), wound/burn, or mucosal application — those are deferred to Wave 1c
sterile ointment carve-out (separate ADR if needed).

Microbial limit USP <61>/<62> + viscosity + pH + content uniformity by `pharma_qc`.

Constitutional gate G11 label content:
- clotrimazole: 7-14 day use limit, contact dermatitis warning
- diclofenac topical: photosensitivity warning, NOT for use on broken skin /
  3rd trimester pregnancy / under occlusion

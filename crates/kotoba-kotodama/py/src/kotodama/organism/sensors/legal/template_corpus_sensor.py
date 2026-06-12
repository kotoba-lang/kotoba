"""TemplateCorpusSensor — ``law/templates/<corpus>`` (chigiri-consumable templates).

Per ADR-2605262800 (legal corpus) §1 ``templates/`` layout + §3
``LegalTemplateSensor`` Protocol. A passive ``LegalTemplateSensor`` over a
pre-pinned subdataset of reusable legal-document templates (Apache 2.0 /
CC license texts, etzhayyim Charter Rider, covenant-ceremony templates,
dispute-mediation, donation-tax-receipt, data-privacy DSAR). Mirrors
``ProcedureCorpusSensor`` / ``TreatyCorpusSensor`` structure.

CONSTITUTIONAL discipline:
  - Passive-only (ADR-2605262400 §7): reads pre-captured NDJSON shards;
    no live scraping at organism-tick time.
  - G6 (ADR-2605262800): the template corpus is structurally SEPARATE
    from the raw-law corpus, so chigiri consumes a template without
    sub-licensing / UPL drift into raw statute text.
  - Tier-A by nature (Apache 2.0 / CC / own Rider / public templates).

Unlike statute/case/treaty/procedure observations, a template carries its
FULL ``body`` (not a 2000-char excerpt) — chigiri needs the whole template
to instantiate it. The optional ``chigiri_consumer_cell_hint`` names the
chigiri cell that consumes this corpus.

Hot-sample is deterministic on ``pin.revision`` per G9.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import LegalTemplateObservation, TemplateClass

# template_corpus selector → canonical subdataset slug (ADR §1 layout).
_CORPUS_SUBDATASET: dict[str, str] = {
    "apache-licenses": "apache-2.0-licenses",
    "cc-licenses": "creative-commons-licenses",
    "charter-rider": "etzhayyim-charter-rider",
    "covenant-ceremony": "covenant-ceremony",
    "dispute-mediation": "dispute-mediation",
    "donation-tax-receipt": "donation-tax-receipt",
    "data-privacy-dsar": "data-privacy-dsar",
}


@dataclass
class TemplateCorpusSensor:
    """Sensor over a ``law/templates/<corpus>/<rev>/`` subdataset NDJSON view.

    NDJSON row shape (one template per line)::

        {template_id, title, body, jurisdiction?, chigiri_cell?}

    ``jurisdiction`` and ``chigiri_cell`` may be supplied per-row (a
    tax-receipt / DSAR corpus spans jurisdictions) and otherwise fall back
    to the sensor-level defaults.
    """

    template_corpus: str
    template_class: TemplateClass = "license"
    jurisdiction_iso3: str | None = None
    chigiri_consumer_cell_hint: str | None = None
    name: str = ""
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "open"
    tier: Tier = "A"
    refresh_cadence_sec: int = 30 * 24 * 3600  # monthly — templates are stable
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name:
            sub = _CORPUS_SUBDATASET.get(self.template_corpus, self.template_corpus)
            self.name = f"law/templates/{sub}"

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_ndjson_paths(self, pin: DatasetPin) -> list[Path]:
        subdataset_dir = self.annex_root / self.name
        if not subdataset_dir.exists():
            raise FileNotFoundError(
                f"subdataset '{self.name}' not present at {subdataset_dir}"
            )
        candidates = sorted(
            (p for p in subdataset_dir.iterdir() if p.is_dir()), reverse=True
        )
        if not candidates:
            raise FileNotFoundError(f"no snapshot directory under {subdataset_dir}")
        ndjson_files = sorted(candidates[0].glob(f"*{self.ndjson_suffix}"))
        if not ndjson_files:
            raise FileNotFoundError(
                f"no '*{self.ndjson_suffix}' under {candidates[0]}"
            )
        return ndjson_files

    def stream(self, pin: DatasetPin) -> Iterator[LegalTemplateObservation]:
        for path in self._resolve_ndjson_paths(pin):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        row = json.loads(s)
                    except json.JSONDecodeError:
                        continue
                    yield self._row_to_observation(pin, row)

    def _row_to_observation(
        self, pin: DatasetPin, row: dict
    ) -> LegalTemplateObservation:
        jurisdiction = row.get("jurisdiction", self.jurisdiction_iso3)
        hint = row.get("chigiri_cell", self.chigiri_consumer_cell_hint)
        return LegalTemplateObservation(
            sensor=self.name,
            tier=self.tier,
            pin_revision=pin.revision,
            template_id=str(row.get("template_id", "")),
            title=str(row.get("title", "")),
            body=str(row.get("body", "")),  # FULL body — chigiri instantiates it
            jurisdiction_iso3=jurisdiction,
            template_class=self.template_class,
            license_tag=self.license,
            chigiri_consumer_cell_hint=hint,
            internal_only=False,
        )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalTemplateObservation]:
        # Reservoir sample; deterministic on (pin.revision, n) per G9.
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[LegalTemplateObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["TemplateCorpusSensor"]

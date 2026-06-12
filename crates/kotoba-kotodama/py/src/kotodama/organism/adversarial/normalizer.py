"""L1 Unicode Normalizer for Adversarial Robustness."""

import unicodedata
from dataclasses import dataclass

@dataclass
class NormalizationResult:
    normalized: str
    original: str
    transforms: list[str]
    suspicious: bool

# Basic confusable mapping (Cyrillic to Latin, etc.)
CONFUSABLES = {
    '\u0430': 'a', # Cyrillic a
    '\u0435': 'e', # Cyrillic e
    '\u043E': 'o', # Cyrillic o
    '\u0440': 'p', # Cyrillic p
    '\u0441': 'c', # Cyrillic c
    '\u0445': 'x', # Cyrillic x
    '\u0443': 'y', # Cyrillic y
    '\u0501': 'd', # Cyrillic d (approx)
    '\u03BF': 'o', # Greek omicron
}

# RTL Overrides and Bidi formatting characters
BIDI_CHARS = {
    '\u202A', '\u202B', '\u202C', '\u202D', '\u202E', '\u200E', '\u200F',
    '\u2066', '\u2067', '\u2068', '\u2069'
}

# Zero-width characters
ZERO_WIDTH_CHARS = {
    '\u200B', '\u200C', '\u200D', '\uFEFF'
}

def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def normalize_input(text: str) -> NormalizationResult:
    original = text
    suspicious = False
    transforms = []

    # 1. Remove Bidi and Zero-width characters
    has_bidi = any(c in BIDI_CHARS for c in text)
    has_zw = any(c in ZERO_WIDTH_CHARS for c in text)
    if has_bidi:
        suspicious = True
        transforms.append("removed_bidi_chars")
    if has_zw:
        suspicious = True
        transforms.append("removed_zero_width_chars")

    filtered = "".join(c for c in text if c not in BIDI_CHARS and c not in ZERO_WIDTH_CHARS)

    # 2. Confusable mapping
    deconfused = []
    mapped_count = 0
    for c in filtered:
        if c in CONFUSABLES:
            deconfused.append(CONFUSABLES[c])
            mapped_count += 1
        else:
            deconfused.append(c)

    if mapped_count > 0:
        transforms.append(f"mapped_{mapped_count}_confusables")
        suspicious = True

    step2_text = "".join(deconfused)

    # 3. NFKC Normalization
    normalized = unicodedata.normalize("NFKC", step2_text)
    if step2_text != normalized:
        transforms.append("nfkc_normalized")

    # 4. Check for drastic changes
    dist = _levenshtein(original, normalized)
    if dist > 0 and dist > len(original) / 3:
        suspicious = True
        if "levenshtein_high" not in transforms:
            transforms.append("levenshtein_high")

    return NormalizationResult(
        normalized=normalized,
        original=original,
        transforms=transforms,
        suspicious=suspicious
    )

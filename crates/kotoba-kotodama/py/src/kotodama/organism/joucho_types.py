from __future__ import annotations
from dataclasses import dataclass

@dataclass
class JouchoDelta:
    kankaku: int = 0
    kanjou: int = 0
    yokkyu: int = 0
    kakushin: int = 0
    seimei: int = 0

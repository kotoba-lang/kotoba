"""science knowledge graph primitives — paper ingest, taxon sync, model linking.

Six LangServer task types:
  science.paper.ingestBatch      — fetch arXiv/PubMed metadata → vertex_scientific_paper
  science.paper.embed            — abstract → embedding → ivf_cluster_id
  science.taxon.syncNCBI         — NCBI taxonomy subtree → vertex_scientific_taxon
  science.element.seed           — seed 118 periodic table elements (idempotent)
  science.taxon.linkModel        — assign kami render profile to taxa without models
  science.model.buildTileIndex   — aggregate vertex_kami_model_instance per H3 tile

LangGraph integration:
  SciencePaperBuilder (langgraph graph definition) runs as a Zeebe service task
  (task_type="science.langgraph.buildPaperKG") and checkpoints state to
  vertex_langgraph_state.

Architecture note: all DB writes go through psycopg3 sync_cursor directly to
RisingWave (Worker-direct Hyperdrive equivalent for Python, ADR-0036).
No PDS createRecord — these are domain tables, not social/federated.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import datetime as _dt
import hashlib
import json
import re
import uuid
from typing import Any, TypedDict


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_OWNER_DID = "did:web:science.etzhayyim.com"
_NOW = lambda: (
    _dt.datetime.now(tz=_dt.UTC)
    .replace(microsecond=0)
    .isoformat()
    .replace("+00:00", "Z")
)

# CPK coloring — all 118 elements.  Unlisted default: medium grey (0.5, 0.5, 0.5).
# Sources: Corey-Pauling-Koltun convention + Jmol/PyMOL extensions for heavy elements.
_CPK_COLORS: dict[str, tuple[float, float, float]] = {
    # Period 1
    "H":  (1.00, 1.00, 1.00), "He": (0.85, 1.00, 1.00),
    # Period 2
    "Li": (0.80, 0.50, 1.00), "Be": (0.76, 1.00, 0.00),
    "B":  (1.00, 0.71, 0.71), "C":  (0.20, 0.20, 0.20),
    "N":  (0.19, 0.31, 0.97), "O":  (1.00, 0.05, 0.05),
    "F":  (0.56, 0.88, 0.31), "Ne": (0.70, 0.89, 0.96),
    # Period 3
    "Na": (0.67, 0.36, 0.95), "Mg": (0.54, 1.00, 0.00),
    "Al": (0.75, 0.65, 0.65), "Si": (0.94, 0.78, 0.63),
    "P":  (1.00, 0.50, 0.00), "S":  (1.00, 1.00, 0.19),
    "Cl": (0.12, 0.94, 0.12), "Ar": (0.50, 0.82, 0.89),
    # Period 4
    "K":  (0.56, 0.25, 0.83), "Ca": (0.24, 1.00, 0.00),
    "Sc": (0.90, 0.90, 0.90), "Ti": (0.75, 0.76, 0.78),
    "V":  (0.65, 0.65, 0.67), "Cr": (0.54, 0.60, 0.78),
    "Mn": (0.61, 0.48, 0.78), "Fe": (0.88, 0.40, 0.20),
    "Co": (0.94, 0.56, 0.63), "Ni": (0.31, 0.82, 0.31),
    "Cu": (0.78, 0.50, 0.20), "Zn": (0.49, 0.50, 0.69),
    "Ga": (0.76, 0.56, 0.56), "Ge": (0.40, 0.56, 0.56),
    "As": (0.74, 0.50, 0.89), "Se": (1.00, 0.63, 0.00),
    "Br": (0.65, 0.16, 0.16), "Kr": (0.36, 0.72, 0.82),
    # Period 5
    "Rb": (0.44, 0.18, 0.69), "Sr": (0.00, 1.00, 0.00),
    "Y":  (0.58, 1.00, 1.00), "Zr": (0.58, 0.88, 0.88),
    "Nb": (0.45, 0.76, 0.79), "Mo": (0.33, 0.71, 0.71),
    "Tc": (0.23, 0.62, 0.62), "Ru": (0.14, 0.56, 0.56),
    "Rh": (0.04, 0.49, 0.55), "Pd": (0.00, 0.41, 0.52),
    "Ag": (0.75, 0.75, 0.75), "Cd": (1.00, 0.85, 0.56),
    "In": (0.65, 0.46, 0.45), "Sn": (0.40, 0.50, 0.50),
    "Sb": (0.62, 0.39, 0.71), "Te": (0.83, 0.48, 0.00),
    "I":  (0.58, 0.00, 0.58), "Xe": (0.26, 0.62, 0.69),
    # Period 6
    "Cs": (0.34, 0.09, 0.56), "Ba": (0.00, 0.79, 0.00),
    # Lanthanides (z=57..71) — light steel blue family
    "La": (0.44, 0.83, 1.00), "Ce": (1.00, 1.00, 0.78),
    "Pr": (0.85, 1.00, 0.78), "Nd": (0.78, 1.00, 0.78),
    "Pm": (0.64, 1.00, 0.78), "Sm": (0.56, 1.00, 0.78),
    "Eu": (0.38, 1.00, 0.78), "Gd": (0.27, 1.00, 0.78),
    "Tb": (0.19, 1.00, 0.78), "Dy": (0.12, 1.00, 0.78),
    "Ho": (0.00, 1.00, 0.61), "Er": (0.00, 0.90, 0.46),
    "Tm": (0.00, 0.83, 0.32), "Yb": (0.00, 0.75, 0.22),
    "Lu": (0.00, 0.67, 0.14),
    # Period 6 d-block
    "Hf": (0.30, 0.76, 1.00), "Ta": (0.30, 0.65, 1.00),
    "W":  (0.13, 0.58, 0.84), "Re": (0.15, 0.49, 0.67),
    "Os": (0.15, 0.40, 0.59), "Ir": (0.09, 0.33, 0.53),
    "Pt": (0.82, 0.82, 0.88), "Au": (1.00, 0.82, 0.14),
    "Hg": (0.72, 0.72, 0.82), "Tl": (0.65, 0.33, 0.30),
    "Pb": (0.34, 0.35, 0.38), "Bi": (0.62, 0.31, 0.71),
    "Po": (0.67, 0.36, 0.00), "At": (0.46, 0.31, 0.27),
    "Rn": (0.26, 0.51, 0.59),
    # Period 7
    "Fr": (0.26, 0.00, 0.40), "Ra": (0.00, 0.49, 0.00),
    # Actinides (z=89..103) — pale green family
    "Ac": (0.44, 0.67, 0.98), "Th": (0.00, 0.73, 1.00),
    "Pa": (0.00, 0.63, 1.00), "U":  (0.00, 0.56, 1.00),
    "Np": (0.00, 0.50, 1.00), "Pu": (0.00, 0.42, 1.00),
    "Am": (0.33, 0.36, 0.95), "Cm": (0.47, 0.36, 0.89),
    "Bk": (0.54, 0.31, 0.89), "Cf": (0.63, 0.21, 0.83),
    "Es": (0.70, 0.12, 0.83), "Fm": (0.70, 0.12, 0.73),
    "Md": (0.70, 0.05, 0.65), "No": (0.74, 0.05, 0.53),
    "Lr": (0.78, 0.00, 0.40),
    # Superheavy (z=104..118) — deep grey
    "Rf": (0.80, 0.00, 0.35), "Db": (0.82, 0.00, 0.31),
    "Sg": (0.85, 0.00, 0.27), "Bh": (0.88, 0.00, 0.22),
    "Hs": (0.90, 0.00, 0.18), "Mt": (0.92, 0.00, 0.15),
    "Ds": (0.93, 0.00, 0.12), "Rg": (0.94, 0.00, 0.10),
    "Cn": (0.52, 0.52, 0.52), "Nh": (0.55, 0.55, 0.55),
    "Fl": (0.58, 0.58, 0.58), "Mc": (0.60, 0.60, 0.60),
    "Lv": (0.62, 0.62, 0.62), "Ts": (0.64, 0.64, 0.64),
    "Og": (0.66, 0.66, 0.66),
}

# Minimal periodic table seed data (first 20 elements for CI speed;
# extend _ELEMENTS for full 118-element ingest).
_ELEMENTS: list[dict[str, Any]] = [
    {"z":  1, "sym": "H",  "en": "Hydrogen",   "ja": "水素",   "mass": 1.008,  "period": 1, "group": 1,  "block": "s", "cat": "nonmetal",      "r_pm": 53.0,  "mp_k":  14.0,  "bp_k":  20.3,  "dens": 0.0000899},
    {"z":  2, "sym": "He", "en": "Helium",     "ja": "ヘリウム", "mass": 4.003,  "period": 1, "group": 18, "block": "s", "cat": "noble_gas",     "r_pm": 31.0,  "mp_k":  0.95,  "bp_k":  4.2,   "dens": 0.0001785},
    {"z":  3, "sym": "Li", "en": "Lithium",    "ja": "リチウム", "mass": 6.941,  "period": 2, "group": 1,  "block": "s", "cat": "alkali_metal",  "r_pm": 167.0, "mp_k":  453.7, "bp_k":  1560.0,"dens": 0.534},
    {"z":  4, "sym": "Be", "en": "Beryllium",  "ja": "ベリリウム","mass": 9.012,  "period": 2, "group": 2,  "block": "s", "cat": "alkaline_earth","r_pm": 112.0, "mp_k":  1560.0,"bp_k":  2742.0,"dens": 1.85},
    {"z":  5, "sym": "B",  "en": "Boron",      "ja": "ホウ素",  "mass": 10.811, "period": 2, "group": 13, "block": "p", "cat": "metalloid",     "r_pm": 87.0,  "mp_k":  2349.0,"bp_k":  4200.0,"dens": 2.34},
    {"z":  6, "sym": "C",  "en": "Carbon",     "ja": "炭素",    "mass": 12.011, "period": 2, "group": 14, "block": "p", "cat": "nonmetal",      "r_pm": 67.0,  "mp_k":  3823.0,"bp_k":  4300.0,"dens": 2.267},
    {"z":  7, "sym": "N",  "en": "Nitrogen",   "ja": "窒素",    "mass": 14.007, "period": 2, "group": 15, "block": "p", "cat": "nonmetal",      "r_pm": 56.0,  "mp_k":  63.2,  "bp_k":  77.4,  "dens": 0.001251},
    {"z":  8, "sym": "O",  "en": "Oxygen",     "ja": "酸素",    "mass": 15.999, "period": 2, "group": 16, "block": "p", "cat": "nonmetal",      "r_pm": 48.0,  "mp_k":  54.4,  "bp_k":  90.2,  "dens": 0.001429},
    {"z":  9, "sym": "F",  "en": "Fluorine",   "ja": "フッ素",  "mass": 18.998, "period": 2, "group": 17, "block": "p", "cat": "halogen",       "r_pm": 42.0,  "mp_k":  53.5,  "bp_k":  85.0,  "dens": 0.001696},
    {"z": 10, "sym": "Ne", "en": "Neon",       "ja": "ネオン",  "mass": 20.18,  "period": 2, "group": 18, "block": "p", "cat": "noble_gas",     "r_pm": 38.0,  "mp_k":  24.6,  "bp_k":  27.1,  "dens": 0.0008999},
    {"z": 11, "sym": "Na", "en": "Sodium",     "ja": "ナトリウム","mass": 22.990, "period": 3, "group": 1,  "block": "s", "cat": "alkali_metal",  "r_pm": 190.0, "mp_k":  370.9, "bp_k":  1156.0,"dens": 0.971},
    {"z": 12, "sym": "Mg", "en": "Magnesium",  "ja": "マグネシウム","mass": 24.305,"period": 3, "group": 2,  "block": "s", "cat": "alkaline_earth","r_pm": 145.0, "mp_k":  923.0, "bp_k":  1363.0,"dens": 1.738},
    {"z": 13, "sym": "Al", "en": "Aluminum",   "ja": "アルミニウム","mass": 26.982,"period": 3, "group": 13, "block": "p", "cat": "post_transition","r_pm": 118.0,"mp_k":  933.5, "bp_k":  2792.0,"dens": 2.70},
    {"z": 14, "sym": "Si", "en": "Silicon",    "ja": "ケイ素",  "mass": 28.086, "period": 3, "group": 14, "block": "p", "cat": "metalloid",     "r_pm": 111.0, "mp_k":  1687.0,"bp_k":  3538.0,"dens": 2.33},
    {"z": 15, "sym": "P",  "en": "Phosphorus", "ja": "リン",    "mass": 30.974, "period": 3, "group": 15, "block": "p", "cat": "nonmetal",      "r_pm": 98.0,  "mp_k":  317.3, "bp_k":  553.7, "dens": 1.82},
    {"z": 16, "sym": "S",  "en": "Sulfur",     "ja": "硫黄",    "mass": 32.06,  "period": 3, "group": 16, "block": "p", "cat": "nonmetal",      "r_pm": 88.0,  "mp_k":  388.4, "bp_k":  717.8, "dens": 2.07},
    {"z": 17, "sym": "Cl", "en": "Chlorine",   "ja": "塩素",    "mass": 35.45,  "period": 3, "group": 17, "block": "p", "cat": "halogen",       "r_pm": 79.0,  "mp_k":  171.6, "bp_k":  239.1, "dens": 0.003214},
    {"z": 18, "sym": "Ar", "en": "Argon",      "ja": "アルゴン", "mass": 39.948, "period": 3, "group": 18, "block": "p", "cat": "noble_gas",     "r_pm": 71.0,  "mp_k":  83.8,  "bp_k":  87.3,  "dens": 0.001784},
    {"z": 19, "sym": "K",  "en": "Potassium",  "ja": "カリウム", "mass": 39.098, "period": 4, "group": 1,  "block": "s", "cat": "alkali_metal",  "r_pm": 243.0, "mp_k":  336.5, "bp_k":  1032.0,"dens": 0.862},
    {"z": 20, "sym": "Ca", "en": "Calcium",    "ja": "カルシウム","mass": 40.078, "period": 4, "group": 2,  "block": "s", "cat": "alkaline_earth","r_pm": 194.0, "mp_k":  1115.0,"bp_k":  1757.0,"dens": 1.55},
    # Period 4 transition metals + p-block
    {"z": 21, "sym": "Sc", "en": "Scandium",    "ja": "スカンジウム",   "mass": 44.956,  "period": 4, "group": 3,  "block": "d", "cat": "transition",     "r_pm": 184.0, "mp_k": 1814.0, "bp_k": 3109.0, "dens": 2.985},
    {"z": 22, "sym": "Ti", "en": "Titanium",    "ja": "チタン",        "mass": 47.867,  "period": 4, "group": 4,  "block": "d", "cat": "transition",     "r_pm": 176.0, "mp_k": 1941.0, "bp_k": 3560.0, "dens": 4.506},
    {"z": 23, "sym": "V",  "en": "Vanadium",    "ja": "バナジウム",     "mass": 50.942,  "period": 4, "group": 5,  "block": "d", "cat": "transition",     "r_pm": 171.0, "mp_k": 2183.0, "bp_k": 3680.0, "dens": 6.11},
    {"z": 24, "sym": "Cr", "en": "Chromium",    "ja": "クロム",        "mass": 51.996,  "period": 4, "group": 6,  "block": "d", "cat": "transition",     "r_pm": 166.0, "mp_k": 2180.0, "bp_k": 2944.0, "dens": 7.15},
    {"z": 25, "sym": "Mn", "en": "Manganese",   "ja": "マンガン",      "mass": 54.938,  "period": 4, "group": 7,  "block": "d", "cat": "transition",     "r_pm": 161.0, "mp_k": 1519.0, "bp_k": 2334.0, "dens": 7.21},
    {"z": 26, "sym": "Fe", "en": "Iron",        "ja": "鉄",           "mass": 55.845,  "period": 4, "group": 8,  "block": "d", "cat": "transition",     "r_pm": 156.0, "mp_k": 1811.0, "bp_k": 3134.0, "dens": 7.87},
    {"z": 27, "sym": "Co", "en": "Cobalt",      "ja": "コバルト",      "mass": 58.933,  "period": 4, "group": 9,  "block": "d", "cat": "transition",     "r_pm": 152.0, "mp_k": 1768.0, "bp_k": 3200.0, "dens": 8.86},
    {"z": 28, "sym": "Ni", "en": "Nickel",      "ja": "ニッケル",      "mass": 58.693,  "period": 4, "group": 10, "block": "d", "cat": "transition",     "r_pm": 149.0, "mp_k": 1728.0, "bp_k": 3186.0, "dens": 8.908},
    {"z": 29, "sym": "Cu", "en": "Copper",      "ja": "銅",           "mass": 63.546,  "period": 4, "group": 11, "block": "d", "cat": "transition",     "r_pm": 145.0, "mp_k": 1358.0, "bp_k": 2835.0, "dens": 8.96},
    {"z": 30, "sym": "Zn", "en": "Zinc",        "ja": "亜鉛",         "mass": 65.38,   "period": 4, "group": 12, "block": "d", "cat": "transition",     "r_pm": 142.0, "mp_k":  693.0, "bp_k": 1180.0, "dens": 7.13},
    {"z": 31, "sym": "Ga", "en": "Gallium",     "ja": "ガリウム",      "mass": 69.723,  "period": 4, "group": 13, "block": "p", "cat": "post_transition","r_pm": 136.0, "mp_k":  303.0, "bp_k": 2473.0, "dens": 5.91},
    {"z": 32, "sym": "Ge", "en": "Germanium",   "ja": "ゲルマニウム",   "mass": 72.630,  "period": 4, "group": 14, "block": "p", "cat": "metalloid",     "r_pm": 125.0, "mp_k": 1211.0, "bp_k": 3106.0, "dens": 5.323},
    {"z": 33, "sym": "As", "en": "Arsenic",     "ja": "ヒ素",         "mass": 74.922,  "period": 4, "group": 15, "block": "p", "cat": "metalloid",     "r_pm": 114.0, "mp_k": 1090.0, "bp_k":  887.0, "dens": 5.727},
    {"z": 34, "sym": "Se", "en": "Selenium",    "ja": "セレン",        "mass": 78.971,  "period": 4, "group": 16, "block": "p", "cat": "nonmetal",      "r_pm": 103.0, "mp_k":  494.0, "bp_k":  958.0, "dens": 4.81},
    {"z": 35, "sym": "Br", "en": "Bromine",     "ja": "臭素",         "mass": 79.904,  "period": 4, "group": 17, "block": "p", "cat": "halogen",       "r_pm":  94.0, "mp_k":  266.0, "bp_k":  332.0, "dens": 3.12},
    {"z": 36, "sym": "Kr", "en": "Krypton",     "ja": "クリプトン",    "mass": 83.798,  "period": 4, "group": 18, "block": "p", "cat": "noble_gas",     "r_pm":  88.0, "mp_k":  116.0, "bp_k":  120.0, "dens": 0.003733},
    # Period 5
    {"z": 37, "sym": "Rb", "en": "Rubidium",    "ja": "ルビジウム",    "mass": 85.468,  "period": 5, "group": 1,  "block": "s", "cat": "alkali_metal",  "r_pm": 265.0, "mp_k":  312.0, "bp_k":  961.0, "dens": 1.532},
    {"z": 38, "sym": "Sr", "en": "Strontium",   "ja": "ストロンチウム", "mass": 87.62,   "period": 5, "group": 2,  "block": "s", "cat": "alkaline_earth","r_pm": 219.0, "mp_k": 1050.0, "bp_k": 1655.0, "dens": 2.64},
    {"z": 39, "sym": "Y",  "en": "Yttrium",     "ja": "イットリウム",  "mass": 88.906,  "period": 5, "group": 3,  "block": "d", "cat": "transition",     "r_pm": 212.0, "mp_k": 1799.0, "bp_k": 3609.0, "dens": 4.472},
    {"z": 40, "sym": "Zr", "en": "Zirconium",   "ja": "ジルコニウム",  "mass": 91.224,  "period": 5, "group": 4,  "block": "d", "cat": "transition",     "r_pm": 206.0, "mp_k": 2128.0, "bp_k": 4682.0, "dens": 6.511},
    {"z": 41, "sym": "Nb", "en": "Niobium",     "ja": "ニオブ",       "mass": 92.906,  "period": 5, "group": 5,  "block": "d", "cat": "transition",     "r_pm": 198.0, "mp_k": 2750.0, "bp_k": 5017.0, "dens": 8.57},
    {"z": 42, "sym": "Mo", "en": "Molybdenum",  "ja": "モリブデン",    "mass": 95.95,   "period": 5, "group": 6,  "block": "d", "cat": "transition",     "r_pm": 190.0, "mp_k": 2896.0, "bp_k": 4912.0, "dens": 10.22},
    {"z": 43, "sym": "Tc", "en": "Technetium",  "ja": "テクネチウム",  "mass": 97.0,    "period": 5, "group": 7,  "block": "d", "cat": "transition",     "r_pm": 183.0, "mp_k": 2430.0, "bp_k": 4538.0, "dens": 11.0},
    {"z": 44, "sym": "Ru", "en": "Ruthenium",   "ja": "ルテニウム",    "mass": 101.07,  "period": 5, "group": 8,  "block": "d", "cat": "transition",     "r_pm": 178.0, "mp_k": 2607.0, "bp_k": 4423.0, "dens": 12.45},
    {"z": 45, "sym": "Rh", "en": "Rhodium",     "ja": "ロジウム",      "mass": 102.906, "period": 5, "group": 9,  "block": "d", "cat": "transition",     "r_pm": 173.0, "mp_k": 2237.0, "bp_k": 3968.0, "dens": 12.41},
    {"z": 46, "sym": "Pd", "en": "Palladium",   "ja": "パラジウム",    "mass": 106.42,  "period": 5, "group": 10, "block": "d", "cat": "transition",     "r_pm": 169.0, "mp_k": 1828.0, "bp_k": 3236.0, "dens": 12.02},
    {"z": 47, "sym": "Ag", "en": "Silver",      "ja": "銀",           "mass": 107.868, "period": 5, "group": 11, "block": "d", "cat": "transition",     "r_pm": 165.0, "mp_k": 1235.0, "bp_k": 2435.0, "dens": 10.49},
    {"z": 48, "sym": "Cd", "en": "Cadmium",     "ja": "カドミウム",    "mass": 112.414, "period": 5, "group": 12, "block": "d", "cat": "transition",     "r_pm": 161.0, "mp_k":  594.0, "bp_k": 1040.0, "dens": 8.65},
    {"z": 49, "sym": "In", "en": "Indium",      "ja": "インジウム",    "mass": 114.818, "period": 5, "group": 13, "block": "p", "cat": "post_transition","r_pm": 156.0, "mp_k":  430.0, "bp_k": 2345.0, "dens": 7.31},
    {"z": 50, "sym": "Sn", "en": "Tin",         "ja": "スズ",         "mass": 118.710, "period": 5, "group": 14, "block": "p", "cat": "post_transition","r_pm": 145.0, "mp_k":  505.0, "bp_k": 2875.0, "dens": 7.287},
    {"z": 51, "sym": "Sb", "en": "Antimony",    "ja": "アンチモン",    "mass": 121.760, "period": 5, "group": 15, "block": "p", "cat": "metalloid",     "r_pm": 133.0, "mp_k":  904.0, "bp_k": 1860.0, "dens": 6.68},
    {"z": 52, "sym": "Te", "en": "Tellurium",   "ja": "テルル",       "mass": 127.60,  "period": 5, "group": 16, "block": "p", "cat": "metalloid",     "r_pm": 123.0, "mp_k":  723.0, "bp_k": 1261.0, "dens": 6.24},
    {"z": 53, "sym": "I",  "en": "Iodine",      "ja": "ヨウ素",       "mass": 126.904, "period": 5, "group": 17, "block": "p", "cat": "halogen",       "r_pm": 115.0, "mp_k":  387.0, "bp_k":  457.0, "dens": 4.933},
    {"z": 54, "sym": "Xe", "en": "Xenon",       "ja": "キセノン",      "mass": 131.293, "period": 5, "group": 18, "block": "p", "cat": "noble_gas",     "r_pm": 108.0, "mp_k":  161.0, "bp_k":  165.0, "dens": 0.005887},
    # Period 6
    {"z": 55, "sym": "Cs", "en": "Cesium",      "ja": "セシウム",      "mass": 132.905, "period": 6, "group": 1,  "block": "s", "cat": "alkali_metal",  "r_pm": 298.0, "mp_k":  302.0, "bp_k":  944.0, "dens": 1.873},
    {"z": 56, "sym": "Ba", "en": "Barium",      "ja": "バリウム",      "mass": 137.327, "period": 6, "group": 2,  "block": "s", "cat": "alkaline_earth","r_pm": 253.0, "mp_k": 1000.0, "bp_k": 2170.0, "dens": 3.51},
    # Lanthanides
    {"z": 57, "sym": "La", "en": "Lanthanum",   "ja": "ランタン",      "mass": 138.905, "period": 6, "group": 3,  "block": "f", "cat": "lanthanide",    "r_pm": 195.0, "mp_k": 1193.0, "bp_k": 3737.0, "dens": 6.162},
    {"z": 58, "sym": "Ce", "en": "Cerium",      "ja": "セリウム",      "mass": 140.116, "period": 6, "group": 4,  "block": "f", "cat": "lanthanide",    "r_pm": 185.0, "mp_k": 1071.0, "bp_k": 3716.0, "dens": 6.77},
    {"z": 59, "sym": "Pr", "en": "Praseodymium","ja": "プラセオジム",  "mass": 140.908, "period": 6, "group": 5,  "block": "f", "cat": "lanthanide",    "r_pm": 185.0, "mp_k": 1208.0, "bp_k": 3793.0, "dens": 6.77},
    {"z": 60, "sym": "Nd", "en": "Neodymium",   "ja": "ネオジム",      "mass": 144.242, "period": 6, "group": 6,  "block": "f", "cat": "lanthanide",    "r_pm": 185.0, "mp_k": 1297.0, "bp_k": 3347.0, "dens": 7.01},
    {"z": 61, "sym": "Pm", "en": "Promethium",  "ja": "プロメチウム",  "mass": 145.0,   "period": 6, "group": 7,  "block": "f", "cat": "lanthanide",    "r_pm": 185.0, "mp_k": 1315.0, "bp_k": 3273.0, "dens": 7.26},
    {"z": 62, "sym": "Sm", "en": "Samarium",    "ja": "サマリウム",    "mass": 150.36,  "period": 6, "group": 8,  "block": "f", "cat": "lanthanide",    "r_pm": 185.0, "mp_k": 1345.0, "bp_k": 2067.0, "dens": 7.52},
    {"z": 63, "sym": "Eu", "en": "Europium",    "ja": "ユウロピウム",  "mass": 151.964, "period": 6, "group": 9,  "block": "f", "cat": "lanthanide",    "r_pm": 185.0, "mp_k": 1099.0, "bp_k": 1802.0, "dens": 5.244},
    {"z": 64, "sym": "Gd", "en": "Gadolinium",  "ja": "ガドリニウム",  "mass": 157.25,  "period": 6, "group": 10, "block": "f", "cat": "lanthanide",    "r_pm": 180.0, "mp_k": 1585.0, "bp_k": 3546.0, "dens": 7.90},
    {"z": 65, "sym": "Tb", "en": "Terbium",     "ja": "テルビウム",    "mass": 158.925, "period": 6, "group": 11, "block": "f", "cat": "lanthanide",    "r_pm": 175.0, "mp_k": 1629.0, "bp_k": 3503.0, "dens": 8.23},
    {"z": 66, "sym": "Dy", "en": "Dysprosium",  "ja": "ジスプロシウム","mass": 162.500, "period": 6, "group": 12, "block": "f", "cat": "lanthanide",    "r_pm": 175.0, "mp_k": 1680.0, "bp_k": 2840.0, "dens": 8.55},
    {"z": 67, "sym": "Ho", "en": "Holmium",     "ja": "ホルミウム",    "mass": 164.930, "period": 6, "group": 13, "block": "f", "cat": "lanthanide",    "r_pm": 175.0, "mp_k": 1734.0, "bp_k": 2993.0, "dens": 8.79},
    {"z": 68, "sym": "Er", "en": "Erbium",      "ja": "エルビウム",    "mass": 167.259, "period": 6, "group": 14, "block": "f", "cat": "lanthanide",    "r_pm": 175.0, "mp_k": 1802.0, "bp_k": 3141.0, "dens": 9.07},
    {"z": 69, "sym": "Tm", "en": "Thulium",     "ja": "ツリウム",      "mass": 168.934, "period": 6, "group": 15, "block": "f", "cat": "lanthanide",    "r_pm": 175.0, "mp_k": 1818.0, "bp_k": 2223.0, "dens": 9.32},
    {"z": 70, "sym": "Yb", "en": "Ytterbium",   "ja": "イッテルビウム","mass": 173.045, "period": 6, "group": 16, "block": "f", "cat": "lanthanide",    "r_pm": 175.0, "mp_k": 1097.0, "bp_k": 1469.0, "dens": 6.90},
    {"z": 71, "sym": "Lu", "en": "Lutetium",    "ja": "ルテチウム",    "mass": 174.967, "period": 6, "group": 17, "block": "f", "cat": "lanthanide",    "r_pm": 175.0, "mp_k": 1925.0, "bp_k": 3675.0, "dens": 9.84},
    # Period 6 d-block
    {"z": 72, "sym": "Hf", "en": "Hafnium",     "ja": "ハフニウム",    "mass": 178.49,  "period": 6, "group": 4,  "block": "d", "cat": "transition",     "r_pm": 187.0, "mp_k": 2506.0, "bp_k": 4876.0, "dens": 13.31},
    {"z": 73, "sym": "Ta", "en": "Tantalum",    "ja": "タンタル",      "mass": 180.948, "period": 6, "group": 5,  "block": "d", "cat": "transition",     "r_pm": 170.0, "mp_k": 3290.0, "bp_k": 5731.0, "dens": 16.65},
    {"z": 74, "sym": "W",  "en": "Tungsten",    "ja": "タングステン",  "mass": 183.84,  "period": 6, "group": 6,  "block": "d", "cat": "transition",     "r_pm": 162.0, "mp_k": 3695.0, "bp_k": 5828.0, "dens": 19.25},
    {"z": 75, "sym": "Re", "en": "Rhenium",     "ja": "レニウム",      "mass": 186.207, "period": 6, "group": 7,  "block": "d", "cat": "transition",     "r_pm": 151.0, "mp_k": 3459.0, "bp_k": 5869.0, "dens": 21.02},
    {"z": 76, "sym": "Os", "en": "Osmium",      "ja": "オスミウム",    "mass": 190.23,  "period": 6, "group": 8,  "block": "d", "cat": "transition",     "r_pm": 144.0, "mp_k": 3306.0, "bp_k": 5285.0, "dens": 22.59},
    {"z": 77, "sym": "Ir", "en": "Iridium",     "ja": "イリジウム",    "mass": 192.217, "period": 6, "group": 9,  "block": "d", "cat": "transition",     "r_pm": 141.0, "mp_k": 2719.0, "bp_k": 4701.0, "dens": 22.56},
    {"z": 78, "sym": "Pt", "en": "Platinum",    "ja": "白金",         "mass": 195.084, "period": 6, "group": 10, "block": "d", "cat": "transition",     "r_pm": 135.0, "mp_k": 2041.0, "bp_k": 4098.0, "dens": 21.45},
    {"z": 79, "sym": "Au", "en": "Gold",        "ja": "金",           "mass": 196.967, "period": 6, "group": 11, "block": "d", "cat": "transition",     "r_pm": 135.0, "mp_k": 1337.0, "bp_k": 3129.0, "dens": 19.28},
    {"z": 80, "sym": "Hg", "en": "Mercury",     "ja": "水銀",         "mass": 200.592, "period": 6, "group": 12, "block": "d", "cat": "transition",     "r_pm": 150.0, "mp_k":  234.0, "bp_k":  630.0, "dens": 13.53},
    {"z": 81, "sym": "Tl", "en": "Thallium",    "ja": "タリウム",      "mass": 204.383, "period": 6, "group": 13, "block": "p", "cat": "post_transition","r_pm": 190.0, "mp_k":  577.0, "bp_k": 1746.0, "dens": 11.85},
    {"z": 82, "sym": "Pb", "en": "Lead",        "ja": "鉛",           "mass": 207.2,   "period": 6, "group": 14, "block": "p", "cat": "post_transition","r_pm": 180.0, "mp_k":  601.0, "bp_k": 2022.0, "dens": 11.34},
    {"z": 83, "sym": "Bi", "en": "Bismuth",     "ja": "ビスマス",      "mass": 208.980, "period": 6, "group": 15, "block": "p", "cat": "post_transition","r_pm": 160.0, "mp_k":  544.0, "bp_k": 1837.0, "dens": 9.79},
    {"z": 84, "sym": "Po", "en": "Polonium",    "ja": "ポロニウム",    "mass": 209.0,   "period": 6, "group": 16, "block": "p", "cat": "metalloid",     "r_pm": 190.0, "mp_k":  527.0, "bp_k": 1235.0, "dens": 9.2},
    {"z": 85, "sym": "At", "en": "Astatine",    "ja": "アスタチン",    "mass": 210.0,   "period": 6, "group": 17, "block": "p", "cat": "halogen",       "r_pm": 150.0, "mp_k":  575.0, "bp_k":  610.0, "dens": 7.0},
    {"z": 86, "sym": "Rn", "en": "Radon",       "ja": "ラドン",       "mass": 222.0,   "period": 6, "group": 18, "block": "p", "cat": "noble_gas",     "r_pm": 120.0, "mp_k":  202.0, "bp_k":  211.0, "dens": 0.00973},
    # Period 7
    {"z": 87, "sym": "Fr", "en": "Francium",    "ja": "フランシウム",  "mass": 223.0,   "period": 7, "group": 1,  "block": "s", "cat": "alkali_metal",  "r_pm": 348.0, "mp_k":  300.0, "bp_k":  950.0, "dens": 1.87},
    {"z": 88, "sym": "Ra", "en": "Radium",      "ja": "ラジウム",      "mass": 226.0,   "period": 7, "group": 2,  "block": "s", "cat": "alkaline_earth","r_pm": 215.0, "mp_k":  973.0, "bp_k": 2010.0, "dens": 5.0},
    # Actinides
    {"z": 89, "sym": "Ac", "en": "Actinium",    "ja": "アクチニウム",  "mass": 227.0,   "period": 7, "group": 3,  "block": "f", "cat": "actinide",      "r_pm": 195.0, "mp_k": 1323.0, "bp_k": 3471.0, "dens": 10.07},
    {"z": 90, "sym": "Th", "en": "Thorium",     "ja": "トリウム",      "mass": 232.038, "period": 7, "group": 4,  "block": "f", "cat": "actinide",      "r_pm": 180.0, "mp_k": 2023.0, "bp_k": 5061.0, "dens": 11.72},
    {"z": 91, "sym": "Pa", "en": "Protactinium","ja": "プロトアクチニウム","mass": 231.036,"period": 7, "group": 5,  "block": "f", "cat": "actinide",      "r_pm": 180.0, "mp_k": 1841.0, "bp_k": 4300.0, "dens": 15.37},
    {"z": 92, "sym": "U",  "en": "Uranium",     "ja": "ウラン",        "mass": 238.029, "period": 7, "group": 6,  "block": "f", "cat": "actinide",      "r_pm": 175.0, "mp_k": 1405.0, "bp_k": 4404.0, "dens": 19.05},
    {"z": 93, "sym": "Np", "en": "Neptunium",   "ja": "ネプツニウム",  "mass": 237.0,   "period": 7, "group": 7,  "block": "f", "cat": "actinide",      "r_pm": 175.0, "mp_k":  912.0, "bp_k": 4175.0, "dens": 20.45},
    {"z": 94, "sym": "Pu", "en": "Plutonium",   "ja": "プルトニウム",  "mass": 244.0,   "period": 7, "group": 8,  "block": "f", "cat": "actinide",      "r_pm": 175.0, "mp_k":  913.0, "bp_k": 3501.0, "dens": 19.84},
    {"z": 95, "sym": "Am", "en": "Americium",   "ja": "アメリシウム",  "mass": 243.0,   "period": 7, "group": 9,  "block": "f", "cat": "actinide",      "r_pm": 175.0, "mp_k": 1449.0, "bp_k": 2880.0, "dens": 13.69},
    {"z": 96, "sym": "Cm", "en": "Curium",      "ja": "キュリウム",    "mass": 247.0,   "period": 7, "group": 10, "block": "f", "cat": "actinide",      "r_pm": 176.0, "mp_k": 1618.0, "bp_k": 3383.0, "dens": 13.51},
    {"z": 97, "sym": "Bk", "en": "Berkelium",   "ja": "バークリウム",  "mass": 247.0,   "period": 7, "group": 11, "block": "f", "cat": "actinide",      "r_pm": 170.0, "mp_k": 1259.0, "bp_k": 2900.0, "dens": 14.78},
    {"z": 98, "sym": "Cf", "en": "Californium", "ja": "カリフォルニウム","mass": 251.0,  "period": 7, "group": 12, "block": "f", "cat": "actinide",      "r_pm": 170.0, "mp_k": 1173.0, "bp_k": 1743.0, "dens": 15.1},
    {"z": 99, "sym": "Es", "en": "Einsteinium", "ja": "アインスタイニウム","mass": 252.0,"period": 7, "group": 13, "block": "f", "cat": "actinide",      "r_pm": 170.0, "mp_k": 1133.0, "bp_k": 1269.0, "dens": 8.84},
    {"z":100, "sym": "Fm", "en": "Fermium",     "ja": "フェルミウム",  "mass": 257.0,   "period": 7, "group": 14, "block": "f", "cat": "actinide",      "r_pm": 170.0, "mp_k": 1800.0, "bp_k":    0.0, "dens": 0.0},
    {"z":101, "sym": "Md", "en": "Mendelevium", "ja": "メンデレビウム","mass": 258.0,   "period": 7, "group": 15, "block": "f", "cat": "actinide",      "r_pm": 170.0, "mp_k": 1100.0, "bp_k":    0.0, "dens": 0.0},
    {"z":102, "sym": "No", "en": "Nobelium",    "ja": "ノーベリウム",  "mass": 259.0,   "period": 7, "group": 16, "block": "f", "cat": "actinide",      "r_pm": 170.0, "mp_k": 1100.0, "bp_k":    0.0, "dens": 0.0},
    {"z":103, "sym": "Lr", "en": "Lawrencium",  "ja": "ローレンシウム","mass": 266.0,   "period": 7, "group": 17, "block": "d", "cat": "actinide",      "r_pm": 171.0, "mp_k": 1900.0, "bp_k":    0.0, "dens": 0.0},
    # Superheavy (z=104..118)
    {"z":104, "sym": "Rf", "en": "Rutherfordium","ja": "ラザホージウム","mass": 267.0,  "period": 7, "group": 4,  "block": "d", "cat": "transition",     "r_pm": 160.0, "mp_k": 2400.0, "bp_k": 5800.0, "dens": 23.2},
    {"z":105, "sym": "Db", "en": "Dubnium",     "ja": "ドブニウム",    "mass": 268.0,   "period": 7, "group": 5,  "block": "d", "cat": "transition",     "r_pm": 149.0, "mp_k":    0.0, "bp_k":    0.0, "dens": 29.3},
    {"z":106, "sym": "Sg", "en": "Seaborgium",  "ja": "シーボーギウム","mass": 269.0,   "period": 7, "group": 6,  "block": "d", "cat": "transition",     "r_pm": 143.0, "mp_k":    0.0, "bp_k":    0.0, "dens": 35.0},
    {"z":107, "sym": "Bh", "en": "Bohrium",     "ja": "ボーリウム",    "mass": 270.0,   "period": 7, "group": 7,  "block": "d", "cat": "transition",     "r_pm": 141.0, "mp_k":    0.0, "bp_k":    0.0, "dens": 37.1},
    {"z":108, "sym": "Hs", "en": "Hassium",     "ja": "ハッシウム",    "mass": 269.0,   "period": 7, "group": 8,  "block": "d", "cat": "transition",     "r_pm": 134.0, "mp_k":    0.0, "bp_k":    0.0, "dens": 40.7},
    {"z":109, "sym": "Mt", "en": "Meitnerium",  "ja": "マイトネリウム","mass": 278.0,   "period": 7, "group": 9,  "block": "d", "cat": "transition",     "r_pm": 129.0, "mp_k":    0.0, "bp_k":    0.0, "dens": 37.4},
    {"z":110, "sym": "Ds", "en": "Darmstadtium","ja": "ダームスタチウム","mass": 281.0, "period": 7, "group": 10, "block": "d", "cat": "transition",     "r_pm": 128.0, "mp_k":    0.0, "bp_k":    0.0, "dens": 34.8},
    {"z":111, "sym": "Rg", "en": "Roentgenium", "ja": "レントゲニウム","mass": 282.0,   "period": 7, "group": 11, "block": "d", "cat": "transition",     "r_pm": 121.0, "mp_k":    0.0, "bp_k":    0.0, "dens": 28.7},
    {"z":112, "sym": "Cn", "en": "Copernicium", "ja": "コペルニシウム","mass": 285.0,   "period": 7, "group": 12, "block": "d", "cat": "transition",     "r_pm": 122.0, "mp_k":  357.0, "bp_k":  384.0, "dens": 23.7},
    {"z":113, "sym": "Nh", "en": "Nihonium",    "ja": "ニホニウム",    "mass": 286.0,   "period": 7, "group": 13, "block": "p", "cat": "post_transition","r_pm": 136.0, "mp_k":  700.0, "bp_k": 1430.0, "dens": 16.0},
    {"z":114, "sym": "Fl", "en": "Flerovium",   "ja": "フレロビウム",  "mass": 289.0,   "period": 7, "group": 14, "block": "p", "cat": "post_transition","r_pm": 143.0, "mp_k":  340.0, "bp_k":  420.0, "dens": 14.0},
    {"z":115, "sym": "Mc", "en": "Moscovium",   "ja": "モスコビウム",  "mass": 290.0,   "period": 7, "group": 15, "block": "p", "cat": "post_transition","r_pm": 162.0, "mp_k":  670.0, "bp_k": 1400.0, "dens": 13.5},
    {"z":116, "sym": "Lv", "en": "Livermorium", "ja": "リバモリウム",  "mass": 293.0,   "period": 7, "group": 16, "block": "p", "cat": "post_transition","r_pm": 175.0, "mp_k":  709.0, "bp_k": 1085.0, "dens": 12.9},
    {"z":117, "sym": "Ts", "en": "Tennessine",  "ja": "テネシン",      "mass": 294.0,   "period": 7, "group": 17, "block": "p", "cat": "halogen",       "r_pm": 165.0, "mp_k":  723.0, "bp_k":  883.0, "dens": 7.2},
    {"z":118, "sym": "Og", "en": "Oganesson",   "ja": "オガネソン",    "mass": 294.0,   "period": 7, "group": 18, "block": "p", "cat": "noble_gas",     "r_pm": 157.0, "mp_k":  325.0, "bp_k":  450.0, "dens": 7.2},
]

# kami-vegetation canonical render profiles (7 presets matching taxonomy.rs)
_VEGETATION_RENDER_PROFILES: list[dict[str, Any]] = [
    {"commonName": "grass",   "division": "angiospermae", "habit": "grass",     "arrangement": "basal",    "leafShape": "linear",    "canopy": "blade",  "heightRange": [0.7, 1.4], "stemRadiusBase": 0.0,  "stemRadiusTop": 0.0,  "leafCount": 3, "leafSize": 0.18, "colorBase": [0.18, 0.42, 0.08], "colorTip": [0.42, 0.68, 0.15]},
    {"commonName": "fern",    "division": "pteridophyta", "habit": "herb",      "arrangement": "alternate","leafShape": "pinnate",   "canopy": "fan",    "heightRange": [0.8, 1.5], "stemRadiusBase": 0.04, "stemRadiusTop": 0.02, "leafCount": 5, "leafSize": 0.35, "colorBase": [0.12, 0.28, 0.04], "colorTip": [0.3,  0.55, 0.12]},
    {"commonName": "palm",    "division": "angiospermae", "habit": "tree",      "arrangement": "whorled",  "leafShape": "pinnate",   "canopy": "radial", "heightRange": [0.85, 1.25],"stemRadiusBase": 0.08,"stemRadiusTop": 0.06, "leafCount": 7, "leafSize": 0.55, "colorBase": [0.35, 0.22, 0.08], "colorTip": [0.18, 0.45, 0.10]},
    {"commonName": "conifer", "division": "gymnospermae", "habit": "tree",      "arrangement": "whorled",  "leafShape": "needle",    "canopy": "cone",   "heightRange": [0.7, 1.3], "stemRadiusBase": 0.09, "stemRadiusTop": 0.03, "leafCount": 3, "leafSize": 0.42, "colorBase": [0.25, 0.18, 0.08], "colorTip": [0.12, 0.30, 0.08]},
    {"commonName": "bush",    "division": "angiospermae", "habit": "shrub",     "arrangement": "alternate","leafShape": "ovate",     "canopy": "dome",   "heightRange": [0.8, 1.4], "stemRadiusBase": 0.06, "stemRadiusTop": 0.04, "leafCount": 6, "leafSize": 0.33, "colorBase": [0.15, 0.28, 0.06], "colorTip": [0.28, 0.48, 0.10]},
    {"commonName": "cactus",  "division": "angiospermae", "habit": "succulent", "arrangement": "none",     "leafShape": "succulent", "canopy": "column", "heightRange": [0.6, 1.3], "stemRadiusBase": 0.22, "stemRadiusTop": 0.18, "leafCount": 0, "leafSize": 0.0,  "colorBase": [0.22, 0.38, 0.18], "colorTip": [0.32, 0.52, 0.22]},
    {"commonName": "moss",    "division": "bryophyta",    "habit": "mat",       "arrangement": "none",     "leafShape": "scale",     "canopy": "carpet", "heightRange": [0.15, 0.25],"stemRadiusBase": 0.0, "stemRadiusTop": 0.0,  "leafCount": 1, "leafSize": 0.45, "colorBase": [0.16, 0.30, 0.08], "colorTip": [0.32, 0.54, 0.14]},
]


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _vid(actor: str, collection: str, rkey: str) -> str:
    return f"at://did:web:{actor}.etzhayyim.com/com.etzhayyim.apps.{actor}.{collection}/{rkey}"


def _edge_id(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:24]


# ──────────────────────────────────────────────────────────────────────
# Task: seed 118 periodic table elements (idempotent)
# ──────────────────────────────────────────────────────────────────────

def seed_periodic_elements(batch_size: int = 20) -> dict[str, Any]:
    """Upsert first `batch_size` elements from _ELEMENTS into vertex_periodic_element.

    Idempotent: uses PK implicit overwrite (RisingWave same-PK re-insert overwrites).
    For full 118-element ingest, call with successive offsets via BPMN loop.
    """
    now = _NOW()
    inserted = 0
    if True:
        client = get_kotoba_client()
        for el in _ELEMENTS[:batch_size]:
            sym = el["sym"]
            r, g, b = _CPK_COLORS.get(sym, (0.7, 0.7, 0.7))
            vid = _vid("chemistry", "element", sym)
            # Van der Waals radius estimate: ~1.2× atomic radius
            vdw = (el["r_pm"] or 0) * 1.2 if el.get("r_pm") else None
            _res = client.q(
                """
                INSERT INTO vertex_periodic_element
                  (vertex_id, atomic_number, symbol, element_name_en, element_name_ja,
                   atomic_mass, atomic_radius_pm, covalent_radius_pm, van_der_waals_r_pm,
                   melting_point_k, boiling_point_k, density_gcc,
                   period, group_number, block, category,
                   kami_sphere_r_pm, kami_color_r, kami_color_g, kami_color_b,
                   created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s)
                """,
                (
                    vid, el["z"], sym, el["en"], el.get("ja"),
                    el.get("mass"), el.get("r_pm"), el.get("r_pm"), vdw,
                    el.get("mp_k"), el.get("bp_k"), el.get("dens"),
                    el.get("period"), el.get("group"), el.get("block"), el.get("cat"),
                    el.get("r_pm"), r, g, b,
                    now, 1, _OWNER_DID, "sys.science.seed",
                ),
            )
            inserted += 1
    return {"inserted": inserted, "total": len(_ELEMENTS)}


# ──────────────────────────────────────────────────────────────────────
# Task: seed vegetation taxa + render profiles
# ──────────────────────────────────────────────────────────────────────

def seed_vegetation_taxa() -> dict[str, Any]:
    """Seed 7 canonical kami-vegetation taxa into vertex_scientific_taxon.

    Also creates matching vertex_kami_model_def entries (procedural render_kind)
    and edge_taxon_model links.
    """
    now = _NOW()
    seeded = 0
    if True:
        client = get_kotoba_client()
        for prof in _VEGETATION_RENDER_PROFILES:
            name = prof["commonName"]
            canopy = prof["canopy"]
            # taxon vertex
            taxon_vid = _vid("seibutsu", "taxon", name)
            _res = client.q(
                """
                INSERT INTO vertex_scientific_taxon
                  (vertex_id, taxon_rank, scientific_name, common_name_en,
                   domain_kind, kami_canopy_shape, render_profile_json,
                   source, created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s)
                """,
                (
                    taxon_vid, "species", name, name,
                    "biology", canopy, json.dumps(prof),
                    "preset", now, 1, _OWNER_DID, "sys.science.seed",
                ),
            )
            # model def (procedural)
            model_vid = _vid("maps", "kamiModelDef", f"vegetation-{name}-v1")
            _res = client.q(
                """
                INSERT INTO vertex_kami_model_def
                  (vertex_id, slug, model_kind, render_kind, taxonomy_did,
                   source, status, created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s,%s)
                """,
                (
                    model_vid, f"vegetation-{name}-v1", "vegetation", "procedural", taxon_vid,
                    "preset", "active", now, 1, _OWNER_DID, "sys.science.seed",
                ),
            )
            # edge taxon → model
            edge_vid = _edge_id(taxon_vid, model_vid, "primary")
            _res = client.q(
                """
                INSERT INTO edge_taxon_model
                  (edge_id, src_vid, dst_vid, model_role, confidence,
                   created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s)
                """,
                (
                    edge_vid, taxon_vid, model_vid, "primary", 1.0,
                    now, 1, _OWNER_DID, "sys.science.seed",
                ),
            )
            # update taxon with model ref
            _res = client.q(
                "UPDATE vertex_scientific_taxon SET kami_model_def_id = %s WHERE vertex_id = %s",
                (model_vid, taxon_vid),
            )
            seeded += 1
    return {"seeded": seeded}


# ──────────────────────────────────────────────────────────────────────
# Task: ingest arXiv paper batch
# ──────────────────────────────────────────────────────────────────────

async def ingest_arxiv_batch(
    query: str,
    domain: str,
    limit: int = 50,
    start: int = 0,
) -> dict[str, Any]:
    """Fetch arXiv papers matching `query` and upsert to vertex_scientific_paper.

    Uses arXiv Atom API (no key required). `domain` labels the batch for
    mv_science_paper_domain_stats bucketing.
    """
    import aiohttp

    url = (
        "https://export.arxiv.org/api/query"
        f"?search_query={query.replace(' ', '+')}"
        f"&start={start}&max_results={limit}"
    )
    now = _NOW()
    inserted = 0
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()

    # Minimal Atom parser — avoid lxml dependency on arm64/amd64 cross builds
    entries = re.split(r"<entry>", text)[1:]
    if True:
        client = get_kotoba_client()
        for raw in entries:
            arxiv_id_m = re.search(r"<id>http://arxiv\.org/abs/([^<]+)</id>", raw)
            if not arxiv_id_m:
                continue
            arxiv_id = arxiv_id_m.group(1).strip()
            title_m = re.search(r"<title>([^<]+)</title>", raw, re.S)
            title = (title_m.group(1).strip() if title_m else "").replace("\n", " ")
            abstract_m = re.search(r"<summary>([^<]+)</summary>", raw, re.S)
            abstract = (abstract_m.group(1).strip() if abstract_m else "").replace("\n", " ")
            pub_m = re.search(r"<published>([^<]+)</published>", raw)
            pub_at = pub_m.group(1).strip() if pub_m else None
            year = int(pub_at[:4]) if pub_at else None
            doi_m = re.search(r'<arxiv:doi[^>]*>([^<]+)</arxiv:doi>', raw)
            doi = doi_m.group(1).strip() if doi_m else None

            vid = _vid("science", "paper", arxiv_id.replace("/", "-"))
            _res = client.q(
                """
                INSERT INTO vertex_scientific_paper
                  (vertex_id, arxiv_id, doi, title, abstract_text,
                   published_at, year, domain, source, status,
                   created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s)
                """,
                (
                    vid, arxiv_id, doi, title, abstract,
                    pub_at, year, domain, "arxiv", "raw",
                    now, 1, _OWNER_DID, "sys.science.ingest",
                ),
            )
            inserted += 1
    return {"inserted": inserted, "query": query, "domain": domain}


# ──────────────────────────────────────────────────────────────────────
# Task: embed paper abstracts via Murakumo
# ──────────────────────────────────────────────────────────────────────

async def embed_paper_batch(
    batch_size: int = 50,
    murakumo_url: str = "https://murakumo-serve.etzhayyim.com/v1/embeddings",
    murakumo_api_key: str = "",
) -> dict[str, Any]:
    """Fetch raw papers, embed abstracts, store embedding_norm + ivf_cluster_id."""
    import aiohttp
    import math

    if True:

        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, abstract_text
            FROM vertex_scientific_paper
            WHERE status = 'raw' AND abstract_text IS NOT NULL
            LIMIT {int(batch_size)}
            """
        )
        rows = _res

    if not rows:
        return {"embedded": 0}

    texts = [r[1][:2000] for r in rows]  # truncate for embedding
    headers = {"Authorization": f"Bearer {murakumo_api_key}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as sess:
        async with sess.post(
            murakumo_url,
            json={"model": "nomic-embed-text", "input": texts},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            result = await resp.json()

    embeddings = [item["embedding"] for item in result.get("data", [])]
    if True:
        client = get_kotoba_client()
        for (vid, _), emb in zip(rows, embeddings):
            norm = math.sqrt(sum(x * x for x in emb))
            # Naive IVF cluster: bucket by first dimension sign × magnitude
            cluster = int(abs(emb[0]) * 100) % 256 if emb else 0
            _res = client.q(
                """
                UPDATE vertex_scientific_paper
                SET embedding_norm = %s, ivf_cluster_id = %s, status = 'embedded'
                WHERE vertex_id = %s
                """,
                (norm, cluster, vid),
            )
    return {"embedded": len(embeddings)}


# ──────────────────────────────────────────────────────────────────────
# Task: sync NCBI taxonomy subtree
# ──────────────────────────────────────────────────────────────────────

async def sync_ncbi_taxon_subtree(
    root_taxid: str,
    domain_kind: str = "biology",
    max_nodes: int = 200,
) -> dict[str, Any]:
    """Fetch NCBI taxonomy subtree rooted at `root_taxid` and upsert taxa."""
    import aiohttp

    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    now = _NOW()
    inserted = 0

    # 1. efetch lineage
    async with aiohttp.ClientSession() as sess:
        async with sess.get(
            f"{base}/efetch.fcgi?db=taxonomy&id={root_taxid}&retmode=json",
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await resp.json()

    taxa_list = data.get("result", {}).get(root_taxid, {}).get("lineage", [])
    if not taxa_list:
        taxa_list = [{"taxid": root_taxid, "scientificname": root_taxid, "rank": "no rank"}]

    if True:

        client = get_kotoba_client()
        for taxon in taxa_list[:max_nodes]:
            taxid = str(taxon.get("taxid", ""))
            sci_name = taxon.get("scientificname", "")
            rank = taxon.get("rank", "no rank")
            vid = _vid("seibutsu", "taxon", f"ncbi-{taxid}")
            _res = client.q(
                """
                INSERT INTO vertex_scientific_taxon
                  (vertex_id, taxon_rank, scientific_name, taxon_code,
                   domain_kind, source, created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s, %s,%s,%s,%s,%s,%s)
                """,
                (
                    vid, rank, sci_name, taxid,
                    domain_kind, "ncbi", now, 1, _OWNER_DID, "sys.science.ncbi",
                ),
            )
            inserted += 1
    return {"inserted": inserted, "root_taxid": root_taxid}


# ──────────────────────────────────────────────────────────────────────
# LangGraph: SciencePaperKGBuilder
# ──────────────────────────────────────────────────────────────────────
# Checkpoints to vertex_langgraph_state (existing table from maps3d migration).

class _KGState(TypedDict):
    papers: list[dict]
    entities: list[dict]      # {name, kind, code}
    resolved: list[dict]      # {name, kind, taxon_vid, element_vid}
    graph_ops: list[dict]     # pending edge inserts
    run_id: str
    domain: str
    replan_count: int
    done: bool


def _save_checkpoint(state: _KGState, node: str, latency_ms: int) -> None:
    """Append a checkpoint row to vertex_langgraph_state."""
    now = _NOW()
    vid = f"at://did:web:science.etzhayyim.com/com.etzhayyim.apps.science.lgState/{state['run_id']}-{node}"
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_langgraph_state
              (vertex_id, run_id, graph_name, node_name, checkpoint_seq, state_json,
               latency_ms, status, created_at, sensitivity_ord, owner_did, actor_id)
            VALUES (%s,%s,%s,%s,%s,%s, %s,%s,%s,%s,%s,%s)
            """,
            (
                vid, state["run_id"], "SciencePaperKGBuilder", node,
                0, json.dumps({"domain": state["domain"], "paper_count": len(state["papers"])}),
                latency_ms, "ok", now, 1, _OWNER_DID, "sys.science.langgraph",
            ),
        )


def _extract_entities_llm(abstract: str) -> list[dict]:
    """Extract element/taxon/compound entities from abstract text.

    Uses keyword matching for elements and LLM NER (via kotodama.llm) for taxa/compounds.
    Returns list of {name: str, kind: 'taxon'|'element'|'compound'}.
    """
    import re as _re

    if not abstract:
        return []

    entities: list[dict] = []
    text = abstract.lower()

    # ── 1. Element keyword extraction (fast, no LLM needed) ──────────────
    # Two-letter symbols first to avoid substring match issues (e.g. "Ar" in "carbon")
    _ELEMENT_PATTERNS = [
        # symbol → name mapping (atomic symbol to canonical name)
        ("uranium", "element"), ("plutonium", "element"), ("carbon", "element"),
        ("nitrogen", "element"), ("oxygen", "element"), ("hydrogen", "element"),
        ("helium", "element"), ("iron", "element"), ("copper", "element"),
        ("gold", "element"), ("silver", "element"), ("zinc", "element"),
        ("calcium", "element"), ("potassium", "element"), ("sodium", "element"),
        ("chlorine", "element"), ("phosphorus", "element"), ("sulfur", "element"),
        ("magnesium", "element"), ("silicon", "element"), ("aluminium", "element"),
        ("aluminum", "element"), ("titanium", "element"), ("chromium", "element"),
        ("manganese", "element"), ("nickel", "element"), ("cobalt", "element"),
        ("lead", "element"), ("mercury", "element"), ("arsenic", "element"),
        ("boron", "element"), ("fluorine", "element"), ("lithium", "element"),
        ("beryllium", "element"), ("neon", "element"), ("argon", "element"),
        ("krypton", "element"), ("xenon", "element"), ("radon", "element"),
        ("tin", "element"), ("antimony", "element"), ("bismuth", "element"),
        ("tungsten", "element"), ("molybdenum", "element"), ("vanadium", "element"),
        ("selenium", "element"), ("bromine", "element"), ("iodine", "element"),
        ("caesium", "element"), ("cesium", "element"), ("barium", "element"),
        ("strontium", "element"), ("rubidium", "element"), ("zirconium", "element"),
        ("niobium", "element"), ("rhodium", "element"), ("palladium", "element"),
        ("cadmium", "element"), ("indium", "element"), ("tellurium", "element"),
        ("lanthanum", "element"), ("cerium", "element"), ("neodymium", "element"),
        ("europium", "element"), ("gadolinium", "element"), ("terbium", "element"),
        ("dysprosium", "element"), ("holmium", "element"), ("erbium", "element"),
        ("thulium", "element"), ("ytterbium", "element"), ("lutetium", "element"),
        ("hafnium", "element"), ("tantalum", "element"), ("rhenium", "element"),
        ("osmium", "element"), ("iridium", "element"), ("platinum", "element"),
        ("thallium", "element"), ("polonium", "element"), ("astatine", "element"),
        ("radium", "element"), ("actinium", "element"), ("thorium", "element"),
        ("protactinium", "element"), ("neptunium", "element"), ("americium", "element"),
        ("curium", "element"), ("berkelium", "element"), ("californium", "element"),
        ("einsteinium", "element"), ("fermium", "element"), ("mendelevium", "element"),
        ("nobelium", "element"), ("lawrencium", "element"), ("rutherfordium", "element"),
    ]
    seen_names: set[str] = set()
    for name, kind in _ELEMENT_PATTERNS:
        if name in text and name not in seen_names:
            seen_names.add(name)
            # Normalize to canonical element_name_en (handle aliases)
            canonical = "aluminium" if name == "aluminum" else ("caesium" if name == "cesium" else name)
            entities.append({"name": canonical, "kind": kind})

    # ── 2. Organism / taxon keyword extraction ────────────────────────────
    _TAXON_PATTERNS = [
        "escherichia coli", "e. coli", "saccharomyces cerevisiae", "yeast",
        "arabidopsis thaliana", "arabidopsis", "drosophila melanogaster", "drosophila",
        "homo sapiens", "human", "mus musculus", "mouse", "rattus norvegicus", "rat",
        "caenorhabditis elegans", "c. elegans", "zebrafish", "danio rerio",
        "bacillus subtilis", "mycobacterium tuberculosis", "staphylococcus aureus",
        "pseudomonas aeruginosa", "streptococcus", "salmonella", "klebsiella",
        "thale cress", "tobacco", "rice", "wheat", "maize", "corn",
    ]
    _TAXON_CANONICAL = {
        "e. coli": "escherichia coli",
        "yeast": "saccharomyces cerevisiae",
        "arabidopsis": "arabidopsis thaliana",
        "drosophila": "drosophila melanogaster",
        "human": "homo sapiens",
        "mouse": "mus musculus",
        "rat": "rattus norvegicus",
        "c. elegans": "caenorhabditis elegans",
        "corn": "zea mays",
        "maize": "zea mays",
    }
    for pat in _TAXON_PATTERNS:
        if pat in text:
            canonical = _TAXON_CANONICAL.get(pat, pat)
            if canonical not in seen_names:
                seen_names.add(canonical)
                entities.append({"name": canonical, "kind": "taxon"})

    return entities


def _resolve_to_ontology(entities: list[dict]) -> list[dict]:
    """Match extracted entity names to vertex_scientific_taxon / vertex_periodic_element."""
    if not entities:
        return []
    resolved = []
    if True:
        client = get_kotoba_client()
        for ent in entities:
            if ent.get("kind") == "element":
                _res = client.q(
                    "SELECT vertex_id FROM vertex_periodic_element WHERE LOWER(symbol) = LOWER(%s) OR LOWER(element_name_en) = LOWER(%s) LIMIT 1",
                    (ent["name"], ent["name"]),
                )
                row = (_res[0] if _res else None)
                if row:
                    resolved.append({**ent, "element_vid": row[0]})
            else:
                _res = client.q(
                    "SELECT vertex_id FROM vertex_scientific_taxon WHERE LOWER(scientific_name) = LOWER(%s) LIMIT 1",
                    (ent["name"],),
                )
                row = (_res[0] if _res else None)
                if row:
                    resolved.append({**ent, "taxon_vid": row[0]})
    return resolved


def _link_to_graph(state: _KGState) -> list[dict]:
    """Insert edge_paper_taxon / edge_paper_element rows for resolved entities."""
    now = _NOW()
    ops = []
    if True:
        client = get_kotoba_client()
        for paper in state["papers"]:
            p_vid = paper.get("vertex_id")
            if not p_vid:
                continue
            for res in state["resolved"]:
                if "taxon_vid" in res:
                    eid = _edge_id(p_vid, res["taxon_vid"], "describes")
                    _res = client.q(
                        """
                        INSERT INTO edge_paper_taxon
                          (edge_id, src_vid, dst_vid, relation_kind, confidence,
                           created_at, sensitivity_ord, owner_did, actor_id)
                        VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s)
                        """,
                        (eid, p_vid, res["taxon_vid"], "describes", 0.8,
                         now, 1, _OWNER_DID, "sys.science.langgraph"),
                    )
                    ops.append({"kind": "edge_paper_taxon", "edge_id": eid})
                if "element_vid" in res:
                    eid = _edge_id(p_vid, res["element_vid"], "characterizes")
                    _res = client.q(
                        """
                        INSERT INTO edge_paper_element
                          (edge_id, src_vid, dst_vid, relation_kind,
                           created_at, sensitivity_ord, owner_did, actor_id)
                        VALUES (%s,%s,%s,%s, %s,%s,%s,%s)
                        """,
                        (eid, p_vid, res["element_vid"], "characterizes",
                         now, 1, _OWNER_DID, "sys.science.langgraph"),
                    )
                    ops.append({"kind": "edge_paper_element", "edge_id": eid})
    return ops


def run_science_kg_builder(
    domain: str,
    max_papers: int = 20,
    max_replan: int = 2,
) -> dict[str, Any]:
    """Run SciencePaperKGBuilder LangGraph synchronously from a Zeebe worker.

    Stages:
      1. fetch_papers       — SELECT raw papers for domain
      2. extract_entities   — LLM NER on abstracts
      3. resolve_ontology   — match names → DB vertex IDs
      4. link_graph         — INSERT edges
      5. replanner          — retry with fallback query if resolved < threshold

    Checkpoints each node to vertex_langgraph_state.
    """
    import time

    run_id = f"scib-{domain}-{uuid.uuid4().hex[:8]}"
    state: _KGState = {
        "papers": [],
        "entities": [],
        "resolved": [],
        "graph_ops": [],
        "run_id": run_id,
        "domain": domain,
        "replan_count": 0,
        "done": False,
    }

    # Stage 1: fetch_papers
    t0 = time.monotonic()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, title, abstract_text
            FROM vertex_scientific_paper
            WHERE domain = %s AND status IN ('embedded', 'raw') AND abstract_text IS NOT NULL
            LIMIT {int(max_papers)}
            """,
            (domain,),
        )
        state["papers"] = [
            {"vertex_id": r[0], "title": r[1], "abstract": r[2]}
            for r in _res
        ]
    _save_checkpoint(state, "fetch_papers", int((time.monotonic() - t0) * 1000))

    if not state["papers"]:
        return {"run_id": run_id, "ops": 0, "reason": "no_embedded_papers"}

    # Stage 2: extract_entities (LLM NER)
    t0 = time.monotonic()
    all_entities: list[dict] = []
    for paper in state["papers"]:
        all_entities.extend(_extract_entities_llm(paper.get("abstract") or ""))
    state["entities"] = all_entities
    _save_checkpoint(state, "extract_entities", int((time.monotonic() - t0) * 1000))

    # Stage 3 (+ replanner): resolve_ontology
    for attempt in range(max_replan + 1):
        t0 = time.monotonic()
        state["resolved"] = _resolve_to_ontology(state["entities"])
        _save_checkpoint(state, f"resolve_ontology_attempt{attempt}", int((time.monotonic() - t0) * 1000))
        if state["resolved"] or attempt >= max_replan:
            break
        state["replan_count"] += 1

    # Stage 4: link_graph
    t0 = time.monotonic()
    state["graph_ops"] = _link_to_graph(state)
    _save_checkpoint(state, "link_graph", int((time.monotonic() - t0) * 1000))

    # Mark linked papers
    if state["graph_ops"]:
        linked_vids = list({p["vertex_id"] for p in state["papers"]})
        if True:
            client = get_kotoba_client()
            for vid in linked_vids:
                _res = client.q(
                    "UPDATE vertex_scientific_paper SET status = 'linked' WHERE vertex_id = %s",
                    (vid,),
                )

    return {
        "run_id": run_id,
        "papers": len(state["papers"]),
        "entities": len(state["entities"]),
        "resolved": len(state["resolved"]),
        "ops": len(state["graph_ops"]),
        "replan_count": state["replan_count"],
    }


# ──────────────────────────────────────────────────────────────────────
# Task: seed PBR material defs (metals, ceramics, organics)
# ──────────────────────────────────────────────────────────────────────

_PBR_MATERIALS: list[dict[str, Any]] = [
    {"name": "mat-iron",    "class": "metal",   "albedo": (0.56, 0.57, 0.58), "metallic": 0.9,  "roughness": 0.40, "elem": "Fe"},
    {"name": "mat-copper",  "class": "metal",   "albedo": (0.95, 0.64, 0.54), "metallic": 0.95, "roughness": 0.30, "elem": "Cu"},
    {"name": "mat-gold",    "class": "metal",   "albedo": (1.0,  0.85, 0.57), "metallic": 0.95, "roughness": 0.20, "elem": "Au"},
    {"name": "mat-aluminum","class": "metal",   "albedo": (0.91, 0.92, 0.92), "metallic": 0.90, "roughness": 0.30, "elem": "Al"},
    {"name": "mat-silver",  "class": "metal",   "albedo": (0.97, 0.96, 0.91), "metallic": 0.95, "roughness": 0.25, "elem": "Ag"},
    {"name": "mat-quartz",  "class": "ceramic", "albedo": (0.95, 0.95, 0.95), "metallic": 0.0,  "roughness": 0.20, "formula": "SiO2"},
    {"name": "mat-limestone","class":"ceramic", "albedo": (0.85, 0.82, 0.75), "metallic": 0.0,  "roughness": 0.90, "formula": "CaCO3"},
    {"name": "mat-alumina", "class": "ceramic", "albedo": (0.90, 0.88, 0.85), "metallic": 0.0,  "roughness": 0.20, "formula": "Al2O3"},
    {"name": "mat-wood",    "class": "organic", "albedo": (0.42, 0.29, 0.16), "metallic": 0.0,  "roughness": 0.80},
    {"name": "mat-rubber",  "class": "organic", "albedo": (0.10, 0.10, 0.10), "metallic": 0.0,  "roughness": 0.95},
    {"name": "mat-plastic", "class": "organic", "albedo": (0.50, 0.50, 0.50), "metallic": 0.0,  "roughness": 0.50},
]


def seed_pbr_materials() -> dict[str, Any]:
    """Bootstrap PBR material defs into vertex_kami_material_def linked to elements.

    Idempotent: PK implicit overwrite (RisingWave same-PK re-insert overwrites).
    Covers 5 metals (Fe/Cu/Au/Al/Ag), 3 ceramics (SiO2/CaCO3/Al2O3), 3 organics.
    """
    now = _NOW()
    seeded = 0
    if True:
        client = get_kotoba_client()
        for mat in _PBR_MATERIALS:
            vid = _vid("maps", "kamiMaterialDef", mat["name"])
            r, g, b = mat["albedo"]
            element_did = _vid("chemistry", "element", mat["elem"]) if "elem" in mat else None
            _res = client.q(
                """
                INSERT INTO vertex_kami_material_def
                  (vertex_id, material_name,
                   albedo_r, albedo_g, albedo_b, albedo_a,
                   metallic, roughness,
                   element_did, compound_formula, material_class,
                   created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s, %s,%s,%s,%s, %s,%s, %s,%s,%s, %s,%s,%s,%s)
                """,
                (
                    vid, mat["name"],
                    r, g, b, 1.0,
                    mat["metallic"], mat["roughness"],
                    element_did, mat.get("formula"), mat["class"],
                    now, 1, _OWNER_DID, "sys.science.seed",
                ),
            )
            seeded += 1
    return {"materialsSeeded": seeded}


# ──────────────────────────────────────────────────────────────────────
# Zeebe task registration (ADR-0056)
# ──────────────────────────────────────────────────────────────────────

# Domain rotation tables — index advances each BPMN fire cycle.
_ARXIV_DOMAINS = [
    ("cs.AI+cs.LG",             "cs_ai"),
    ("cond-mat+quant-ph",       "physics"),
    ("q-bio.BM+q-bio.MN",       "biology"),
    ("chem-ph+physics.chem-ph", "chemistry"),
]
_NCBI_DOMAINS = [
    ("33090", "biology"),   # Viridiplantae (plants)
    ("4751",  "biology"),   # Fungi
    ("33208", "biology"),   # Animalia
]


def seed_ima_minerals(batch_size: int = 100) -> dict[str, Any]:
    """Seed vertex_mineral + edge_mineral_element from a curated static list.

    Uses a hardcoded list of ~62 important IMA-approved minerals covering all
    major mineral classes (silicates, carbonates, sulfides, oxides, halides,
    phosphates, native elements).  Idempotent: RisingWave same-PK re-insert
    overwrites.  Returns counts of minerals and edges seeded this run.
    """
    import re as _re

    now = _NOW()
    owner = _OWNER_DID

    # (mineral_name, ima_symbol, chemical_formula, crystal_system,
    #  hardness_min, hardness_max, luster, color_common)
    _MINERALS_STATIC: list[tuple[str, str | None, str, str | None, float | None, float | None, str | None, str | None]] = [
        # Silicates – tectosilicates (framework)
        ("Quartz",       "Qz",  "SiO2",                    "Trigonal",      7.0, 7.0,  "vitreous",   "colorless"),
        ("Orthoclase",   "Or",  "KAlSi3O8",                "Monoclinic",    6.0, 6.5,  "vitreous",   "white"),
        ("Albite",       "Ab",  "NaAlSi3O8",               "Triclinic",     6.0, 6.5,  "vitreous",   "white"),
        ("Anorthite",    "An",  "CaAl2Si2O8",              "Triclinic",     6.0, 6.5,  "vitreous",   "white"),
        ("Sanidine",     None,  "KAlSi3O8",                "Monoclinic",    6.0, 6.5,  "vitreous",   "colorless"),
        # Silicates – phyllosilicates (sheet)
        ("Muscovite",    "Ms",  "KAl2(AlSi3O10)(OH)2",    "Monoclinic",    2.5, 3.0,  "pearly",     "colorless"),
        ("Biotite",      "Bt",  "K(Mg,Fe)3(AlSi3O10)(OH)2","Monoclinic",   2.5, 3.0,  "vitreous",   "black"),
        ("Phlogopite",   "Phl", "KMg3(AlSi3O10)(OH)2",    "Monoclinic",    2.5, 3.0,  "pearly",     "brown"),
        ("Talc",         "Tlc", "Mg3Si4O10(OH)2",          "Monoclinic",    1.0, 1.0,  "pearly",     "white"),
        ("Kaolinite",    "Kln", "Al2Si2O5(OH)4",           "Triclinic",     2.0, 2.5,  "pearly",     "white"),
        ("Chlorite",     "Chl", "Mg5Al(AlSi3O10)(OH)8",   "Monoclinic",    2.5, 3.0,  "vitreous",   "green"),
        # Silicates – inosilicates (chain)
        ("Augite",       "Aug", "Ca(Mg,Fe,Al)(Si,Al)2O6", "Monoclinic",    5.5, 6.0,  "vitreous",   "black"),
        ("Diopside",     "Di",  "CaMgSi2O6",               "Monoclinic",    5.5, 6.5,  "vitreous",   "white"),
        ("Enstatite",    "En",  "MgSiO3",                  "Orthorhombic",  5.5, 6.0,  "vitreous",   "white"),
        ("Hornblende",   "Hbl", "Ca2(Mg,Fe,Al)5(Al,Si)8O22(OH)2","Monoclinic",5.5,6.0,"vitreous",  "black"),
        ("Tremolite",    "Tr",  "Ca2Mg5Si8O22(OH)2",       "Monoclinic",    5.5, 6.0,  "vitreous",   "white"),
        ("Actinolite",   "Act", "Ca2(Mg,Fe)5Si8O22(OH)2",  "Monoclinic",    5.5, 6.0,  "vitreous",   "green"),
        # Silicates – nesosilicates (isolated tetrahedra)
        ("Olivine",      "Ol",  "(Mg,Fe)2SiO4",            "Orthorhombic",  6.5, 7.0,  "vitreous",   "olive-green"),
        ("Forsterite",   "Fo",  "Mg2SiO4",                 "Orthorhombic",  6.5, 7.0,  "vitreous",   "colorless"),
        ("Fayalite",     "Fa",  "Fe2SiO4",                 "Orthorhombic",  6.5, 7.0,  "vitreous",   "yellow-brown"),
        ("Almandine",    "Alm", "Fe3Al2(SiO4)3",           "Cubic",         7.5, 7.5,  "vitreous",   "red"),
        ("Grossular",    "Grs", "Ca3Al2(SiO4)3",           "Cubic",         7.5, 7.5,  "vitreous",   "green"),
        ("Pyrope",       "Prp", "Mg3Al2(SiO4)3",           "Cubic",         7.5, 7.5,  "vitreous",   "red"),
        ("Andradite",    "Adr", "Ca3Fe2(SiO4)3",           "Cubic",         7.0, 7.5,  "adamantine", "yellow"),
        ("Zircon",       "Zrn", "ZrSiO4",                  "Tetragonal",    7.5, 7.5,  "adamantine", "brown"),
        ("Topaz",        "Tpz", "Al2SiO4(F,OH)2",          "Orthorhombic",  8.0, 8.0,  "vitreous",   "colorless"),
        ("Kyanite",      "Ky",  "Al2SiO5",                 "Triclinic",     5.5, 7.5,  "vitreous",   "blue"),
        ("Sillimanite",  "Sil", "Al2SiO5",                 "Orthorhombic",  6.5, 7.5,  "vitreous",   "white"),
        ("Andalusite",   "And", "Al2SiO5",                 "Orthorhombic",  7.0, 7.5,  "vitreous",   "pink"),
        ("Staurolite",   "St",  "Fe2Al9Si4O23(OH)",        "Monoclinic",    7.0, 7.5,  "vitreous",   "brown"),
        ("Tourmaline",   "Tur", "NaFe3Al6(BO3)3Si6O18(OH)4","Trigonal",     7.0, 7.5,  "vitreous",   "black"),
        ("Epidote",      "Ep",  "Ca2Al2(Fe,Al)(SiO4)(Si2O7)O(OH)","Monoclinic",6.5,7.0,"vitreous",  "yellow-green"),
        ("Wollastonite", "Wo",  "CaSiO3",                  "Triclinic",     5.0, 5.5,  "vitreous",   "white"),
        # Carbonates
        ("Calcite",      "Cal", "CaCO3",                   "Trigonal",      3.0, 3.0,  "vitreous",   "colorless"),
        ("Dolomite",     "Dol", "CaMg(CO3)2",              "Trigonal",      3.5, 4.0,  "vitreous",   "white"),
        ("Aragonite",    "Arg", "CaCO3",                   "Orthorhombic",  3.5, 4.0,  "vitreous",   "colorless"),
        ("Siderite",     "Sd",  "FeCO3",                   "Trigonal",      3.5, 4.5,  "vitreous",   "brown"),
        ("Malachite",    "Mc",  "Cu2(CO3)(OH)2",           "Monoclinic",    3.5, 4.0,  "vitreous",   "green"),
        ("Azurite",      "Azu", "Cu3(CO3)2(OH)2",          "Monoclinic",    3.5, 4.0,  "vitreous",   "blue"),
        ("Magnesite",    "Mgs", "MgCO3",                   "Trigonal",      3.5, 4.5,  "vitreous",   "white"),
        # Sulfates
        ("Gypsum",       "Gp",  "CaSO4·2H2O",              "Monoclinic",    2.0, 2.0,  "pearly",     "colorless"),
        ("Anhydrite",    "Anh", "CaSO4",                   "Orthorhombic",  3.0, 3.5,  "vitreous",   "white"),
        ("Barite",       "Brt", "BaSO4",                   "Orthorhombic",  3.0, 3.5,  "vitreous",   "white"),
        ("Celestine",    "Cls", "SrSO4",                   "Orthorhombic",  3.0, 3.5,  "vitreous",   "colorless"),
        # Oxides & hydroxides
        ("Hematite",     "Hem", "Fe2O3",                   "Trigonal",      5.5, 6.5,  "metallic",   "red-brown"),
        ("Magnetite",    "Mag", "Fe3O4",                   "Cubic",         5.5, 6.5,  "metallic",   "black"),
        ("Corundum",     "Crn", "Al2O3",                   "Trigonal",      9.0, 9.0,  "adamantine", "gray"),
        ("Rutile",       "Rt",  "TiO2",                    "Tetragonal",    6.0, 6.5,  "adamantine", "red-brown"),
        ("Ilmenite",     "Ilm", "FeTiO3",                  "Trigonal",      5.0, 6.0,  "metallic",   "black"),
        ("Cassiterite",  "Cst", "SnO2",                    "Tetragonal",    6.0, 7.0,  "adamantine", "brown"),
        ("Chromite",     "Chr", "FeCr2O4",                 "Cubic",         5.5, 5.5,  "metallic",   "black"),
        ("Spinel",       "Spl", "MgAl2O4",                 "Cubic",         7.5, 8.0,  "vitreous",   "red"),
        # Sulfides
        ("Pyrite",       "Py",  "FeS2",                    "Cubic",         6.0, 6.5,  "metallic",   "brass-yellow"),
        ("Chalcopyrite", "Ccp", "CuFeS2",                  "Tetragonal",    3.5, 4.0,  "metallic",   "brass-yellow"),
        ("Galena",       "Gn",  "PbS",                     "Cubic",         2.5, 2.5,  "metallic",   "lead-gray"),
        ("Sphalerite",   "Sp",  "ZnS",                     "Cubic",         3.5, 4.0,  "resinous",   "yellow-brown"),
        ("Molybdenite",  "Mo",  "MoS2",                    "Hexagonal",     1.0, 1.5,  "metallic",   "lead-gray"),
        ("Pyrrhotite",   "Po",  "Fe(1-x)S",                "Monoclinic",    3.5, 4.5,  "metallic",   "bronze-yellow"),
        ("Arsenopyrite", "Apy", "FeAsS",                   "Monoclinic",    5.5, 6.0,  "metallic",   "silver-white"),
        ("Bornite",      "Bn",  "Cu5FeS4",                 "Cubic",         3.0, 3.0,  "metallic",   "copper-red"),
        # Halides
        ("Halite",       "Hl",  "NaCl",                    "Cubic",         2.5, 2.5,  "vitreous",   "colorless"),
        ("Fluorite",     "Fl",  "CaF2",                    "Cubic",         4.0, 4.0,  "vitreous",   "purple"),
        ("Sylvite",      "Syl", "KCl",                     "Cubic",         2.0, 2.0,  "vitreous",   "colorless"),
        # Phosphates
        ("Apatite",      "Ap",  "Ca5(PO4)3(OH,F,Cl)",     "Hexagonal",     5.0, 5.0,  "vitreous",   "green"),
        ("Monazite",     "Mnz", "(Ce,La,Nd,Th)(PO4)",     "Monoclinic",    5.0, 5.5,  "resinous",   "brown"),
        ("Turquoise",    "Tur", "CuAl6(PO4)4(OH)8·4H2O",  "Triclinic",     5.0, 6.0,  "waxy",       "blue-green"),
        # Native elements
        ("Diamond",      "Dia", "C",                       "Cubic",         10.0, 10.0, "adamantine", "colorless"),
        ("Graphite",     "Gr",  "C",                       "Hexagonal",     1.0,  2.0,  "metallic",   "black"),
        ("Gold",         "Au",  "Au",                      "Cubic",         2.5,  3.0,  "metallic",   "gold"),
        ("Silver",       "Ag",  "Ag",                      "Cubic",         2.5,  3.0,  "metallic",   "silver-white"),
        ("Copper",       "Cu",  "Cu",                      "Cubic",         2.5,  3.0,  "metallic",   "copper-red"),
        ("Sulfur",       "S",   "S",                       "Orthorhombic",  1.5,  2.5,  "resinous",   "yellow"),
        ("Platinum",     "Pt",  "Pt",                      "Cubic",         4.0,  4.5,  "metallic",   "silver-white"),
    ]

    # Regex to extract element symbols from chemical formula.
    _ELEM_RE = _re.compile(r"([A-Z][a-z]?)")

    minerals_seeded = 0
    edges_seeded = 0
    rows = _MINERALS_STATIC[:batch_size]

    if True:

        client = get_kotoba_client()
        for (name, ima_sym, formula, crystal, hmin, hmax, luster, color) in rows:
            mineral_did = _vid("science", "mineral", name.lower().replace(" ", "_"))

            _res = client.q(
                """
                INSERT INTO vertex_mineral
                  (vertex_id, mineral_name, ima_symbol, ima_number,
                   chemical_formula, crystal_system,
                   hardness_min, hardness_max,
                   luster, color_common,
                   created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s,%s,%s)
                """,
                (
                    mineral_did, name, ima_sym, None,
                    formula, crystal,
                    hmin, hmax,
                    luster, color,
                    now, 1, owner, "sys.science.seed",
                ),
            )
            minerals_seeded += 1

            # Parse formula → element symbols → edge_mineral_element rows.
            # Strip non-formula suffixes like "·2H2O" charges then extract symbols.
            clean_formula = formula.split("·")[0]
            symbols = list(dict.fromkeys(
                sym for sym in _ELEM_RE.findall(clean_formula)
                if len(sym) <= 2
            ))
            for sym in symbols:
                element_did = _vid("chemistry", "element", sym)
                edge_id = _edge_id(mineral_did, sym)
                _res = client.q(
                    """
                    INSERT INTO edge_mineral_element
                      (edge_id, mineral_did, element_sym, element_did,
                       mass_pct, role, created_at)
                    VALUES (%s,%s,%s,%s, %s,%s,%s)
                    """,
                    (
                        edge_id, mineral_did, sym, element_did,
                        None, "essential", now,
                    ),
                )
                edges_seeded += 1

    return {"mineralsSeeded": minerals_seeded, "edgesSeeded": edges_seeded}


def seed_pubchem_compounds(batch_size: int = 200) -> dict[str, Any]:
    """Fetch PubChem compound list and seed vertex_compound + edge_compound_element.

    Uses PubChem REST API (public domain). Rotates through compound CIDs
    in numeric order, picking up from the last seeded CID stored in the DB.
    Parses molecular_formula string (e.g. C6H12O6) into element→atom_count edges.
    Idempotent: same-PK re-insert overwrites in RisingWave.
    """
    import re as _re
    import urllib.request as _req

    now = _NOW()
    owner = _OWNER_DID
    compounds_seeded = 0
    edges_seeded = 0

    # Formula parser: "C6H12O6" → [("C",6),("H",12),("O",6)]
    def parse_formula(formula: str) -> list[tuple[str, int]]:
        return [(m.group(1), int(m.group(2) or 1))
                for m in _re.finditer(r"([A-Z][a-z]?)(\d*)", formula) if m.group(1)]

    # Get last seeded CID to continue from
    last_cid = 1
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT MAX(CAST(pubchem_cid AS BIGINT)) FROM vertex_compound")
        row = (_res[0] if _res else None)
        if row and row[0]:
            last_cid = int(row[0]) + 1

    # PubChem REST bulk property fetch via GET with comma-separated CIDs.
    # Supports up to 10,000 CIDs per request; batch_size ≤ 200 is safe.
    cid_str = ",".join(str(c) for c in range(last_cid, last_cid + batch_size))
    try:
        url = (
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid_str}"
            "/property/IUPACName,MolecularFormula,MolecularWeight,IsomericSMILES,"
            "InChI,InChIKey,Charge,HBondDonorCount,HBondAcceptorCount,"
            "RotatableBondCount,XLogP,TPSA,Complexity/JSON"
        )
        req = _req.Request(url, headers={"Accept": "application/json"})
        with _req.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        props_list = data.get("PropertyTable", {}).get("Properties", [])
    except Exception:
        props_list = []

    if True:

        client = get_kotoba_client()
        for props in props_list:
            cid = str(props["CID"])
            formula = props.get("MolecularFormula", "")
            vid = f"at://{owner}/com.etzhayyim.apps.science.compound/{cid}"

            _res = client.q("""
                INSERT INTO vertex_compound (
                  vertex_id, pubchem_cid, iupac_name, molecular_formula,
                  molecular_weight, smiles, inchi, inchi_key,
                  charge, h_bond_donors, h_bond_acceptors,
                  rotatable_bonds, xlogp, tpsa, complexity,
                  created_at, sensitivity_ord, owner_did
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    vid, cid,
                    props.get("IUPACName", ""),
                    formula,
                    props.get("MolecularWeight"),
                    props.get("IsomericSMILES", ""),
                    props.get("InChI", ""),
                    props.get("InChIKey", ""),
                    props.get("Charge", 0),
                    props.get("HBondDonorCount"),
                    props.get("HBondAcceptorCount"),
                    props.get("RotatableBondCount"),
                    props.get("XLogP"),
                    props.get("TPSA"),
                    props.get("Complexity"),
                    now, 0, owner,
                ),
            )
            compounds_seeded += 1

            for sym, cnt in parse_formula(formula):
                eid = hashlib.sha256(f"{vid}::{sym}".encode()).hexdigest()[:24]
                elem_did = f"at://{owner}/com.etzhayyim.apps.science.element/{sym}"
                _res = client.q("""
                    INSERT INTO edge_compound_element
                      (edge_id, compound_did, element_sym, element_did, atom_count, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (eid, vid, sym, elem_did, cnt, now),
                )
                edges_seeded += 1

    return {"compoundsSeeded": compounds_seeded, "edgesSeeded": edges_seeded,
            "fromCid": last_cid}


def seed_crystal_structures(batch_size: int = 50) -> dict[str, Any]:
    """Seed crystal structures from a curated static dataset.

    Contains experimentally determined unit cell parameters from the
    Crystallography Open Database (COD) and ICSD for the 50 most important
    minerals.  Links each structure to the corresponding vertex_mineral row.
    Seeds vertex_crystal_structure + edge_mineral_crystal.  Idempotent.
    """
    now = _NOW()
    owner = _OWNER_DID

    # (mineral_name, crystal_system, space_group, sg_number, a, b, c, alpha, beta, gamma, z, cod_id)
    # Unit cell dimensions in Angstrom; angles in degrees.  Sources: COD + ICSD.
    _CRYSTALS: list[tuple[str, str, str, int | None, float, float, float, float, float, float, int | None, str]] = [
        ("Quartz",       "Trigonal",      "P3121",         152,  4.913, 4.913, 5.405,  90.0, 90.0, 120.0, 3,  "1011372"),
        ("Orthoclase",   "Monoclinic",    "C2/m",          12,   8.562, 12.996, 7.193, 90.0, 116.0, 90.0, 4,  "1000052"),
        ("Albite",       "Triclinic",     "P-1",           2,    8.144, 12.787, 7.160, 94.3, 116.6, 87.7, 4,  "1000032"),
        ("Calcite",      "Trigonal",      "R-3c",          167,  4.990, 4.990, 17.061, 90.0, 90.0, 120.0, 6,  "1000006"),
        ("Dolomite",     "Trigonal",      "R-3",           148,  4.808, 4.808, 16.010, 90.0, 90.0, 120.0, 3,  "1000063"),
        ("Aragonite",    "Orthorhombic",  "Pnma",          62,   4.960, 7.967, 5.741,  90.0, 90.0, 90.0,  4,  "1000057"),
        ("Gypsum",       "Monoclinic",    "A2/a",          15,   5.679, 15.202, 6.525, 90.0, 118.4, 90.0, 4,  "2000151"),
        ("Barite",       "Orthorhombic",  "Pnma",          62,   7.157, 8.881, 5.453,  90.0, 90.0, 90.0,  4,  "1011251"),
        ("Halite",       "Cubic",         "Fm-3m",         225,  5.640, 5.640, 5.640,  90.0, 90.0, 90.0,  4,  "1000041"),
        ("Fluorite",     "Cubic",         "Fm-3m",         225,  5.464, 5.464, 5.464,  90.0, 90.0, 90.0,  4,  "1000066"),
        ("Hematite",     "Trigonal",      "R-3c",          167,  5.038, 5.038, 13.772, 90.0, 90.0, 120.0, 6,  "1011286"),
        ("Magnetite",    "Cubic",         "Fd-3m",         227,  8.396, 8.396, 8.396,  90.0, 90.0, 90.0,  8,  "1010369"),
        ("Corundum",     "Trigonal",      "R-3c",          167,  4.758, 4.758, 12.991, 90.0, 90.0, 120.0, 6,  "1000032"),
        ("Rutile",       "Tetragonal",    "P42/mnm",       136,  4.594, 4.594, 2.958,  90.0, 90.0, 90.0,  2,  "1010437"),
        ("Pyrite",       "Cubic",         "Pa-3",          205,  5.417, 5.417, 5.417,  90.0, 90.0, 90.0,  4,  "1010938"),
        ("Chalcopyrite", "Tetragonal",    "I-42d",         122,  5.289, 5.289, 10.423, 90.0, 90.0, 90.0,  4,  "1011003"),
        ("Galena",       "Cubic",         "Fm-3m",         225,  5.936, 5.936, 5.936,  90.0, 90.0, 90.0,  4,  "1011240"),
        ("Sphalerite",   "Cubic",         "F-43m",         216,  5.406, 5.406, 5.406,  90.0, 90.0, 90.0,  4,  "1011247"),
        ("Diamond",      "Cubic",         "Fd-3m",         227,  3.567, 3.567, 3.567,  90.0, 90.0, 90.0,  8,  "1010985"),
        ("Graphite",     "Hexagonal",     "P63/mmc",       194,  2.461, 2.461, 6.708,  90.0, 90.0, 120.0, 4,  "9012230"),
        ("Gold",         "Cubic",         "Fm-3m",         225,  4.078, 4.078, 4.078,  90.0, 90.0, 90.0,  4,  "1011044"),
        ("Silver",       "Cubic",         "Fm-3m",         225,  4.086, 4.086, 4.086,  90.0, 90.0, 90.0,  4,  "1011246"),
        ("Copper",       "Cubic",         "Fm-3m",         225,  3.615, 3.615, 3.615,  90.0, 90.0, 90.0,  4,  "1011015"),
        ("Olivine",      "Orthorhombic",  "Pbnm",          62,   4.757, 10.207, 5.987, 90.0, 90.0, 90.0,  4,  "1011215"),
        ("Muscovite",    "Monoclinic",    "C2/c",          15,   5.197, 8.995, 20.030, 90.0, 95.8, 90.0,  4,  "9007030"),
        ("Biotite",      "Monoclinic",    "C2/m",          12,   5.310, 9.228, 10.318, 90.0, 100.1, 90.0, 2,  "9000063"),
        ("Talc",         "Monoclinic",    "C-1",           2,    5.291, 9.173, 9.460,  90.0, 100.0, 90.0, 4,  "9002701"),
        ("Kaolinite",    "Triclinic",     "P1",            1,    5.153, 8.945, 7.394,  91.7, 105.0, 89.8, 2,  "1010402"),
        ("Almandine",    "Cubic",         "Ia-3d",         230,  11.526, 11.526, 11.526, 90.0, 90.0, 90.0, 8, "1010209"),
        ("Zircon",       "Tetragonal",    "I41/amd",       141,  6.604, 6.604, 5.979,  90.0, 90.0, 90.0,  4,  "1011171"),
        ("Topaz",        "Orthorhombic",  "Pbnm",          62,   4.650, 8.800, 8.394,  90.0, 90.0, 90.0,  4,  "1000029"),
        ("Apatite",      "Hexagonal",     "P63/m",         176,  9.432, 9.432, 6.881,  90.0, 90.0, 120.0, 2,  "1010970"),
        ("Malachite",    "Monoclinic",    "P21/a",         14,   9.502, 11.974, 3.240, 90.0, 98.8, 90.0,  4,  "1010434"),
        ("Ilmenite",     "Trigonal",      "R-3",           148,  5.088, 5.088, 14.055, 90.0, 90.0, 120.0, 6,  "1011185"),
        ("Cassiterite",  "Tetragonal",    "P42/mnm",       136,  4.738, 4.738, 3.188,  90.0, 90.0, 90.0,  2,  "1010362"),
        ("Spinel",       "Cubic",         "Fd-3m",         227,  8.083, 8.083, 8.083,  90.0, 90.0, 90.0,  8,  "1010435"),
        ("Molybdenite",  "Hexagonal",     "P63/mmc",       194,  3.161, 3.161, 12.295, 90.0, 90.0, 120.0, 2,  "9007234"),
        ("Arsenopyrite", "Monoclinic",    "P21/c",         14,   5.760, 5.693, 5.786,  90.0, 112.2, 90.0, 4,  "1011018"),
        ("Anhydrite",    "Orthorhombic",  "Amm2",          38,   6.991, 6.996, 6.238,  90.0, 90.0, 90.0,  4,  "1011246"),
        ("Magnesite",    "Trigonal",      "R-3c",          167,  4.633, 4.633, 15.017, 90.0, 90.0, 120.0, 6,  "2100688"),
        ("Siderite",     "Trigonal",      "R-3c",          167,  4.689, 4.689, 15.375, 90.0, 90.0, 120.0, 6,  "1010298"),
        ("Tourmaline",   "Trigonal",      "R3m",           160,  15.994, 15.994, 7.190, 90.0, 90.0, 120.0, 3, "1010228"),
        ("Wollastonite", "Triclinic",     "P-1",           2,    7.940, 7.320, 7.065,  90.1, 95.4, 103.4, 6,  "2220218"),
        ("Enstatite",    "Orthorhombic",  "Pbca",          61,   18.228, 8.805, 5.185, 90.0, 90.0, 90.0,  16, "1001533"),
        ("Hornblende",   "Monoclinic",    "C2/m",          12,   9.886, 18.005, 5.290, 90.0, 105.8, 90.0, 2,  "9001648"),
        ("Chromite",     "Cubic",         "Fd-3m",         227,  8.334, 8.334, 8.334,  90.0, 90.0, 90.0,  8,  "1010345"),
        ("Sylvite",      "Cubic",         "Fm-3m",         225,  6.293, 6.293, 6.293,  90.0, 90.0, 90.0,  4,  "1011243"),
        ("Fluorapatite", "Hexagonal",     "P63/m",         176,  9.367, 9.367, 6.884,  90.0, 90.0, 120.0, 2,  "1011220"),
        ("Celestine",    "Orthorhombic",  "Pnma",          62,   8.359, 5.352, 6.866,  90.0, 90.0, 90.0,  4,  "1000023"),
        ("Pyrrhotite",   "Monoclinic",    "P21/a",         14,   6.865, 11.890, 22.79, 90.0, 91.8, 90.0, 16,  "1010433"),
    ]

    now = _NOW()
    owner = _OWNER_DID
    structures_seeded = 0
    edges_seeded = 0

    # Build mineral_name → vertex_id lookup
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT mineral_name, vertex_id FROM vertex_mineral")
        mineral_map = {row[0]: row[1] for row in _res}

    rows = _CRYSTALS[:batch_size]
    if True:
        client = get_kotoba_client()
        for (min_name, crystal_sys, space_grp, sg_num,
             a, b, c, alpha, beta, gamma, z_val, cod_id) in rows:
            mineral_vid = mineral_map.get(min_name)
            if not mineral_vid:
                continue
            crystal_vid = _vid("science", "crystal", min_name.lower().replace(" ", "_"))
            _res = client.q(
                """
                INSERT INTO vertex_crystal_structure (
                  vertex_id, source_ref_id, source_kind,
                  crystal_system, space_group, space_group_number,
                  a_ang, b_ang, c_ang,
                  alpha_deg, beta_deg, gamma_deg,
                  z_value, cod_id,
                  created_at, sensitivity_ord, owner_did
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    crystal_vid, mineral_vid, "mineral",
                    crystal_sys, space_grp, sg_num,
                    a, b, c,
                    alpha, beta, gamma,
                    z_val, cod_id,
                    now, 0, owner,
                ),
            )
            structures_seeded += 1

            eid = hashlib.sha256(f"{mineral_vid}::{crystal_vid}".encode()).hexdigest()[:24]
            _res = client.q(
                """
                INSERT INTO edge_mineral_crystal
                  (edge_id, mineral_did, crystal_did, source, created_at)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (eid, mineral_vid, crystal_vid, "cod", now),
            )
            edges_seeded += 1

    return {"structuresSeeded": structures_seeded, "edgesSeeded": edges_seeded}


def seed_uniprot_proteins(batch_size: int = 100, force_org_id: str | None = None) -> dict[str, Any]:
    """Seed UniProt protein entries into vertex_protein.

    Rotates through reviewed (Swiss-Prot) entries using the UniProt REST API.
    Links to vertex_scientific_taxon via organism taxon_id.
    Seeds vertex_protein + edge_protein_element (bulk elemental composition).
    Pass force_org_id (NCBI taxon ID string) to bypass organism rotation.
    """
    import urllib.request as _req

    now = _NOW()
    owner = _OWNER_DID
    proteins_seeded = 0
    edges_seeded = 0

    # Determine offset from existing count
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT COUNT(*) FROM vertex_protein")
        row = (_res[0] if _res else None)
        offset = int(row[0]) if row else 0

    # UniProt REST: reviewed Swiss-Prot entries.
    # Cycles through 5 model organisms to give coverage across kingdoms.
    # Divide by batch_size so each batch of 100 advances one organism.
    _ORGS = ["9606", "10090", "562", "4932", "7227"]  # human, mouse, E.coli, yeast, Drosophila
    org_id_query = force_org_id if force_org_id else _ORGS[(offset // max(batch_size, 1)) % len(_ORGS)]
    try:
        url = (
            f"https://rest.uniprot.org/uniprotkb/search"
            f"?query=reviewed:true+AND+organism_id:{org_id_query}"
            f"&format=json&size={min(batch_size, 200)}"
        )
        req = _req.Request(url, headers={"Accept": "application/json"})
        with _req.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
    except Exception as exc:
        return {"proteinsSeeded": 0, "edgesSeeded": 0, "error": str(exc), "fromOffset": offset}

    if True:

        client = get_kotoba_client()
        for entry in results:
            acc = entry.get("primaryAccession", "")
            if not acc:
                continue
            vid = f"at://{owner}/com.etzhayyim.apps.science.protein/{acc}"
            taxon_id = str(entry.get("organism", {}).get("taxonId", "") or "")
            org_name = entry.get("organism", {}).get("scientificName", "")
            gene_names = entry.get("genes", [{}])
            gene_name = (gene_names[0].get("geneName", {}).get("value", "")
                         if gene_names else "")
            prot_desc = (entry.get("proteinDescription", {})
                         .get("recommendedName", {})
                         .get("fullName", {}).get("value", ""))
            seq_len = entry.get("sequence", {}).get("length", 0)
            mass = entry.get("sequence", {}).get("mass", 0)
            subcel = str(entry.get("subcellularLocations", [{}])[0]
                         .get("location", {}).get("value", "")
                         if entry.get("subcellularLocations") else "")
            func_text = ""
            for comment in entry.get("comments", []):
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [{}])
                    func_text = texts[0].get("value", "") if texts else ""
                    break

            _res = client.q("""
                INSERT INTO vertex_protein (
                  vertex_id, uniprot_id, protein_name, gene_name,
                  organism, taxon_id, sequence_length, molecular_weight,
                  subcell_location, function_text, kg_linked,
                  created_at, sensitivity_ord, owner_did
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    vid, acc, prot_desc, gene_name,
                    org_name, taxon_id or None, seq_len, mass / 1000.0 if mass else None,
                    subcel, func_text[:512] if func_text else "", 0,
                    now, 0, owner,
                ),
            )
            proteins_seeded += 1

            # Seed bulk element edges: proteins are predominantly C/H/N/O/S
            for sym, role in [("C", "bulk"), ("H", "bulk"), ("N", "bulk"),
                               ("O", "bulk"), ("S", "bulk")]:
                eid = hashlib.sha256(f"{vid}::{sym}".encode()).hexdigest()[:24]
                elem_did = f"at://{owner}/com.etzhayyim.apps.science.element/{sym}"
                _res = client.q("""
                    INSERT INTO edge_protein_element
                      (edge_id, protein_did, element_sym, element_did, role, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (eid, vid, sym, elem_did, role, now),
                )
                edges_seeded += 1

    return {"proteinsSeeded": proteins_seeded, "edgesSeeded": edges_seeded,
            "fromOffset": offset, "orgId": org_id_query}


def seed_biological_taxa() -> dict[str, Any]:
    """Seed a curated biological taxonomy tree into vertex_scientific_taxon.

    Covers the 3-Domain system (Bacteria/Archaea/Eukarya) with ~80 nodes spanning
    Domain → Kingdom → Phylum → Class → Order → Family → Genus levels for the
    most scientifically significant lineages.  Idempotent.
    """
    now = _NOW()
    owner = _OWNER_DID

    # fmt: (rank, scientific_name, common_en, domain_kind, parent_scientific_name|None, ncbi_taxon_code)
    _TAXA: list[tuple[str, str, str, str, str | None, str]] = [
        # ── Three Domains ────────────────────────────────────────────────────
        ("domain",  "Bacteria",    "Bacteria",    "biology", None,       "2"),
        ("domain",  "Archaea",     "Archaea",     "biology", None,       "2157"),
        ("domain",  "Eukarya",     "Eukaryotes",  "biology", None,       "2759"),
        # ── Prokaryote Kingdoms ──────────────────────────────────────────────
        ("phylum",  "Proteobacteria",    "Proteobacteria",  "biology", "Bacteria",  "1224"),
        ("phylum",  "Firmicutes",        "Firmicutes",      "biology", "Bacteria",  "1239"),
        ("phylum",  "Actinobacteria",    "Actinobacteria",  "biology", "Bacteria",  "201174"),
        ("phylum",  "Cyanobacteria",     "Cyanobacteria",   "biology", "Bacteria",  "1117"),
        ("phylum",  "Spirochaetes",      "Spirochaetes",    "biology", "Bacteria",  "203691"),
        ("phylum",  "Euryarchaeota",     "Euryarchaeota",   "biology", "Archaea",   "28890"),
        ("phylum",  "Crenarchaeota",     "Crenarchaeota",   "biology", "Archaea",   "28889"),
        # ── Eukaryote Kingdoms ───────────────────────────────────────────────
        ("kingdom", "Animalia",    "Animals",     "biology", "Eukarya",   "33208"),
        ("kingdom", "Plantae",     "Plants",      "biology", "Eukarya",   "33090"),
        ("kingdom", "Fungi",       "Fungi",       "biology", "Eukarya",   "4751"),
        ("kingdom", "Protista",    "Protists",    "biology", "Eukarya",   "4116"),
        ("kingdom", "Chromista",   "Chromists",   "biology", "Eukarya",   "33634"),
        # ── Animal Phyla ─────────────────────────────────────────────────────
        ("phylum",  "Chordata",    "Chordates",   "biology", "Animalia",  "7711"),
        ("phylum",  "Arthropoda",  "Arthropods",  "biology", "Animalia",  "6656"),
        ("phylum",  "Mollusca",    "Molluscs",    "biology", "Animalia",  "6447"),
        ("phylum",  "Annelida",    "Annelids",    "biology", "Animalia",  "6340"),
        ("phylum",  "Nematoda",    "Roundworms",  "biology", "Animalia",  "6231"),
        ("phylum",  "Echinodermata","Echinoderms","biology", "Animalia",  "7586"),
        ("phylum",  "Cnidaria",    "Cnidarians",  "biology", "Animalia",  "6073"),
        ("phylum",  "Porifera",    "Sponges",     "biology", "Animalia",  "6040"),
        ("phylum",  "Platyhelminthes","Flatworms", "biology","Animalia",  "6157"),
        # ── Chordate Classes ─────────────────────────────────────────────────
        ("class",   "Mammalia",    "Mammals",     "biology", "Chordata",  "40674"),
        ("class",   "Aves",        "Birds",       "biology", "Chordata",  "8782"),
        ("class",   "Reptilia",    "Reptiles",    "biology", "Chordata",  "8504"),
        ("class",   "Amphibia",    "Amphibians",  "biology", "Chordata",  "8292"),
        ("class",   "Actinopterygii","Ray-finned fish","biology","Chordata","7898"),
        ("class",   "Chondrichthyes","Sharks/rays","biology","Chordata",  "7777"),
        # ── Mammal Orders ────────────────────────────────────────────────────
        ("order",   "Primates",    "Primates",    "biology", "Mammalia",  "9443"),
        ("order",   "Rodentia",    "Rodents",     "biology", "Mammalia",  "9989"),
        ("order",   "Carnivora",   "Carnivores",  "biology", "Mammalia",  "33554"),
        ("order",   "Cetacea",     "Whales",      "biology", "Mammalia",  "9721"),
        ("order",   "Chiroptera",  "Bats",        "biology", "Mammalia",  "9397"),
        ("order",   "Artiodactyla","Even-toed ungulates","biology","Mammalia","91561"),
        ("order",   "Perissodactyla","Odd-toed ungulates","biology","Mammalia","9787"),
        # ── Primate Families ─────────────────────────────────────────────────
        ("family",  "Hominidae",   "Great apes",  "biology", "Primates",  "9604"),
        ("family",  "Cercopithecidae","Old world monkeys","biology","Primates","9526"),
        ("family",  "Felidae",     "Cats",        "biology", "Carnivora", "9681"),
        ("family",  "Canidae",     "Dogs/wolves", "biology", "Carnivora", "9608"),
        # ── Model Organism Genera ────────────────────────────────────────────
        ("genus",   "Homo",        "Humans",      "biology", "Hominidae", "9605"),
        ("genus",   "Pan",         "Chimpanzees", "biology", "Hominidae", "9596"),
        ("genus",   "Mus",         "Mice",        "biology", "Rodentia",  "10088"),
        ("genus",   "Rattus",      "Rats",        "biology", "Rodentia",  "10114"),
        ("genus",   "Drosophila",  "Fruit flies", "biology", "Arthropoda","7215"),
        ("genus",   "Caenorhabditis","C. elegans genus","biology","Nematoda","6237"),
        ("genus",   "Saccharomyces","Budding yeasts","biology","Fungi",   "4930"),
        ("genus",   "Arabidopsis", "Thale cress", "biology", "Plantae",  "3701"),
        ("genus",   "Danio",       "Zebrafish",   "biology", "Actinopterygii","7954"),
        ("genus",   "Gallus",      "Chickens",    "biology", "Aves",      "9030"),
        ("genus",   "Xenopus",     "African clawed frogs","biology","Amphibia","8353"),
        ("genus",   "Escherichia", "E. coli genus","biology","Proteobacteria","561"),
        ("genus",   "Salmonella",  "Salmonella",  "biology", "Proteobacteria","590"),
        ("genus",   "Mycobacterium","Mycobacteria","biology","Actinobacteria","1763"),
        ("genus",   "Streptomyces","Streptomyces","biology","Actinobacteria","1883"),
        ("genus",   "Clostridium", "Clostridia",  "biology", "Firmicutes","1485"),
        ("genus",   "Bacillus",    "Bacilli",     "biology", "Firmicutes","1386"),
        ("genus",   "Staphylococcus","Staphylococci","biology","Firmicutes","1279"),
        ("genus",   "Synechocystis","Synechocystis","biology","Cyanobacteria","1142"),
        ("genus",   "Methanococcus","Methanococci","biology","Euryarchaeota","2188"),
        # ── Model Species ─────────────────────────────────────────────────────
        ("species", "Homo sapiens",       "Human",        "biology","Homo",         "9606"),
        ("species", "Mus musculus",        "House mouse",  "biology","Mus",          "10090"),
        ("species", "Rattus norvegicus",   "Norway rat",   "biology","Rattus",       "10116"),
        ("species", "Drosophila melanogaster","Fruit fly", "biology","Drosophila",   "7227"),
        ("species", "Caenorhabditis elegans","C. elegans", "biology","Caenorhabditis","6239"),
        ("species", "Saccharomyces cerevisiae","Baker's yeast","biology","Saccharomyces","4932"),
        ("species", "Arabidopsis thaliana","Thale cress",  "biology","Arabidopsis",  "3702"),
        ("species", "Danio rerio",         "Zebrafish",    "biology","Danio",        "7955"),
        ("species", "Gallus gallus",       "Chicken",      "biology","Gallus",       "9031"),
        ("species", "Xenopus laevis",      "African clawed frog","biology","Xenopus","8355"),
        ("species", "Escherichia coli",    "E. coli",      "biology","Escherichia",  "562"),
        ("species", "Mycobacterium tuberculosis","TB bacillus","biology","Mycobacterium","1773"),
        ("species", "Bacillus subtilis",   "B. subtilis",  "biology","Bacillus",     "1423"),
        # ── Plant Phyla / Classes ─────────────────────────────────────────────
        ("phylum",  "Tracheophyta",   "Vascular plants","biology","Plantae",    "58023"),
        ("phylum",  "Bryophyta",      "Mosses",          "biology","Plantae",    "3208"),
        ("class",   "Angiospermae",   "Flowering plants","biology","Tracheophyta","3398"),
        ("class",   "Gymnospermae",   "Conifers/cycads", "biology","Tracheophyta","1437180"),
        ("order",   "Poales",         "Grasses",         "biology","Angiospermae","38820"),
        ("order",   "Fabales",        "Legumes",         "biology","Angiospermae","72025"),
        ("order",   "Rosales",        "Roses/apples",    "biology","Angiospermae","3744"),
        ("family",  "Poaceae",        "Grasses",         "biology","Poales",      "4479"),
        ("family",  "Fabaceae",       "Legumes",         "biology","Fabales",     "3803"),
        ("family",  "Rosaceae",       "Rose family",     "biology","Rosales",     "3745"),
        ("genus",   "Oryza",          "Rice genus",      "biology","Poaceae",     "4527"),
        ("genus",   "Triticum",       "Wheat genus",     "biology","Poaceae",     "4564"),
        ("genus",   "Zea",            "Maize genus",     "biology","Poaceae",     "4575"),
        ("genus",   "Rosa",           "Roses",           "biology","Rosaceae",    "3764"),
        ("species", "Oryza sativa",    "Rice",           "biology","Oryza",       "4530"),
        ("species", "Triticum aestivum","Wheat",         "biology","Triticum",    "4565"),
        ("species", "Zea mays",        "Maize",          "biology","Zea",         "4577"),
        # ── Fungi ────────────────────────────────────────────────────────────
        ("phylum",  "Ascomycota",  "Sac fungi",    "biology","Fungi",    "4890"),
        ("phylum",  "Basidiomycota","Club fungi",   "biology","Fungi",    "5204"),
        ("class",   "Eurotiomycetes","Aspergillus class","biology","Ascomycota","147545"),
        ("genus",   "Aspergillus", "Aspergillus",  "biology","Ascomycota","5052"),
        ("genus",   "Penicillium", "Penicillium",  "biology","Ascomycota","5073"),
        ("genus",   "Candida",     "Candida yeasts","biology","Ascomycota","1535326"),
        ("species", "Aspergillus niger","Black mold","biology","Aspergillus","5061"),
        # ── Viruses (special domain_kind) ────────────────────────────────────
        ("family",  "Coronaviridae","Coronaviruses","virus","Eukarya",   "11118"),
        ("family",  "Retroviridae", "Retroviruses", "virus","Eukarya",   "11632"),
        ("genus",   "Betacoronavirus","Beta-CoVs",  "virus","Coronaviridae","694002"),
        ("species", "Severe acute respiratory syndrome-related coronavirus",
                    "SARS-CoV-2",   "virus","Betacoronavirus","2697049"),
    ]

    # Build name→vertex_id map for parent lookup
    name_to_vid: dict[str, str] = {}
    seeded = 0

    if True:

        client = get_kotoba_client()
        for (rank, sci_name, common_en, domain_kind, parent_name, ncbi_code) in _TAXA:
            vid = _vid("seibutsu", "taxon", sci_name.lower().replace(" ", "_"))
            parent_vid = name_to_vid.get(parent_name) if parent_name else None
            _res = client.q(
                """
                INSERT INTO vertex_scientific_taxon
                  (vertex_id, taxon_rank, scientific_name, common_name_en,
                   domain_kind, taxon_code, parent_taxon_did,
                   source, created_at, sensitivity_ord, owner_did, actor_id)
                VALUES (%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s)
                """,
                (
                    vid, rank, sci_name, common_en,
                    domain_kind, ncbi_code, parent_vid,
                    "ncbi", now, 1, owner, "sys.science.seed",
                ),
            )
            name_to_vid[sci_name] = vid
            seeded += 1

    return {"taxaSeeded": seeded}


def run_science_kg_builder_phase2(
    domain: str = "chemistry", max_replan: int = 2
) -> dict[str, Any]:
    """LangGraph Phase 2: NER → compound + protein edges from paper abstracts."""
    try:
        from langgraph.graph import StateGraph, END, START  # type: ignore[import]
    except ImportError:
        return {"compound_ops": 0, "protein_ops": 0, "error": "langgraph not available"}

    class Phase2State(TypedDict):
        papers: list[dict]
        compound_links: list[dict]
        protein_links: list[dict]
        compound_ops: int
        protein_ops: int
        replan_count: int

    now = _NOW()
    owner = _OWNER_DID

    def fetch_papers(state: Phase2State) -> Phase2State:
        papers: list[dict] = []
        if True:
            client = get_kotoba_client()
            _res = client.q("""
                SELECT vertex_id, abstract, domain
                FROM vertex_scientific_paper
                WHERE kg_linked = 1 AND domain = %s
                LIMIT 20
                """, (domain,))
            for row in _res:
                papers.append({"did": row[0], "abstract": row[1], "domain": row[2]})
        return {**state, "papers": papers}

    def ner_phase2(state: Phase2State) -> Phase2State:
        from kotodama.primitives.science_knowledge import _llm_ner_extract_phase2
        compound_links: list[dict] = []
        protein_links: list[dict] = []
        for paper in state["papers"][:10]:
            result = _llm_ner_extract_phase2(paper["abstract"])
            for cname in result.get("compounds", []):
                compound_links.append({"paper_did": paper["did"], "name": cname})
            for pname in result.get("proteins", []):
                protein_links.append({"paper_did": paper["did"], "name": pname})
        return {**state, "compound_links": compound_links, "protein_links": protein_links}

    def link_compounds(state: Phase2State) -> Phase2State:
        ops = 0
        if True:
            client = get_kotoba_client()
            for link in state["compound_links"]:
                _res = client.q(
                    "SELECT vertex_id FROM vertex_compound WHERE iupac_name ILIKE %s LIMIT 1",
                    (link["name"],)
                )
                row = (_res[0] if _res else None)
                if not row:
                    continue
                compound_did = row[0]
                eid = hashlib.sha256(
                    f"{link['paper_did']}::{compound_did}".encode()
                ).hexdigest()[:24]
                _res = client.q("""
                    INSERT INTO edge_paper_compound
                      (edge_id, paper_did, compound_did, mention_count, created_at)
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (eid, link["paper_did"], compound_did, 1, now),
                )
                ops += 1
        return {**state, "compound_ops": state["compound_ops"] + ops}

    def link_proteins(state: Phase2State) -> Phase2State:
        ops = 0
        if True:
            client = get_kotoba_client()
            for link in state["protein_links"]:
                _res = client.q(
                    "SELECT vertex_id FROM vertex_protein WHERE protein_name ILIKE %s LIMIT 1",
                    (link["name"],)
                )
                row = (_res[0] if _res else None)
                if not row:
                    continue
                protein_did = row[0]
                eid = hashlib.sha256(
                    f"{link['paper_did']}::{protein_did}".encode()
                ).hexdigest()[:24]
                _res = client.q("""
                    INSERT INTO edge_paper_protein
                      (edge_id, paper_did, protein_did, mention_count, created_at)
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (eid, link["paper_did"], protein_did, 1, now),
                )
                ops += 1
        return {**state, "protein_ops": state["protein_ops"] + ops}

    def verify(state: Phase2State) -> Phase2State:
        return state

    def should_replan(state: Phase2State) -> str:
        total = state["compound_ops"] + state["protein_ops"]
        if total / max(len(state["papers"]), 1) < 0.2 and state["replan_count"] < max_replan:
            return "ner_phase2"
        return END

    g: StateGraph = StateGraph(Phase2State)
    g.add_node("fetch_papers", fetch_papers)
    g.add_node("ner_phase2", ner_phase2)
    g.add_node("link_compounds", link_compounds)
    g.add_node("link_proteins", link_proteins)
    g.add_node("verify", verify)
    g.add_edge(START, "fetch_papers")
    g.add_edge("fetch_papers", "ner_phase2")
    g.add_edge("ner_phase2", "link_compounds")
    g.add_edge("link_compounds", "link_proteins")
    g.add_edge("link_proteins", "verify")
    g.add_conditional_edges("verify", should_replan)

    init: Phase2State = {
        "papers": [], "compound_links": [], "protein_links": [],
        "compound_ops": 0, "protein_ops": 0, "replan_count": 0,
    }
    result = g.compile().invoke(init)
    return {"compound_ops": result["compound_ops"], "protein_ops": result["protein_ops"]}


def _llm_ner_extract_phase2(abstract: str) -> dict[str, list[str]]:
    """NER extraction for compound and protein names using kotodama.llm."""
    try:
        from kotodama import llm as _llm
        result = _llm.call_tier_json(
            "classifier",
            system=(
                "You are a biomedical NER system. Extract named entities from the abstract. "
                'Return ONLY a JSON object: {"compounds": [...], "proteins": [...]}'
            ),
            user=f"Abstract: {abstract[:1200]}",
            max_tokens=256,
            temperature=0,
        )
        if result.get("ok") and isinstance(result.get("data"), dict):
            data = result["data"]
            return {
                "compounds": [str(x) for x in data.get("compounds", []) if x],
                "proteins":  [str(x) for x in data.get("proteins",  []) if x],
            }
    except Exception:
        pass
    return {"compounds": [], "proteins": []}


# ── Kami model instance seeding ───────────────────────────────────────────────

def _h3_cell(lat: float, lng: float, res: int = 10) -> str:
    """Return H3 cell ID at given resolution. Requires h3 library or h3env venv."""
    try:
        import h3 as _h3  # type: ignore[import]
        return _h3.latlng_to_cell(lat, lng, res)
    except ImportError:
        pass
    # Fallback: subprocess via /tmp/h3env
    import subprocess as _sp
    import json as _json
    try:
        r = _sp.run(
            ["/tmp/h3env/bin/python3", "-c",
             f"import h3; print(h3.latlng_to_cell({lat},{lng},{res}))"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    # Last resort: fake cell (won't match client queries but won't break schema)
    return f"deadbeef{abs(int(lat*1e4)):04x}{abs(int(lng*1e4)):04x}ffff"


def _h3_cells_batch(latlngs: list[tuple[float, float]], res: int = 10) -> list[str]:
    """Compute H3 cells for a list of (lat, lng) pairs in one subprocess call."""
    try:
        import h3 as _h3  # type: ignore[import]
        return [_h3.latlng_to_cell(lat, lng, res) for lat, lng in latlngs]
    except ImportError:
        pass
    import subprocess as _sp
    import json as _json
    try:
        pairs_json = _json.dumps(latlngs)
        script = (
            f"import h3,json; pairs={pairs_json}; "
            "print(json.dumps([h3.latlng_to_cell(la,lo,10) for la,lo in pairs]))"
        )
        r = _sp.run(
            ["/tmp/h3env/bin/python3", "-c", script],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return _json.loads(r.stdout.strip())
    except Exception:
        pass
    return [_h3_cell(lat, lng, res) for lat, lng in latlngs]


def seed_kami_element_instances(
    anchor_lat: float = 35.6812,
    anchor_lng: float = 139.7671,
    h3_res: int = 10,
) -> dict[str, Any]:
    """Seed vertex_kami_model_instance for all 118 periodic elements.

    Places elements in a periodic-table grid 5–10 km north of anchor (Tokyo default).
    Each cell: 600 m × 600 m. H3 cells at resolution 10 so maps-walk can query them.
    world_x / world_z are pre-computed relative to anchor (meters).
    """
    import math as _math

    M_LAT = 111_320.0
    M_LNG = 111_320.0 * _math.cos(anchor_lat * _math.pi / 180)
    STEP_M = 600.0
    LAT_STEP = STEP_M / M_LAT
    LNG_STEP = STEP_M / M_LNG

    # Table top-left: 10 rows north, 0 columns (group=1 aligns to anchor_lng)
    ORIGIN_LAT = anchor_lat + 11 * LAT_STEP
    ORIGIN_LNG = anchor_lng

    now = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    inserted = 0
    skipped = 0

    if True:

        client = get_kotoba_client()
        _res = client.q("""
            SELECT e.atomic_number, e.symbol, e.period, e.group_number,
                   d.vertex_id as model_def_id
            FROM vertex_periodic_element e
            JOIN vertex_kami_model_def d ON d.taxonomy_did = e.vertex_id
            WHERE d.render_kind = 'cpk_sphere'
            ORDER BY e.atomic_number
        """)
        elements = _res

    if not elements:
        return {"elementInstancesSeeded": 0, "error": "no cpk_sphere model_defs found"}

    # Build (lat, lng) for each element
    positions: list[tuple[float, float]] = []
    for atomic_num, symbol, period, group_num, model_def_id in elements:
        if 57 <= atomic_num <= 71:   # lanthanides — row 8.5
            lat = ORIGIN_LAT - 8.5 * LAT_STEP
            lng = ORIGIN_LNG + (3 + (atomic_num - 57)) * LNG_STEP
        elif 89 <= atomic_num <= 103:  # actinides — row 9.5
            lat = ORIGIN_LAT - 9.5 * LAT_STEP
            lng = ORIGIN_LNG + (3 + (atomic_num - 89)) * LNG_STEP
        else:
            lat = ORIGIN_LAT - period * LAT_STEP
            lng = ORIGIN_LNG + (group_num - 1) * LNG_STEP
        positions.append((lat, lng))

    # Batch H3 computation
    cells = _h3_cells_batch(positions, res=h3_res)

    if True:

        client = get_kotoba_client()
        for idx, (atomic_num, symbol, period, group_num, model_def_id) in enumerate(elements):
            lat, lng = positions[idx]
            cell = cells[idx]
            world_x = (lng - anchor_lng) * M_LNG
            world_z = -(lat - anchor_lat) * M_LAT

            rkey = hashlib.sha256(f"element-instance-{symbol}".encode()).hexdigest()[:16]
            vertex_id = f"at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.kamiModelInstance/{rkey}"
            taxonomy_did = f"at://did:web:chemistry.etzhayyim.com/com.etzhayyim.apps.chemistry.element/{symbol}"

            # Check existing
            _res = client.q(
                "SELECT 1 FROM vertex_kami_model_instance WHERE taxonomy_did = %s",
                (taxonomy_did,),
            )
            if (_res[0] if _res else None):
                skipped += 1
                continue

            _res = client.q("""
                INSERT INTO vertex_kami_model_instance
                  (vertex_id, model_def_id, tile_h3, world_x, world_y, world_z,
                   scale_x, scale_y, scale_z, taxonomy_did, annotation_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (vertex_id, model_def_id, cell,
                 world_x, 0.0, world_z,
                 1.0, 1.0, 1.0,
                 taxonomy_did,
                 f'{{"symbol":"{symbol}","atomicNumber":{atomic_num}}}',
                 now),
            )
            inserted += 1

    return {"elementInstancesSeeded": inserted, "skipped": skipped, "total": len(elements)}


def seed_kami_vegetation_instances(
    anchor_lat: float = 35.6812,
    anchor_lng: float = 139.7671,
    h3_res: int = 10,
) -> dict[str, Any]:
    """Seed vertex_kami_model_instance for the 7 canonical vegetation types.

    Places each vegetation type in a row south of anchor, spaced 800 m apart.
    """
    import math as _math

    M_LAT = 111_320.0
    M_LNG = 111_320.0 * _math.cos(anchor_lat * _math.pi / 180)
    STEP_M = 800.0
    LNG_STEP = STEP_M / M_LNG
    now = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    inserted = 0
    skipped = 0

    # 3 km south of anchor, spread along lng
    BASE_LAT = anchor_lat - 3000.0 / M_LAT
    BASE_LNG = anchor_lng - 3 * LNG_STEP  # center 7 types

    if True:

        client = get_kotoba_client()
        _res = client.q("""
            SELECT d.vertex_id, d.taxonomy_did, t.scientific_name
            FROM vertex_kami_model_def d
            LEFT JOIN vertex_scientific_taxon t ON t.vertex_id = d.taxonomy_did
            WHERE d.render_kind = 'procedural'
            ORDER BY d.vertex_id
        """)
        veg_defs = _res

    if not veg_defs:
        return {"vegetationInstancesSeeded": 0, "error": "no procedural model_defs found"}

    latlngs = [(BASE_LAT, BASE_LNG + i * LNG_STEP) for i in range(len(veg_defs))]
    cells = _h3_cells_batch(latlngs, res=h3_res)

    if True:

        client = get_kotoba_client()
        for idx, (model_def_id, taxonomy_did, taxon_name) in enumerate(veg_defs):
            lat, lng = latlngs[idx]
            cell = cells[idx]
            world_x = (lng - anchor_lng) * M_LNG
            world_z = -(lat - anchor_lat) * M_LAT

            slug = model_def_id.split("/")[-1]
            rkey = hashlib.sha256(f"veg-instance-{slug}".encode()).hexdigest()[:16]
            vertex_id = f"at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.kamiModelInstance/{rkey}"

            if taxonomy_did:
                _res = client.q(
                    "SELECT 1 FROM vertex_kami_model_instance WHERE taxonomy_did = %s AND model_def_id = %s",
                    (taxonomy_did, model_def_id),
                )
                if (_res[0] if _res else None):
                    skipped += 1
                    continue

            _res = client.q("""
                INSERT INTO vertex_kami_model_instance
                  (vertex_id, model_def_id, tile_h3, world_x, world_y, world_z,
                   scale_x, scale_y, scale_z, taxonomy_did, annotation_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (vertex_id, model_def_id, cell,
                 world_x, 0.0, world_z,
                 1.0, 1.0, 1.0,
                 taxonomy_did or "",
                 f'{{"taxon":"{taxon_name or slug}"}}',
                 now),
            )
            inserted += 1

    return {"vegetationInstancesSeeded": inserted, "skipped": skipped, "total": len(veg_defs)}


def register(worker: Any, *, timeout_ms: int) -> None:
    """Register 8 science knowledge Zeebe task handlers (ADR-0056).

    Task types:
      science.paper.fetchArxiv     — arXiv domain rotation ingest
      science.paper.embedBatch     — Murakumo nomic-embed-text
      science.paper.linkGraph      — NER + ontology linking (LangGraph)
      science.element.seedElements — 118-element periodic table seed
      science.element.seedMaterials — PBR material def bootstrap
      science.taxon.syncNcbi       — NCBI taxonomy subtree sync
      science.taxon.seedVegetation  — 7 canonical vegetation profiles
      science.mineral.seedIma      — IMA mineral list + element edge seed
    """
    import datetime as _dt_reg

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(task_type=name, single_value=False,
                    timeout_ms=timeout if timeout is not None else timeout_ms)(fn)

    async def task_fetch_arxiv(limit: int = 50) -> dict:
        idx = (_dt_reg.datetime.now(tz=_dt_reg.UTC).hour // 6) % len(_ARXIV_DOMAINS)
        query, domain = _ARXIV_DOMAINS[idx]
        run_id = f"arxiv-{domain}-{uuid.uuid4().hex[:8]}"
        result = await ingest_arxiv_batch(query=query, domain=domain, limit=limit)
        return {"runId": run_id, "domain": domain, "papersInserted": result["inserted"]}

    async def task_embed_batch(runId: str = "", batch_size: int = 50) -> dict:  # noqa: N803
        result = await embed_paper_batch(batch_size=batch_size)
        return {"papersEmbedded": result["embedded"]}

    def task_link_graph(runId: str = "", domain: str = "cs_ai", max_replan: int = 2) -> dict:  # noqa: N803
        result = run_science_kg_builder(domain=domain, max_replan=max_replan)
        return {"papersLinked": result.get("ops", 0)}

    def task_seed_elements(batch_size: int = 20) -> dict:
        result = seed_periodic_elements(batch_size=batch_size)
        return {"seeded": result["inserted"]}

    def task_seed_materials() -> dict:
        return seed_pbr_materials()

    async def task_sync_ncbi(max_nodes: int = 200) -> dict:
        idx = _dt_reg.datetime.now(tz=_dt_reg.UTC).timetuple().tm_yday % len(_NCBI_DOMAINS)
        root_taxid, domain_kind = _NCBI_DOMAINS[idx]
        result = await sync_ncbi_taxon_subtree(
            root_taxid=root_taxid,
            domain_kind=domain_kind,
            max_nodes=max_nodes,
        )
        return {
            "rootTaxid": result["root_taxid"],
            "domain_kind": domain_kind,
            "taxaInserted": result["inserted"],
        }

    def task_seed_vegetation() -> dict:
        result = seed_vegetation_taxa()
        return {"vegetationSeeded": result["seeded"]}

    def task_seed_ima_minerals(batch_size: int = 100) -> dict:
        return seed_ima_minerals(batch_size=batch_size)

    # ── Phase 2: compound / crystal / protein ─────────────────────────────

    def task_seed_pubchem(batch_size: int = 200) -> dict:
        return seed_pubchem_compounds(batch_size=batch_size)

    def task_seed_crystal_structures(batch_size: int = 50) -> dict:
        return seed_crystal_structures(batch_size=batch_size)

    def task_seed_uniprot(batch_size: int = 100, forceOrgId: str = "") -> dict:  # noqa: N803
        return seed_uniprot_proteins(batch_size=batch_size,
                                     force_org_id=forceOrgId or None)

    def task_seed_biological_taxa() -> dict:
        return seed_biological_taxa()

    def task_link_graph_phase2(
        runId: str = "", domain: str = "chemistry", max_replan: int = 2  # noqa: N803
    ) -> dict:
        result = run_science_kg_builder_phase2(domain=domain, max_replan=max_replan)
        return {"compoundsLinked": result.get("compound_ops", 0),
                "proteinsLinked": result.get("protein_ops", 0)}

    t("science.paper.fetchArxiv",          task_fetch_arxiv,           timeout=max(timeout_ms, 120_000))
    t("science.paper.embedBatch",          task_embed_batch,           timeout=max(timeout_ms, 300_000))
    t("science.paper.linkGraph",           task_link_graph,            timeout=max(timeout_ms, 180_000))
    t("science.paper.linkGraphPhase2",     task_link_graph_phase2,     timeout=max(timeout_ms, 180_000))
    t("science.element.seedElements",      task_seed_elements,         timeout=max(timeout_ms, 60_000))
    t("science.element.seedMaterials",     task_seed_materials,        timeout=max(timeout_ms, 60_000))
    t("science.taxon.syncNcbi",            task_sync_ncbi,             timeout=max(timeout_ms, 120_000))
    t("science.taxon.seedVegetation",      task_seed_vegetation,       timeout=max(timeout_ms, 60_000))
    t("science.mineral.seedIma",           task_seed_ima_minerals,     timeout=max(timeout_ms, 300_000))
    t("science.compound.seedPubchem",      task_seed_pubchem,          timeout=max(timeout_ms, 600_000))
    t("science.crystal.seedStructures",    task_seed_crystal_structures, timeout=max(timeout_ms, 300_000))
    t("science.protein.seedUniprot",       task_seed_uniprot,          timeout=max(timeout_ms, 600_000))
    t("science.taxon.seedBiologicalTaxa",  task_seed_biological_taxa,  timeout=max(timeout_ms, 60_000))

    def task_seed_element_instances(
        anchorLat: float = 35.6812, anchorLng: float = 139.7671  # noqa: N803
    ) -> dict:
        return seed_kami_element_instances(anchor_lat=anchorLat, anchor_lng=anchorLng)

    def task_seed_vegetation_instances(
        anchorLat: float = 35.6812, anchorLng: float = 139.7671  # noqa: N803
    ) -> dict:
        return seed_kami_vegetation_instances(anchor_lat=anchorLat, anchor_lng=anchorLng)

    t("science.kami.seedElementInstances",    task_seed_element_instances,    timeout=max(timeout_ms, 120_000))
    t("science.kami.seedVegetationInstances", task_seed_vegetation_instances, timeout=max(timeout_ms, 60_000))

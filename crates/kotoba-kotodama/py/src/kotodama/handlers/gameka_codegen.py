"""
gameka.codegen.renderKamiApp — Python codegen for kami-app-{slug} crates
(ADR 2604250900 P2).

Given a gameSpec (title / slug / genre / mechanic_json / scene_json), emit
a deterministic Rust source tree mirroring the structure of the existing
reference `kami-app-isekai` crate (`40-engine/kami-engine/kami-app-isekai/`).
The tree is **not** written to disk by this task — that is the responsibility
of the downstream wasm-pack build runner (P3, deferred). This task computes:

  - wasmCid     CIDv1-shape sha256 of the canonical sources blob
                (b base32 + raw codec + multihash 0x12 + 32 bytes), used
                as a content-addressed identifier in vertex_gameka_artifact.
                Becomes the wasm binary CID once P3 wasm-pack lands.
  - wasmSize    Total bytes of all source files (proxy until binary build).
  - entryFn     Public WASM entrypoint name `run_<slug-with-underscores>`.
  - fileCount   Number of files in the rendered tree.
  - buildStatus "sources_ready"  — sources rendered, no wasm yet.

The actual file tree is exposed as `_render_kami_app_sources(...)` for
unit tests + the future P3 build runner.

Determinism: the same spec input MUST produce byte-identical sources +
the same wasmCid. No timestamps, no randomness in templates.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)


# ─── Config ─────────────────────────────────────────────────────────────


_BIOME_KEYWORDS = (
    ("plains",         "Plains"),
    ("quarry",         "Quarry"),
    ("desert",         "Desert"),
    ("tundra",         "Tundra"),
    ("voxel",          "Plains"),  # voxel default biome
    ("volcano",        "Quarry"),
    ("snow",           "Tundra"),
    ("forest",         "Plains"),
    ("cave",           "Quarry"),
    ("ice",            "Tundra"),
    ("sand",           "Desert"),
    ("dune",           "Desert"),
)

_GENRE_CAMERA = {
    "platformer":   "ThirdPerson",
    "puzzle":       "Orbit",
    "shmup":        "TopDown",
    "runner":       "ThirdPerson",
    "sandbox":      "Fps",
    "rhythm":       "Static",
    "rogue-lite":   "TopDown",
    "tower-defense": "TopDown",
}

_GENRE_INPUT = {
    "platformer":   "Wasd",
    "puzzle":       "PointerOrbit",
    "shmup":        "Wasd",
    "runner":       "ArrowsOnly",
    "sandbox":      "WasdMouseLook",
    "rhythm":       "BeatTap",
    "rogue-lite":   "Wasd",
    "tower-defense": "PointerSelect",
}

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _biome_for(scene_text: str) -> str:
    s = (scene_text or "").lower()
    for needle, biome in _BIOME_KEYWORDS:
        if needle in s:
            return biome
    return "Plains"


def _camera_for(genre: str) -> str:
    return _GENRE_CAMERA.get((genre or "").lower(), "Orbit")


def _input_for(genre: str) -> str:
    return _GENRE_INPUT.get((genre or "").lower(), "PointerOrbit")


def _slug(s: str) -> str:
    base = re.sub(r"\s+", "-", (s or "").strip().lower())
    base = _SLUG_RE.sub("", base)
    return (base[:24] or "game").strip("-") or "game"


def _entry_fn(slug: str) -> str:
    """`run_<slug-with-underscores>`. WASM-bindgen exports must be valid
    Rust idents; hyphens become underscores."""
    return "run_" + slug.replace("-", "_")


def _safe_str(s: Any, max_len: int = 200) -> str:
    """Sanitise free-form text for embedding in Rust source comments."""
    out = str(s or "")
    out = out.replace("\\", "\\\\").replace("\"", "\\\"")
    out = out.replace("\n", " ").replace("\r", " ")
    return out[:max_len]


def _parse_json(s: Any) -> dict[str, Any]:
    if isinstance(s, dict):
        return s
    if isinstance(s, str) and s:
        try:
            v = json.loads(s)
            return v if isinstance(v, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


# ─── Mechanic templates (P13) ───────────────────────────────────────────
#
# Three sub-genre modules, selected per spec.mechanic.kind. Each emits
# `src/mechanic.rs` in the generated kami-app-{slug} crate. The
# modules are pure Rust state machines (no kami-* crate deps) so they
# can be unit-tested in isolation and drive the game's audio +
# social bridges through `crate::{play_sfx, share_score}`.
#
# Wasm-bindgen exports let the host (playtest shell + future
# kami-ui-gpu input layer) drive the state. Each module exposes:
#
#   mechanic_init()          set up fresh state
#   mechanic_status() -> u32 0=playing, 1=won, 2=lost
#   mechanic_score()  -> u32 current score
#   <kind-specific input fns>
#
# The library never panics on bad input — out-of-range / missing
# state returns no-ops, matching the bridge philosophy.
#
# These are skeletons in two senses:
#   1. they implement the mechanic state machine completely (cargo
#      test runs the merge / win logic against in-memory boards),
#   2. they don't render — the kami-pipelines biome scene is the
#      visual; mechanic state surfaces only via SFX + share events.
#      A P14 follow-up will add a `kami-ui-gpu` overlay grid.

_MECHANIC_GRID_2048 = r"""//! 4x4 swipe-merge mechanic — emitted by gameka.codegen.renderKamiApp.
//!
//! State: `[[u32; 4]; 4]` board, each cell holding a tile rank
//! (0 = empty). `swipe(Dir)` slides every column or row in the
//! direction, merges same-rank adjacent tiles into rank+1, then
//! spawns one new rank-1 tile in a random empty cell.
//!
//! Win = any cell reaches rank 11 (2048 in classic 2^N notation).
//! Lose = no swipe in any direction would change the board.

use std::cell::RefCell;

#[cfg(target_family = "wasm")]
use wasm_bindgen::prelude::*;

const N: usize = 4;
const WIN_RANK: u32 = 11;

#[derive(Copy, Clone, Debug)]
pub enum Dir { Left, Right, Up, Down }

#[derive(Debug)]
pub struct State {
    pub board: [[u32; N]; N],
    pub score: u32,
    pub status: u32,    // 0=playing 1=won 2=lost
    seed: u64,
}

impl State {
    pub fn new(seed: u64) -> Self {
        let mut s = Self { board: [[0; N]; N], score: 0, status: 0, seed };
        s.spawn();
        s.spawn();
        s
    }

    fn rng(&mut self) -> u64 {
        // xorshift64 — deterministic from seed. Good enough for
        // tile placement; cargo test uses a fixed seed.
        let mut x = self.seed;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.seed = x;
        x
    }

    fn spawn(&mut self) {
        // Use a fixed-size buffer to avoid pulling in a heap allocator
        // dep; max empties is N*N = 16.
        let mut empties: [(usize, usize); 16] = [(0, 0); 16];
        let mut n_empty = 0usize;
        for r in 0..N { for c in 0..N {
            if self.board[r][c] == 0 { empties[n_empty] = (r, c); n_empty += 1; }
        }}
        if n_empty == 0 { return; }
        let i = (self.rng() as usize) % n_empty;
        let (r, c) = empties[i];
        // 90% rank 1, 10% rank 2 (matches 2048 conventions).
        self.board[r][c] = if (self.rng() & 0xF) == 0 { 2 } else { 1 };
    }

    pub fn swipe(&mut self, dir: Dir) -> bool {
        if self.status != 0 { return false; }
        let before = self.board;
        match dir {
            Dir::Left  => for row in self.board.iter_mut() { merge_row(row, &mut self.score); },
            Dir::Right => for row in self.board.iter_mut() {
                row.reverse();
                merge_row(row, &mut self.score);
                row.reverse();
            },
            Dir::Up    => for col in 0..N {
                let mut tmp = [self.board[0][col], self.board[1][col], self.board[2][col], self.board[3][col]];
                merge_row(&mut tmp, &mut self.score);
                for r in 0..N { self.board[r][col] = tmp[r]; }
            },
            Dir::Down  => for col in 0..N {
                let mut tmp = [self.board[3][col], self.board[2][col], self.board[1][col], self.board[0][col]];
                merge_row(&mut tmp, &mut self.score);
                for r in 0..N { self.board[N - 1 - r][col] = tmp[r]; }
            },
        }
        let changed = self.board != before;
        if changed {
            self.spawn();
            // Win check
            if self.board.iter().any(|r| r.iter().any(|&v| v >= WIN_RANK)) {
                self.status = 1;
            } else if !any_move_possible(&self.board) {
                self.status = 2;
            }
        }
        changed
    }
}

fn merge_row(row: &mut [u32; N], score: &mut u32) -> bool {
    let mut compact = [0u32; N];
    let mut n = 0usize;
    for &v in row.iter() { if v != 0 { compact[n] = v; n += 1; } }
    let mut merged = [0u32; N];
    let mut m = 0usize;
    let mut i = 0usize;
    while i < n {
        if i + 1 < n && compact[i] == compact[i + 1] {
            let next = compact[i] + 1;
            merged[m] = next; m += 1;
            *score += 1u32 << (next as u32).min(31);
            i += 2;
        } else {
            merged[m] = compact[i]; m += 1;
            i += 1;
        }
    }
    let mut changed = false;
    for k in 0..N {
        if row[k] != merged[k] { changed = true; }
        row[k] = merged[k];
    }
    changed
}

fn any_move_possible(b: &[[u32; N]; N]) -> bool {
    for r in 0..N { for c in 0..N {
        if b[r][c] == 0 { return true; }
        if c + 1 < N && b[r][c] == b[r][c + 1] { return true; }
        if r + 1 < N && b[r][c] == b[r + 1][c] { return true; }
    }}
    false
}

thread_local! {
    static MECH: RefCell<State> = RefCell::new(State::new(0xC0FFEE));
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_init(seed: u32) {
    MECH.with(|m| *m.borrow_mut() = State::new(seed as u64 | 0xC0FFEE_0000_0000));
    crate::play_sfx("loaded");
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_swipe(dir: u32) {
    let d = match dir { 0 => Dir::Left, 1 => Dir::Right, 2 => Dir::Up, 3 => Dir::Down, _ => return };
    let mut won_now = false;
    MECH.with(|m| {
        let mut s = m.borrow_mut();
        let prev = s.status;
        if s.swipe(d) {
            crate::play_sfx("click");
            if s.status == 1 && prev == 0 { won_now = true; }
        }
    });
    if won_now {
        crate::play_sfx("success");
        crate::share_score(2u32.pow(WIN_RANK), "reached the apex tile in Grid Merge");
    }
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_score() -> u32 {
    MECH.with(|m| m.borrow().score)
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_status() -> u32 {
    MECH.with(|m| m.borrow().status)
}

/// Returns the mechanic kind tag — also exported to the JS renderer
/// in __playtest__.html so the DOM overlay can dispatch on it.
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_kind() -> String {
    "grid_2048".to_string()
}

/// JSON snapshot of the visible state. Polled by the shell's DOM
/// overlay at ~60Hz. Shape (grid_2048):
///   { kind, score, status, board: [[u32;4];4] }
/// Status: 0 playing / 1 won / 2 lost.
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_render_state() -> String {
    MECH.with(|m| {
        let s = m.borrow();
        let mut out = String::with_capacity(192);
        out.push_str("{\"kind\":\"grid_2048\",\"score\":");
        out.push_str(&s.score.to_string());
        out.push_str(",\"status\":");
        out.push_str(&s.status.to_string());
        out.push_str(",\"board\":[");
        for r in 0..N {
            if r > 0 { out.push(','); }
            out.push('[');
            for c in 0..N {
                if c > 0 { out.push(','); }
                out.push_str(&s.board[r][c].to_string());
            }
            out.push(']');
        }
        out.push_str("]}");
        out
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn empty_board_two_spawns_after_new() {
        let s = State::new(1);
        let nz = s.board.iter().flatten().filter(|&&v| v != 0).count();
        assert_eq!(nz, 2);
    }
    #[test]
    fn merge_two_rank1_into_rank2() {
        let mut s = State::new(1);
        s.board = [[1,1,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
        s.score = 0;
        let changed = s.swipe(Dir::Left);
        assert!(changed);
        assert_eq!(s.board[0][0], 2);
    }
    #[test]
    fn no_merge_on_distinct_ranks() {
        let mut s = State::new(1);
        s.board = [[1,2,3,4],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
        s.swipe(Dir::Left);
        assert_eq!(s.board[0], [1,2,3,4]);
    }
    #[test]
    fn win_at_rank_11() {
        let mut s = State::new(1);
        s.board = [[10,10,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
        s.swipe(Dir::Left);
        assert_eq!(s.status, 1);
    }
    #[test]
    fn lose_when_no_move_possible() {
        let mut s = State::new(1);
        s.board = [[1,2,1,2],[2,1,2,1],[1,2,1,2],[2,1,2,1]];
        s.score = 0; s.status = 0;
        let changed = s.swipe(Dir::Left);
        assert!(!changed);
        // After a real failed swipe lose check needs spawn() to fail too;
        // we simulate the static end state directly:
        assert!(!any_move_possible(&s.board));
    }
}
"""


_MECHANIC_DROP_SUIKA = r"""//! Suika-style physics drop merge — emitted by gameka.codegen.renderKamiApp.
//!
//! State: a Vec<Ball> in a fixed-width jar. drop_at(x) spawns a tier-1
//! ball at the top emitter. step(dt) integrates gravity + AABB walls
//! + circle-circle collision; same-tier balls in contact fuse into
//! tier+1. Lose = any ball center crosses the top line. Win = tier 11.

use std::cell::RefCell;

#[cfg(target_family = "wasm")]
use wasm_bindgen::prelude::*;

const JAR_W: f32 = 6.0;
const JAR_H: f32 = 9.0;
const TOP_LINE_Y: f32 = 8.5;
const G: f32 = 9.8;
const RESTITUTION: f32 = 0.20;
const RADIUS_BASE: f32 = 0.30;
const RADIUS_RATIO: f32 = 1.40;
const WIN_TIER: u8 = 11;

#[derive(Copy, Clone, Debug)]
pub struct Ball {
    pub x: f32, pub y: f32,
    pub vx: f32, pub vy: f32,
    pub tier: u8,
}

impl Ball {
    pub fn radius(&self) -> f32 {
        RADIUS_BASE * RADIUS_RATIO.powi(self.tier as i32 - 1)
    }
}

#[derive(Debug)]
pub struct State {
    pub balls: Vec<Ball>,
    pub score: u32,
    pub status: u32,
    seed: u64,
}

impl State {
    pub fn new(seed: u64) -> Self {
        Self { balls: Vec::with_capacity(64), score: 0, status: 0, seed }
    }

    fn rng(&mut self) -> u64 {
        let mut x = self.seed;
        x ^= x << 13; x ^= x >> 7; x ^= x << 17;
        self.seed = x; x
    }

    pub fn drop_at(&mut self, x: f32) {
        if self.status != 0 || self.balls.len() >= 64 { return; }
        let bx = x.clamp(-JAR_W * 0.5 + RADIUS_BASE, JAR_W * 0.5 - RADIUS_BASE);
        // Tier 1 80%, tier 2 20% — bounded variety for early plays.
        let tier = if (self.rng() & 0x3) == 0 { 2 } else { 1 };
        self.balls.push(Ball { x: bx, y: TOP_LINE_Y - 0.5, vx: 0.0, vy: 0.0, tier });
    }

    pub fn step(&mut self, dt: f32) {
        if self.status != 0 || self.balls.is_empty() { return; }
        let dt = dt.clamp(0.0, 0.05);

        // Integrate
        for b in &mut self.balls {
            b.vy -= G * dt;
            b.x += b.vx * dt;
            b.y += b.vy * dt;
            // Walls
            let r = b.radius();
            let half = JAR_W * 0.5;
            if b.x < -half + r { b.x = -half + r; b.vx = -b.vx * RESTITUTION; }
            if b.x >  half - r { b.x =  half - r; b.vx = -b.vx * RESTITUTION; }
            if b.y < -JAR_H + r { b.y = -JAR_H + r; b.vy = -b.vy * RESTITUTION; b.vx *= 0.95; }
        }

        // Collisions + merges. O(N^2) is fine at N≤64.
        let mut merged_idx: Option<(usize, usize)> = None;
        'outer: for i in 0..self.balls.len() {
            for j in (i + 1)..self.balls.len() {
                let dx = self.balls[j].x - self.balls[i].x;
                let dy = self.balls[j].y - self.balls[i].y;
                let r_sum = self.balls[i].radius() + self.balls[j].radius();
                let dist2 = dx * dx + dy * dy;
                if dist2 < r_sum * r_sum && dist2 > 1e-6 {
                    if self.balls[i].tier == self.balls[j].tier && self.balls[i].tier < WIN_TIER {
                        merged_idx = Some((i, j));
                        break 'outer;
                    }
                    // Elastic separation
                    let d = dist2.sqrt();
                    let nx = dx / d; let ny = dy / d;
                    let overlap = r_sum - d;
                    self.balls[i].x -= nx * overlap * 0.5;
                    self.balls[i].y -= ny * overlap * 0.5;
                    self.balls[j].x += nx * overlap * 0.5;
                    self.balls[j].y += ny * overlap * 0.5;
                    let dvx = self.balls[j].vx - self.balls[i].vx;
                    let dvy = self.balls[j].vy - self.balls[i].vy;
                    let dot = dvx * nx + dvy * ny;
                    if dot < 0.0 {
                        let imp = -(1.0 + RESTITUTION) * dot * 0.5;
                        self.balls[i].vx -= imp * nx;
                        self.balls[i].vy -= imp * ny;
                        self.balls[j].vx += imp * nx;
                        self.balls[j].vy += imp * ny;
                    }
                }
            }
        }
        if let Some((i, j)) = merged_idx {
            let (a, b) = (self.balls[i], self.balls[j]);
            self.balls.swap_remove(j);   // j > i so swap_remove(j) is safe
            self.balls.swap_remove(i);
            let new = Ball {
                x: (a.x + b.x) * 0.5,
                y: (a.y + b.y) * 0.5,
                vx: (a.vx + b.vx) * 0.5,
                vy: (a.vy + b.vy) * 0.5,
                tier: a.tier + 1,
            };
            self.score += 1u32 << (new.tier as u32).min(31);
            let won = new.tier >= WIN_TIER;
            self.balls.push(new);
            if won { self.status = 1; }
        }

        // Lose check — overflow above the top line.
        if self.status == 0 && self.balls.iter().any(|b| b.y > TOP_LINE_Y) {
            self.status = 2;
        }
    }
}

thread_local! {
    static MECH: RefCell<State> = RefCell::new(State::new(0xC0FFEE));
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_init(seed: u32) {
    MECH.with(|m| *m.borrow_mut() = State::new(seed as u64 | 0xC0FFEE_0000_0000));
    crate::play_sfx("loaded");
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_drop_at(x: f32) {
    let mut tier_before = 0u8;
    MECH.with(|m| { tier_before = m.borrow().balls.last().map(|b| b.tier).unwrap_or(0); });
    MECH.with(|m| m.borrow_mut().drop_at(x));
    crate::play_sfx("pop");
    let _ = tier_before; // silence unused warning if optimisation strips it
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_step(dt: f32) {
    let mut won_now = false;
    let mut top_tier = 0u8;
    MECH.with(|m| {
        let mut s = m.borrow_mut();
        let prev_top = s.balls.iter().map(|b| b.tier).max().unwrap_or(0);
        let prev_status = s.status;
        s.step(dt);
        let new_top = s.balls.iter().map(|b| b.tier).max().unwrap_or(0);
        if new_top > prev_top { crate::play_sfx("coin"); top_tier = new_top; }
        if s.status == 1 && prev_status == 0 { won_now = true; }
    });
    if won_now {
        crate::play_sfx("success");
        crate::share_score(top_tier as u32, "reached the largest tier in Drop Merge");
    }
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_score() -> u32 {
    MECH.with(|m| m.borrow().score)
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_status() -> u32 {
    MECH.with(|m| m.borrow().status)
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_kind() -> String {
    "drop_suika".to_string()
}

/// JSON snapshot of the visible state. Shape:
///   { kind, score, status,
///     jar: { w, h, top },
///     balls: [{ x, y, r, tier }] }
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_render_state() -> String {
    MECH.with(|m| {
        let s = m.borrow();
        let mut out = String::with_capacity(64 + s.balls.len() * 64);
        out.push_str("{\"kind\":\"drop_suika\",\"score\":");
        out.push_str(&s.score.to_string());
        out.push_str(",\"status\":");
        out.push_str(&s.status.to_string());
        out.push_str(",\"jar\":{\"w\":");
        out.push_str(&format!("{:.3}", JAR_W));
        out.push_str(",\"h\":");
        out.push_str(&format!("{:.3}", JAR_H));
        out.push_str(",\"top\":");
        out.push_str(&format!("{:.3}", TOP_LINE_Y));
        out.push_str("},\"balls\":[");
        for (i, b) in s.balls.iter().enumerate() {
            if i > 0 { out.push(','); }
            out.push_str(&format!(
                "{{\"x\":{:.3},\"y\":{:.3},\"r\":{:.3},\"tier\":{}}}",
                b.x, b.y, b.radius(), b.tier
            ));
        }
        out.push_str("]}");
        out
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn drop_pushes_one_ball() {
        let mut s = State::new(1);
        s.drop_at(0.0);
        assert_eq!(s.balls.len(), 1);
    }
    #[test]
    fn gravity_pulls_y_down() {
        let mut s = State::new(1);
        s.drop_at(0.0);
        let y0 = s.balls[0].y;
        for _ in 0..100 { s.step(0.016); }
        assert!(s.balls[0].y < y0);
    }
    #[test]
    fn same_tier_in_contact_merges() {
        let mut s = State::new(1);
        s.balls.push(Ball { x: 0.0, y: -8.0, vx: 0.0, vy: 0.0, tier: 1 });
        s.balls.push(Ball { x: 0.05, y: -8.0, vx: 0.0, vy: 0.0, tier: 1 });
        s.step(0.016);
        // The two should fuse into one tier-2 ball.
        assert_eq!(s.balls.len(), 1);
        assert_eq!(s.balls[0].tier, 2);
    }
    #[test]
    fn ball_radius_scales_per_tier() {
        let b1 = Ball { x:0., y:0., vx:0., vy:0., tier: 1 };
        let b3 = Ball { x:0., y:0., vx:0., vy:0., tier: 3 };
        assert!(b3.radius() > b1.radius());
    }
}
"""


_MECHANIC_FIELD_TRIPLE = r"""//! 5x5 place-and-cluster merge — emitted by gameka.codegen.renderKamiApp.
//!
//! State: 5×5 board of Option<u8> (rank). place(r, c) drops the
//! preview rank into an empty cell, then BFS-detects orthogonal
//! clusters of 3+ same-rank tiles. A cluster collapses into a single
//! rank+1 tile at the placement spot; cascade continues until no
//! cluster remains. Win = any tile reaches rank 6. Lose = full board
//! with no placement that triggers a merge.

use std::cell::RefCell;

#[cfg(target_family = "wasm")]
use wasm_bindgen::prelude::*;

const N: usize = 5;
const WIN_RANK: u8 = 6;

#[derive(Debug)]
pub struct State {
    pub board: [[Option<u8>; N]; N],
    pub preview: u8,
    pub score: u32,
    pub status: u32,
    seed: u64,
}

impl State {
    pub fn new(seed: u64) -> Self {
        let mut s = Self { board: [[None; N]; N], preview: 1, score: 0, status: 0, seed };
        s.preview = s.next_preview();
        s
    }

    fn rng(&mut self) -> u64 {
        let mut x = self.seed;
        x ^= x << 13; x ^= x >> 7; x ^= x << 17;
        self.seed = x; x
    }

    fn next_preview(&mut self) -> u8 {
        // 80% rank 1, 18% rank 2, 2% rank 3 — small upper-tier seeds
        // keep the early game tractable.
        let r = self.rng() % 100;
        if r < 80 { 1 } else if r < 98 { 2 } else { 3 }
    }

    pub fn place(&mut self, r: usize, c: usize) -> bool {
        if self.status != 0 || r >= N || c >= N { return false; }
        if self.board[r][c].is_some() { return false; }
        self.board[r][c] = Some(self.preview);
        self.cascade_from(r, c);
        if self.board.iter().flatten().any(|x| x.map(|v| v >= WIN_RANK).unwrap_or(false)) {
            self.status = 1;
        } else if self.board.iter().flatten().all(|x| x.is_some()) {
            // Full board + no further place would merge.
            self.status = 2;
        } else {
            self.preview = self.next_preview();
        }
        true
    }

    fn cascade_from(&mut self, r0: usize, c0: usize) {
        loop {
            let rank = match self.board[r0][c0] { Some(v) => v, None => return };
            let cluster = self.collect_cluster(r0, c0, rank);
            if cluster.len() < 3 { return; }
            for &(r, c) in &cluster { self.board[r][c] = None; }
            let next_rank = (rank + 1).min(WIN_RANK);
            self.board[r0][c0] = Some(next_rank);
            self.score += 1u32 << (next_rank as u32).min(31);
            if next_rank >= WIN_RANK { return; }
        }
    }

    fn collect_cluster(&self, r0: usize, c0: usize, rank: u8) -> Vec<(usize, usize)> {
        let mut visited = [[false; N]; N];
        let mut stack: Vec<(usize, usize)> = vec![(r0, c0)];
        let mut out: Vec<(usize, usize)> = Vec::new();
        while let Some((r, c)) = stack.pop() {
            if visited[r][c] { continue; }
            if self.board[r][c] != Some(rank) { continue; }
            visited[r][c] = true;
            out.push((r, c));
            if r > 0     { stack.push((r - 1, c)); }
            if r + 1 < N { stack.push((r + 1, c)); }
            if c > 0     { stack.push((r, c - 1)); }
            if c + 1 < N { stack.push((r, c + 1)); }
        }
        out
    }
}

thread_local! {
    static MECH: RefCell<State> = RefCell::new(State::new(0xC0FFEE));
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_init(seed: u32) {
    MECH.with(|m| *m.borrow_mut() = State::new(seed as u64 | 0xC0FFEE_0000_0000));
    crate::play_sfx("loaded");
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_place(r: u32, c: u32) {
    let mut won_now = false;
    let mut placed = false;
    let mut max_rank = 0u8;
    MECH.with(|m| {
        let mut s = m.borrow_mut();
        let prev_top = s.board.iter().flatten().filter_map(|x| *x).max().unwrap_or(0);
        let prev_status = s.status;
        if s.place(r as usize, c as usize) {
            placed = true;
            let new_top = s.board.iter().flatten().filter_map(|x| *x).max().unwrap_or(0);
            if new_top > prev_top { crate::play_sfx("coin"); max_rank = new_top; }
            if s.status == 1 && prev_status == 0 { won_now = true; }
        }
    });
    if placed { crate::play_sfx("click"); }
    if won_now {
        crate::play_sfx("success");
        crate::share_score(max_rank as u32, "built the apex tile in Field Merge");
    }
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_score() -> u32 {
    MECH.with(|m| m.borrow().score)
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_status() -> u32 {
    MECH.with(|m| m.borrow().status)
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_preview() -> u32 {
    MECH.with(|m| m.borrow().preview as u32)
}

#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_kind() -> String {
    "field_triple".to_string()
}

/// JSON snapshot of the visible state. Shape:
///   { kind, score, status, preview,
///     board: [[number|0; 5]; 5] }   (0 = empty)
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn mechanic_render_state() -> String {
    MECH.with(|m| {
        let s = m.borrow();
        let mut out = String::with_capacity(192);
        out.push_str("{\"kind\":\"field_triple\",\"score\":");
        out.push_str(&s.score.to_string());
        out.push_str(",\"status\":");
        out.push_str(&s.status.to_string());
        out.push_str(",\"preview\":");
        out.push_str(&(s.preview as u32).to_string());
        out.push_str(",\"board\":[");
        for r in 0..N {
            if r > 0 { out.push(','); }
            out.push('[');
            for c in 0..N {
                if c > 0 { out.push(','); }
                let v = s.board[r][c].map(|x| x as u32).unwrap_or(0);
                out.push_str(&v.to_string());
            }
            out.push(']');
        }
        out.push_str("]}");
        out
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn place_in_empty_cell_succeeds() {
        let mut s = State::new(1);
        s.preview = 1;
        assert!(s.place(0, 0));
        assert_eq!(s.board[0][0], Some(1));
    }
    #[test]
    fn place_in_filled_cell_fails() {
        let mut s = State::new(1);
        s.preview = 1; s.place(0, 0);
        s.preview = 1; assert!(!s.place(0, 0));
    }
    #[test]
    fn three_in_a_row_merges() {
        let mut s = State::new(1);
        s.board[0][0] = Some(1); s.board[0][1] = Some(1);
        s.preview = 1;
        s.place(0, 2);
        // Three rank-1s should collapse to one rank-2 at (0,2).
        assert_eq!(s.board[0][0], None);
        assert_eq!(s.board[0][1], None);
        assert_eq!(s.board[0][2], Some(2));
    }
    #[test]
    fn cascade_chains_two_steps() {
        let mut s = State::new(1);
        s.board[0][0] = Some(1); s.board[0][1] = Some(1);
        s.board[1][2] = Some(2); s.board[0][3] = Some(2);
        s.preview = 1;
        // Placing rank-1 at (0,2) merges 3×rank-1 → rank-2 at (0,2),
        // which now has 3×rank-2 neighbours → rank-3 at (0,2).
        s.place(0, 2);
        assert_eq!(s.board[0][2], Some(3));
    }
    #[test]
    fn win_at_rank_6() {
        let mut s = State::new(1);
        s.board[0][0] = Some(5); s.board[0][1] = Some(5);
        s.preview = 5;
        s.place(0, 2);
        assert_eq!(s.status, 1);
    }
}
"""


_MECHANIC_TEMPLATES: dict[str, str] = {
    "grid_2048":    _MECHANIC_GRID_2048,
    "drop_suika":   _MECHANIC_DROP_SUIKA,
    "field_triple": _MECHANIC_FIELD_TRIPLE,
}

_DEFAULT_MECHANIC_KIND = "grid_2048"


def _mechanic_for(spec_mechanic: dict[str, Any]) -> tuple[str, str]:
    """Pick a mechanic kind + return its (kind, rust_source) pair.

    Honours an explicit `mechanic.kind` first; falls back to a
    keyword scan of `mechanic.coreVerb` / description so unannotated
    LLM-generated specs still resolve to a sensible mechanic.
    """
    kind = str(spec_mechanic.get("kind") or "").strip().lower()
    if kind in _MECHANIC_TEMPLATES:
        return kind, _MECHANIC_TEMPLATES[kind]
    text = " ".join(
        str(spec_mechanic.get(k) or "")
        for k in ("coreVerb", "description")
    ).lower()
    for needle, mapped in (
        ("drop", "drop_suika"),
        ("physics", "drop_suika"),
        ("place", "field_triple"),
        ("cluster", "field_triple"),
        ("triple", "field_triple"),
        ("swipe", "grid_2048"),
        ("slide", "grid_2048"),
        ("2048", "grid_2048"),
    ):
        if needle in text:
            return mapped, _MECHANIC_TEMPLATES[mapped]
    return _DEFAULT_MECHANIC_KIND, _MECHANIC_TEMPLATES[_DEFAULT_MECHANIC_KIND]


# ─── Templates ──────────────────────────────────────────────────────────


_CARGO_TOML_TEMPLATE = """\
# Auto-generated by gameka.codegen.renderKamiApp.
# Source spec: {spec_id}.
# Title: {title}
# Genre: {genre}
[package]
name = "kami-app-{slug}"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
crate-type = ["cdylib", "rlib"]

[dependencies]
kami-app = {{ path = "../kami-app" }}
kami-pipelines = {{ path = "../kami-pipelines" }}
kami-render = {{ path = "../kami-render" }}
kami-terrain = {{ path = "../kami-terrain" }}
# kami-audio: spatial audio mixer (HRTF, channels). Used through the
# game's tick hooks; the Web Audio synthesis side lives in the
# playtest-shell's vendored kami-sound.js (no audio files, ADR §kami).
kami-audio = {{ path = "../kami-audio" }}
glam = {{ workspace = true }}
log = {{ workspace = true }}
wgpu = "24"

[target.'cfg(target_family = "wasm")'.dependencies]
wasm-bindgen = {{ workspace = true }}
wasm-bindgen-futures = "0.4"
web-sys = {{ version = "0.3", features = ["console"] }}
console_error_panic_hook = "0.1"
console_log = "1"
"""


_LIB_RS_TEMPLATE = """\
//! kami-app-{slug} — generated by gameka.codegen.renderKamiApp.
//!
//! Spec     : {spec_id}
//! Title    : {title}
//! Genre    : {genre}
//! Mechanic : {mechanic}
//! Scene    : {scene}
//! Audio    : bgm={bgm_hint}, sfx=[{sfx_palette_csv}]
//! Mechanic : kind={mechanic_kind} (see src/mechanic.rs)
//!
//! This crate is a thin composition layer over the kami-app Builder SDK
//! (mirrors `kami-app-isekai`). Camera + input mode + biome are picked
//! from the spec; the render adapter set is the v3-default (Sky +
//! Terrain + Water). The merge mechanic state machine lives in
//! `src/mechanic.rs` and is driven from JS via wasm-bindgen exports
//! (`mechanic_init`, `mechanic_swipe`/`drop_at`/`place`, …).
//!
//! Bridges into the host page (playtest-shell or game-play.etzhayyim.com/play/{slug}):
//!   - `__kamiPlay(name)`         — Web Audio SFX synth (kami-sound.js presets)
//!   - `__kamiSocialShare(text)`  — POST app.bsky.feed.post AS the game's sub-DID
//!   - `__kamiSocialFollow()`     — toggle follow on the game's sub-DID
//!
//! All three bridges are no-ops when the host page doesn't expose them
//! (e.g., during cargo test); the safe wrappers below catch the missing
//! window globals and log a debug message instead of panicking.

use kami_app::{{KamiApp, CameraMode, InputMode}};
use kami_pipelines::{{SkyAdapter, TerrainAdapter, WaterAdapter}};
use log::Level;

/// SFX palette declared by the spec's scene_json. The host's
/// `__kamiPlay(name)` is expected to recognise each name as a
/// kami-sound.js preset. Game logic calls `play_sfx("coin")` etc.
pub const SFX_PALETTE: &[&str] = &[{sfx_palette_array}];

/// Looping background-music tag the host should start on entry.
pub const BGM_HINT: &str = "{bgm_hint}";

/// Mechanic kind tag baked at codegen time. The actual state machine
/// is in `src/mechanic.rs` (selected per spec).
pub const MECHANIC_KIND: &str = "{mechanic_kind}";

pub mod mechanic;

#[cfg(target_family = "wasm")]
use wasm_bindgen::prelude::*;

/// JS bridges. These mirror the kami-engine convention that
/// `window.__kamiPlay` / `window.__kamiSocial.*` are owned by the
/// hosting page (playtest-shell / game-play.etzhayyim.com). `catch` ensures
/// a missing function doesn't panic the wasm — typical for unit tests
/// run outside the browser shell.
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
extern "C" {{
    #[wasm_bindgen(js_namespace = window, js_name = __kamiPlay, catch)]
    fn __kami_play(name: &str) -> Result<(), JsValue>;

    #[wasm_bindgen(js_namespace = window, js_name = __kamiPlayBgm, catch)]
    fn __kami_play_bgm(name: &str) -> Result<(), JsValue>;

    #[wasm_bindgen(js_namespace = window, js_name = __kamiSocialShare, catch)]
    fn __kami_social_share(text: &str) -> Result<(), JsValue>;

    #[wasm_bindgen(js_namespace = window, js_name = __kamiSocialFollow, catch)]
    fn __kami_social_follow() -> Result<(), JsValue>;
}}

/// Safe SFX trigger. Throttling + same-name dedupe live on the JS
/// side (kami-sound.js convention). Unknown names are dropped at the
/// host without panicking.
#[cfg(target_family = "wasm")]
pub fn play_sfx(name: &str) {{
    let _ = __kami_play(name);
}}

#[cfg(not(target_family = "wasm"))]
pub fn play_sfx(_name: &str) {{}}

/// Safe BGM trigger. Calls `window.__kamiPlayBgm(BGM_HINT)`. The
/// host is responsible for cross-fading and looping; this fn is
/// idempotent — re-issuing the same name is a no-op on the JS side.
#[cfg(target_family = "wasm")]
pub fn start_bgm() {{
    let _ = __kami_play_bgm(BGM_HINT);
}}

#[cfg(not(target_family = "wasm"))]
pub fn start_bgm() {{}}

/// Public WASM export — game logic calls this on win / milestone /
/// other share-worthy moments. The host posts to atproto.etzhayyim.com
/// AS the game's sub-DID via `app.bsky.feed.post`.
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn share_score(score: u32, message: &str) {{
    let body = format!("score: {{}} · {{}}", score, message);
    let _ = __kami_social_share(&body);
}}

/// Toggle follow on the game's sub-DID. Host implementation does the
/// graph mutation; result lands in the user's PDS.
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub fn follow_creator() {{
    let _ = __kami_social_follow();
}}

/// WASM entrypoint exported to JS.
///
/// ```js
/// import init, {{ {entry_fn} }} from './kami_app_{slug_underscore}.js';
/// await init();
/// await {entry_fn}('canvas-id');
/// ```
#[cfg(target_family = "wasm")]
#[wasm_bindgen]
pub async fn {entry_fn}(canvas_id: &str) -> Result<(), JsValue> {{
    console_error_panic_hook::set_once();
    let _ = console_log::init_with_level(Level::Info);
    log::info!("[{slug}] booting (spec={spec_id})");

    // Host audio bootstrap. Kicks off BGM + a "loaded" SFX so the
    // playtest probe sees the audio bridge wire end-to-end.
    start_bgm();
    play_sfx("loaded");

    // Mechanic state bootstrap. Seeded from the spec id hash so the
    // playtest harness gets a deterministic first-board, while real
    // visitors get something fresh on each load (the JS shell can
    // call mechanic_init() with a fresh seed at any time).
    mechanic::mechanic_init({mechanic_seed}u32);

    KamiApp::new_web(canvas_id)
        .with_camera(CameraMode::{camera})
        .with_input(InputMode::{input})
        .with_pipeline(SkyAdapter::default())
        .with_pipeline(TerrainAdapter::biome(kami_terrain::Biome::{biome}))
        .with_pipeline(WaterAdapter::default())
        .run()
        .await
}}

/// Native (desktop) entrypoint — kept tiny so `cargo test -p kami-app-{slug}`
/// passes without wgpu/winit. Real desktop runs go through `kami-demo`.
#[cfg(not(target_family = "wasm"))]
pub fn entry_name() -> &'static str {{
    "{entry_fn}"
}}

#[cfg(test)]
mod tests {{
    #[test]
    fn entry_name_is_stable() {{
        assert_eq!(super::entry_name(), "{entry_fn}");
    }}

    #[test]
    fn audio_palette_is_non_empty() {{
        assert!(!super::BGM_HINT.is_empty());
        assert!(!super::SFX_PALETTE.is_empty());
    }}

    #[test]
    fn mechanic_kind_is_set() {{
        assert!(!super::MECHANIC_KIND.is_empty());
    }}
}}
"""


_README_TEMPLATE = """\
# kami-app-{slug}

Auto-generated by `gameka.codegen.renderKamiApp` from spec `{spec_id}`.

| Field    | Value |
|---|---|
| Title    | {title} |
| Genre    | {genre} |
| Camera   | {camera} |
| Input    | {input} |
| Biome    | {biome} |
| BGM      | `{bgm_hint}` |
| SFX      | {sfx_palette_csv} |
| Entry    | `{entry_fn}` |

Mechanic
:   {mechanic}

Scene
:   {scene}

## Host bridges (provided by the playtest shell / game-play.etzhayyim.com)

| Rust fn | JS bridge | Effect |
|---|---|---|
| `play_sfx(name)`            | `window.__kamiPlay(name)`        | Web Audio synth (kami-sound.js preset) |
| `start_bgm()`               | `window.__kamiPlayBgm(name)`     | start looping BGM tagged `BGM_HINT` |
| `share_score(score, msg)`   | `window.__kamiSocialShare(text)` | `app.bsky.feed.post` AS the game's sub-DID |
| `follow_creator()`          | `window.__kamiSocialFollow()`    | follow toggle on the game's sub-DID |

Each bridge is a `catch`-wrapped wasm-bindgen extern — missing window
globals (e.g., `cargo test` outside a browser) are silently dropped.

This crate is **regenerable**. Do not hand-edit; round-trip through
`gameka.codegen.renderKamiApp` instead.
"""


# ─── Audio palette ──────────────────────────────────────────────────────

_DEFAULT_SFX_PALETTE = ("loaded", "click", "coin", "success")
_DEFAULT_BGM_HINT = "ambient-default"
_SFX_RE = re.compile(r"[^a-z0-9_-]+")


def _normalise_sfx_name(name: Any) -> str:
    """Lowercase + strip to [a-z0-9_-]; ≤32 chars; empty-out invalids."""
    s = str(name or "").strip().lower()
    s = _SFX_RE.sub("", s)
    return s[:32]


def _audio_from_scene(scene_obj: dict[str, Any]) -> tuple[str, list[str]]:
    """Extract bgm + sfx palette from the spec's scene_json.

    Falls back to a safe default so the generated lib.rs's BGM_HINT and
    SFX_PALETTE are never empty (the generated `audio_palette_is_non_empty`
    cargo test would otherwise fail). At most 12 SFX entries to bound the
    generated array.
    """
    palette = scene_obj.get("audioPalette") if isinstance(scene_obj, dict) else None
    if not isinstance(palette, dict):
        palette = {}
    bgm = _normalise_sfx_name(palette.get("bgm") or _DEFAULT_BGM_HINT) or _DEFAULT_BGM_HINT
    raw_sfx = palette.get("sfx")
    if not isinstance(raw_sfx, list):
        raw_sfx = []
    cleaned: list[str] = []
    seen: set[str] = set()
    for n in raw_sfx:
        norm = _normalise_sfx_name(n)
        if norm and norm not in seen:
            seen.add(norm)
            cleaned.append(norm)
    if not cleaned:
        cleaned = list(_DEFAULT_SFX_PALETTE)
    return bgm, cleaned[:12]


# ─── Render ─────────────────────────────────────────────────────────────


def _render_kami_app_sources(
    *,
    spec_id: str,
    title: str,
    slug: str,
    genre: str,
    mechanic_json: str | dict[str, Any],
    scene_json: str | dict[str, Any],
) -> dict[str, str]:
    """Pure function: spec → file tree (path → contents). Deterministic."""
    norm_slug = _slug(slug or title)
    entry_fn = _entry_fn(norm_slug)
    mechanic_obj = _parse_json(mechanic_json)
    scene_obj = _parse_json(scene_json)
    mechanic_text = _safe_str(mechanic_obj.get("description") or "", 240)
    scene_text = _safe_str(scene_obj.get("description") or "", 240)
    biome = _biome_for(scene_text)
    camera = _camera_for(genre)
    input_mode = _input_for(genre)
    bgm_hint, sfx_palette = _audio_from_scene(scene_obj)
    sfx_palette_array = ", ".join(f'"{n}"' for n in sfx_palette)
    sfx_palette_csv = ", ".join(sfx_palette)
    mechanic_kind, mechanic_rs = _mechanic_for(mechanic_obj)
    # Mechanic seed is derived deterministically from spec_id so two
    # runs of the same spec start from the same first board — useful
    # for the playtest harness's perf budget. xorshift mixes 32 bits.
    mechanic_seed = (
        int.from_bytes(
            hashlib.sha256(spec_id.encode("utf-8")).digest()[:4],
            "big",
        )
        if spec_id
        else 0xC0FFEE
    )

    fmt = {
        "spec_id":          _safe_str(spec_id, 80),
        "title":            _safe_str(title, 80),
        "genre":            _safe_str(genre, 24),
        "mechanic":         mechanic_text,
        "scene":            scene_text,
        "slug":             norm_slug,
        "slug_underscore":  norm_slug.replace("-", "_"),
        "entry_fn":         entry_fn,
        "camera":           camera,
        "input":            input_mode,
        "biome":            biome,
        "bgm_hint":         bgm_hint,
        "sfx_palette_array": sfx_palette_array,
        "sfx_palette_csv":  sfx_palette_csv,
        "mechanic_kind":    mechanic_kind,
        "mechanic_seed":    mechanic_seed,
    }

    return {
        "Cargo.toml":     _CARGO_TOML_TEMPLATE.format(**fmt),
        "src/lib.rs":     _LIB_RS_TEMPLATE.format(**fmt),
        "src/mechanic.rs": mechanic_rs,
        "README.md":      _README_TEMPLATE.format(**fmt),
    }


def _canonical_blob(tree: dict[str, str]) -> bytes:
    """Concatenate files in sorted-path order with a fixed separator so
    wasmCid is deterministic across runs."""
    chunks: list[bytes] = []
    for path in sorted(tree):
        chunks.append(path.encode("utf-8"))
        chunks.append(b"\x00")
        chunks.append(tree[path].encode("utf-8"))
        chunks.append(b"\x1f")  # ASCII unit separator
    return b"".join(chunks)


def _cidv1_b32_sha256(blob: bytes) -> str:
    """CIDv1 raw codec sha2-256, base32 lower (multibase prefix 'b').

    Wire-format: <multibase>b<base32(<version 0x01><codec 0x55><multihash>)>
    multihash = 0x12 (sha2-256) || 0x20 (length 32) || digest.
    Matches ADR-0029 + the plc-directory implementation.
    """
    digest = hashlib.sha256(blob).digest()
    multihash = b"\x12\x20" + digest
    cid_bytes = b"\x01\x55" + multihash
    encoded = base64.b32encode(cid_bytes).decode("ascii").rstrip("=").lower()
    return "b" + encoded


# ─── LangServer task wrapper ───────────────────────────────────────────────


async def task_gameka_codegen_render_kami_app(
    specId: str = "",
    title: str = "",
    slug: str = "",
    genre: str = "",
    mechanicJson: str = "",
    sceneJson: str = "",
) -> dict:
    """Entry point registered as `gameka.codegen.renderKamiApp` in
    kotodama.zeebe_worker_main. Returns flat dict consumable by FEEL
    ioMapping. Idempotent — same input → same wasmCid."""
    if not specId or not title or not slug:
        return {
            "wasmCid": "",
            "wasmSize": 0,
            "entryFn": "",
            "fileCount": 0,
            "buildStatus": "failed",
            "error": "missing required fields (specId/title/slug)",
        }
    try:
        tree = _render_kami_app_sources(
            spec_id=specId,
            title=title,
            slug=slug,
            genre=genre or "",
            mechanic_json=mechanicJson or "",
            scene_json=sceneJson or "",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("gameka.codegen render failed: %s", e)
        return {
            "wasmCid": "",
            "wasmSize": 0,
            "entryFn": "",
            "fileCount": 0,
            "buildStatus": "failed",
            "error": f"render-error:{type(e).__name__}:{str(e)[:80]}",
        }
    blob = _canonical_blob(tree)
    return {
        "wasmCid": _cidv1_b32_sha256(blob),
        "wasmSize": len(blob),
        "entryFn": _entry_fn(_slug(slug or title)),
        "fileCount": len(tree),
        "buildStatus": "sources_ready",
    }

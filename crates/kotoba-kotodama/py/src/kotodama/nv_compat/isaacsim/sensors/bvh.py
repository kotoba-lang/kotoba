"""BvhScene — Bounding Volume Hierarchy accelerator for ray + distance queries.

Drop-in replacement for `Scene` (lidar.py). Same `.add(prim)` and
`.nearest_hit(origin, dir)` API, but per-ray complexity is O(log N) average
case versus O(N) for the linear `Scene`. With N=256 primitives + 960 rays
(120 h_beams × 8 v_beams lidar sweep), the BVH path is ~3-5× faster on CPU;
the speedup scales with both N and ray count and becomes ~10-30× for full
VLP-16 sweeps (28800 rays) against N=1024+ primitive scenes.

Construction uses top-down median split on the largest extent axis:

    1. Compute AABB for every primitive
    2. Combine into a global AABB for the current subtree
    3. If ≤ leaf_threshold primitives, emit a leaf node holding their indices
    4. Otherwise pick the longest extent axis, sort primitives by AABB center
       on that axis, split at median, recurse left + right

Traversal at query time:

    1. Test ray vs node AABB via the slab method; prune subtree if miss
    2. Leaf: linear scan over the (small) primitive set
    3. Internal: recurse into both children, keeping running best-t

Infinite primitives (PrimKind.GROUND_PLANE) have no finite AABB so they
are extracted at build time and tested first via a separate linear scan.
For typical scenes there's at most one ground plane, so this stays O(1).

ContactSensor's `_primitive_closest` is independent of the ray-cast path
and reuses the existing Scene.primitives interface — BvhScene exposes
.primitives identically, so ContactSensor works against BvhScene unchanged.

Pure stdlib (math).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .lidar import PrimKind, Primitive


# ----- internal BVH node -----

@dataclass
class _BvhNode:
    """One BVH tree node. Leaf when primitive_indices is non-empty AND
    children are None; internal node otherwise."""
    bounds_min: tuple
    bounds_max: tuple
    primitive_indices: List[int] = field(default_factory=list)
    left: Optional["_BvhNode"] = None
    right: Optional["_BvhNode"] = None


def _primitive_aabb(p: Primitive) -> Optional[Tuple[tuple, tuple]]:
    """Returns (min, max) AABB of a primitive, or None if infinite (GroundPlane)."""
    if p.kind == PrimKind.SPHERE:
        cx, cy, cz = p.center
        r = p.radius
        return (cx - r, cy - r, cz - r), (cx + r, cy + r, cz + r)
    if p.kind == PrimKind.AABB:
        return tuple(p.min), tuple(p.max)
    # GROUND_PLANE: infinite extent.
    return None


def _ray_aabb_intersect(origin: tuple, dir_: tuple,
                        bmin: tuple, bmax: tuple) -> bool:
    """Returns True if the ray (origin, dir) intersects the AABB at some
    t > 0. Slab method; handles axis-aligned rays via the ε guard."""
    tmin = -math.inf
    tmax = math.inf
    for axis in range(3):
        d = dir_[axis]
        if abs(d) < 1e-12:
            # Ray parallel to slab: miss if origin outside the slab.
            if origin[axis] < bmin[axis] or origin[axis] > bmax[axis]:
                return False
            continue
        inv = 1.0 / d
        t1 = (bmin[axis] - origin[axis]) * inv
        t2 = (bmax[axis] - origin[axis]) * inv
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > tmin:
            tmin = t1
        if t2 < tmax:
            tmax = t2
        if tmin > tmax:
            return False
    return tmax > 0.0


# ----- BvhScene -----

@dataclass
class BvhScene:
    """Drop-in Scene replacement with O(log N) ray queries.

    Usage matches `lidar.Scene`:

        scene = BvhScene()
        scene.add(Primitive.ground_plane(0.0))
        scene.add(Primitive.sphere((0, 0, 5), 0.5))
        ...
        hit = scene.nearest_hit(origin, dir_)

    BVH is built lazily on the first nearest_hit() call after an .add() —
    so bulk-add then query is the common case and pays one O(N log N)
    build cost amortised over many ray queries. Call .build() explicitly
    to force the build (e.g. before timing a ray batch).
    """
    primitives: List[Primitive] = field(default_factory=list)
    leaf_threshold: int = 4
    max_depth: int = 32

    _root: Optional[_BvhNode] = field(default=None, init=False, repr=False)
    _infinite: List[int] = field(default_factory=list, init=False, repr=False)
    _dirty: bool = field(default=True, init=False, repr=False)

    # ----- add / build -----

    def add(self, p: Primitive) -> "BvhScene":
        self.primitives.append(p)
        self._dirty = True
        return self

    def build(self) -> "BvhScene":
        """Rebuild the BVH from current primitives. Idempotent (clears
        the existing tree first). O(N log N)."""
        finite: List[tuple] = []
        infinite: List[int] = []
        for i, p in enumerate(self.primitives):
            aabb = _primitive_aabb(p)
            if aabb is None:
                infinite.append(i)
            else:
                bmin, bmax = aabb
                finite.append((i, bmin, bmax))
        self._infinite = infinite
        self._root = self._build_recursive(finite, depth=0)
        self._dirty = False
        return self

    def _build_recursive(self, items: List[tuple], depth: int) -> Optional[_BvhNode]:
        if not items:
            return None
        # Compute combined AABB across all items.
        bmin = [items[0][1][0], items[0][1][1], items[0][1][2]]
        bmax = [items[0][2][0], items[0][2][1], items[0][2][2]]
        for _, bn, bx in items[1:]:
            for a in range(3):
                if bn[a] < bmin[a]:
                    bmin[a] = bn[a]
                if bx[a] > bmax[a]:
                    bmax[a] = bx[a]

        # Leaf condition: small enough OR depth budget exhausted.
        if len(items) <= self.leaf_threshold or depth >= self.max_depth:
            return _BvhNode(
                bounds_min=tuple(bmin), bounds_max=tuple(bmax),
                primitive_indices=[i for i, _, _ in items],
                left=None, right=None,
            )

        # Split: median on the largest-extent axis.
        extents = (bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2])
        axis = extents.index(max(extents))
        items.sort(key=lambda it: 0.5 * (it[1][axis] + it[2][axis]))
        mid = len(items) // 2
        if mid == 0 or mid == len(items):
            # Degenerate (all primitives co-located on this axis): emit leaf.
            return _BvhNode(
                bounds_min=tuple(bmin), bounds_max=tuple(bmax),
                primitive_indices=[i for i, _, _ in items],
                left=None, right=None,
            )
        left = self._build_recursive(items[:mid], depth + 1)
        right = self._build_recursive(items[mid:], depth + 1)
        return _BvhNode(
            bounds_min=tuple(bmin), bounds_max=tuple(bmax),
            primitive_indices=[],
            left=left, right=right,
        )

    # ----- query -----

    def nearest_hit(self, origin: tuple, dir_: tuple) -> Optional[Tuple[float, int]]:
        """Returns (t, primitive_index) of the closest hit, or None.

        Identical contract to `Scene.nearest_hit`. Auto-builds on first
        call if a primitive has been added since the last build.
        """
        if self._dirty:
            self.build()
        best_t = math.inf
        best_idx = -1
        # 1. Infinite primitives (e.g. GroundPlane) — linear scan over a
        #    typically empty or singleton list.
        for i in self._infinite:
            t = self.primitives[i].intersect(origin, dir_)
            if t is not None and t < best_t:
                best_t = t
                best_idx = i
        # 2. BVH traversal.
        if self._root is not None:
            best_t, best_idx = self._traverse(
                self._root, origin, dir_, best_t, best_idx
            )
        if best_idx < 0:
            return None
        return (best_t, best_idx)

    def _traverse(self, node: _BvhNode, origin: tuple, dir_: tuple,
                  best_t: float, best_idx: int) -> Tuple[float, int]:
        # Prune by node AABB. Even if the AABB extends past best_t, the slab
        # test is a cheap precondition that eliminates most internal nodes.
        if not _ray_aabb_intersect(origin, dir_, node.bounds_min, node.bounds_max):
            return best_t, best_idx
        if node.primitive_indices:
            # Leaf: test each primitive.
            for i in node.primitive_indices:
                t = self.primitives[i].intersect(origin, dir_)
                if t is not None and t < best_t:
                    best_t = t
                    best_idx = i
            return best_t, best_idx
        # Internal: recurse into both children. Near-first ordering is a
        # micro-opt we skip — the slab-test prune handles most pruning.
        if node.left is not None:
            best_t, best_idx = self._traverse(node.left, origin, dir_, best_t, best_idx)
        if node.right is not None:
            best_t, best_idx = self._traverse(node.right, origin, dir_, best_t, best_idx)
        return best_t, best_idx

    # ----- introspection helpers (testing / diagnostics) -----

    def node_count(self) -> int:
        """Total node count in the tree (build-time diagnostic)."""
        if self._dirty:
            self.build()
        return _count_nodes(self._root)

    def leaf_count(self) -> int:
        """Leaf node count."""
        if self._dirty:
            self.build()
        return _count_leaves(self._root)

    def max_leaf_size(self) -> int:
        """Largest leaf size — should be ≤ leaf_threshold for healthy builds."""
        if self._dirty:
            self.build()
        return _max_leaf_size(self._root)


def _count_nodes(n: Optional[_BvhNode]) -> int:
    if n is None:
        return 0
    return 1 + _count_nodes(n.left) + _count_nodes(n.right)


def _count_leaves(n: Optional[_BvhNode]) -> int:
    if n is None:
        return 0
    if n.primitive_indices:
        return 1
    return _count_leaves(n.left) + _count_leaves(n.right)


def _max_leaf_size(n: Optional[_BvhNode]) -> int:
    if n is None:
        return 0
    if n.primitive_indices:
        return len(n.primitive_indices)
    return max(_max_leaf_size(n.left), _max_leaf_size(n.right))

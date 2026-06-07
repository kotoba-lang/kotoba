"""NVIDIA Warp® kernel-API parity stubs — single-threaded Python execution.

Mirror of `warp` (Warp 1.x) — the SIMT kernel framework that Isaac Lab uses
heavily for parallel MDP event / reward / observation functions. Real Warp
JIT-compiles `@wp.kernel`-decorated Python functions to CUDA / Vulkan /
WebGPU and dispatches them as N-way parallel grids.

This stub provides the SAME PUBLIC API SURFACE so Isaac Lab task definitions
that reference `wp.kernel` / `wp.launch` / `wp.array` / `wp.vec3` / `wp.quat`
/ `wp.transform` / atomic ops parse + import + RUN — but execution is
sequential pure-Python (`for i in range(dim): kernel(*inputs)`). Performance
is bad; semantics are correct. A future iter swaps the executor for a
WebGPU compute-shader backend; the API surface stays.

Trademark: "NVIDIA®" and "Warp®" are trademarks of NVIDIA Corporation.
Per ADR-2605261800 §D6 this is API namespace localization for
interoperability purposes only (Google v. Oracle 2021 — API fair use).
The canonical religious-corp equivalent will live under
`kami-warp` (40-engine/kami-warp/) when it ships in R2+.

API surface covered:

  Decorators / launch:
    @wp.kernel             — mark a function as a Warp kernel (no-op shim)
    @wp.func               — mark a helper function (no-op shim)
    wp.launch(...)         — sequential N-way "grid" dispatch
    wp.tid()               — thread index inside a kernel body
    wp.init()              — module init (no-op)
    wp.config              — config namespace (mode / verify_cuda — no-op)

  Scalar dtypes (type-marker sentinels — used as type annotations):
    wp.float32, wp.float64, wp.int32, wp.int64, wp.uint32, wp.bool, wp.uint8

  Container dtypes:
    wp.array(data=[...] | shape=N, dtype=...)
    wp.zeros(shape, dtype=wp.float32)
    wp.empty(shape, dtype=wp.float32)

  Linear-algebra value types (pure Python tuples-with-arithmetic):
    wp.vec3, wp.vec4
    wp.quat (Hamilton, x,y,z,w convention — matches Isaac Lab)
    wp.mat33
    wp.transform (translation + quat)

  Math (scalar):
    wp.sin / wp.cos / wp.tan / wp.atan2 / wp.sqrt / wp.abs / wp.min / wp.max
    wp.clamp / wp.floor / wp.ceil / wp.exp / wp.log
    wp.pi

  Math (vec / quat / transform):
    wp.length / wp.length_sq / wp.normalize / wp.dot / wp.cross
    wp.quat_identity / wp.quat_from_axis_angle / wp.quat_inverse /
    wp.quat_rotate / wp.quat_rotate_inv / wp.quat_mul
    wp.transform_identity / wp.transform_point / wp.transform_vector /
    wp.transform_get_translation / wp.transform_get_rotation /
    wp.transform_multiply

  Atomic ops (no-op single-threaded; matches semantics under sequential exec):
    wp.atomic_add / wp.atomic_sub / wp.atomic_max / wp.atomic_min

  Indexing:
    wp.index(arr, i)        — alternative array read (parity with real wp)

stdlib-only. No numpy / torch / Warp / WebGPU bindings.
"""

from __future__ import annotations

import math as _math
import threading as _threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

# Capture Python builtins BEFORE we shadow them below with wp.bool / wp.min /
# wp.max etc. Used by the dtype constructors and the vec-aware min/max.
_py_bool = bool
_py_min = min
_py_max = max
_py_abs = abs


# ── module-level constants ─────────────────────────────────────────────────

pi = _math.pi


# ── thread-local kernel state ──────────────────────────────────────────────

_local = _threading.local()


def _current_tid() -> int:
    """Return the current thread index inside an in-flight kernel launch.

    Raises RuntimeError when called outside `wp.launch`.
    """
    tid = getattr(_local, "tid", None)
    if tid is None:
        raise RuntimeError(
            "wp.tid() called outside of an active wp.launch — "
            "kernel functions must run via wp.launch(kernel=..., dim=..., inputs=[...])"
        )
    return tid


def tid() -> int:
    """Thread index inside a Warp kernel body (matches real `wp.tid()`)."""
    return _current_tid()


# ── dtype sentinels ────────────────────────────────────────────────────────


class _DtypeMarker:
    """Sentinel for Warp scalar dtypes. Functions as a type annotation only —
    arithmetic is delegated to the underlying Python numeric type."""

    def __init__(self, name: str):
        self._name = name

    def __repr__(self) -> str:
        return f"wp.{self._name}"

    def __call__(self, value: Any = 0) -> Any:
        """Constructor — coerces value via Python's underlying numeric type."""
        if self._name in ("float32", "float64"):
            return float(value)
        if self._name in ("int32", "int64", "uint32", "uint8"):
            return int(value)
        if self._name == "bool":
            return _py_bool(value)
        return value


float32 = _DtypeMarker("float32")
float64 = _DtypeMarker("float64")
int32 = _DtypeMarker("int32")
int64 = _DtypeMarker("int64")
uint32 = _DtypeMarker("uint32")
uint8 = _DtypeMarker("uint8")
bool = _DtypeMarker("bool")


# ── config namespace ───────────────────────────────────────────────────────


class _Config:
    """`wp.config.*` namespace (real Warp uses this for CUDA/Vulkan toggles).
    All flags are no-ops in this stub."""

    mode: str = "release"
    verify_cuda: bool = False
    verify_fp: bool = False
    print_launches: bool = False
    cache_kernels: bool = True


config = _Config()


def init() -> None:
    """`wp.init()` — module init. No-op in this stub (real Warp probes CUDA
    drivers + JIT compiles kernel cache)."""
    return None


# ── linear-algebra value types ─────────────────────────────────────────────


def _coerce_vec(x: Any, dim: int) -> List[float]:
    """Coerce arbitrary sequence-like → length-`dim` list[float].

    Accepts a vec3/vec4/list/tuple/single-scalar (broadcast). Pads with
    zeros if shorter, truncates if longer (matches Warp's permissive
    construction)."""
    if hasattr(x, "_components"):
        c = list(x._components)
    elif isinstance(x, (list, tuple)):
        c = [float(v) for v in x]
    else:
        # Scalar broadcast.
        c = [float(x)] * dim
    while len(c) < dim:
        c.append(0.0)
    return c[:dim]


class vec3:
    """3-vector value type (x, y, z) with arithmetic."""

    __slots__ = ("_components",)

    def __init__(self, x: Any = 0.0, y: float = 0.0, z: float = 0.0):
        if isinstance(x, (list, tuple)) and y == 0.0 and z == 0.0:
            self._components = _coerce_vec(x, 3)
        elif hasattr(x, "_components"):
            self._components = _coerce_vec(x, 3)
        else:
            self._components = [float(x), float(y), float(z)]

    @property
    def x(self) -> float: return self._components[0]
    @property
    def y(self) -> float: return self._components[1]
    @property
    def z(self) -> float: return self._components[2]

    def __getitem__(self, i: int) -> float:
        return self._components[i]

    def __setitem__(self, i: int, v: float) -> None:
        self._components[i] = float(v)

    def __iter__(self): return iter(self._components)
    def __len__(self): return 3

    def __add__(self, other: Any) -> "vec3":
        o = _coerce_vec(other, 3)
        return vec3(self._components[0] + o[0], self._components[1] + o[1], self._components[2] + o[2])

    def __sub__(self, other: Any) -> "vec3":
        o = _coerce_vec(other, 3)
        return vec3(self._components[0] - o[0], self._components[1] - o[1], self._components[2] - o[2])

    def __mul__(self, other: Any) -> "vec3":
        if isinstance(other, (int, float)):
            s = float(other)
            return vec3(self._components[0] * s, self._components[1] * s, self._components[2] * s)
        o = _coerce_vec(other, 3)
        return vec3(self._components[0] * o[0], self._components[1] * o[1], self._components[2] * o[2])

    def __rmul__(self, other: Any) -> "vec3":
        return self.__mul__(other)

    def __neg__(self) -> "vec3":
        return vec3(-self._components[0], -self._components[1], -self._components[2])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, vec3):
            return NotImplemented
        return self._components == other._components

    def __repr__(self) -> str:
        return f"vec3({self._components[0]}, {self._components[1]}, {self._components[2]})"


class vec4:
    """4-vector value type (x, y, z, w) — also used as the raw storage for
    quaternions."""

    __slots__ = ("_components",)

    def __init__(self, x: Any = 0.0, y: float = 0.0, z: float = 0.0, w: float = 0.0):
        if isinstance(x, (list, tuple)) and y == 0.0 and z == 0.0 and w == 0.0:
            self._components = _coerce_vec(x, 4)
        elif hasattr(x, "_components"):
            self._components = _coerce_vec(x, 4)
        else:
            self._components = [float(x), float(y), float(z), float(w)]

    @property
    def x(self) -> float: return self._components[0]
    @property
    def y(self) -> float: return self._components[1]
    @property
    def z(self) -> float: return self._components[2]
    @property
    def w(self) -> float: return self._components[3]

    def __getitem__(self, i: int) -> float: return self._components[i]
    def __setitem__(self, i: int, v: float) -> None: self._components[i] = float(v)
    def __iter__(self): return iter(self._components)
    def __len__(self): return 4

    def __add__(self, other: Any) -> "vec4":
        o = _coerce_vec(other, 4)
        return vec4(self._components[0] + o[0], self._components[1] + o[1],
                     self._components[2] + o[2], self._components[3] + o[3])

    def __sub__(self, other: Any) -> "vec4":
        o = _coerce_vec(other, 4)
        return vec4(self._components[0] - o[0], self._components[1] - o[1],
                     self._components[2] - o[2], self._components[3] - o[3])

    def __mul__(self, other: Any) -> "vec4":
        if isinstance(other, (int, float)):
            s = float(other)
            return vec4(self._components[0] * s, self._components[1] * s,
                         self._components[2] * s, self._components[3] * s)
        o = _coerce_vec(other, 4)
        return vec4(self._components[0] * o[0], self._components[1] * o[1],
                     self._components[2] * o[2], self._components[3] * o[3])

    def __rmul__(self, other: Any) -> "vec4":
        return self.__mul__(other)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, vec4):
            return NotImplemented
        return self._components == other._components

    def __repr__(self) -> str:
        c = self._components
        return f"vec4({c[0]}, {c[1]}, {c[2]}, {c[3]})"


class quat:
    """Quaternion (x, y, z, w) — Hamilton convention. Matches Isaac Lab
    + iter 35/41/63 controller convention. Stored as 4 floats."""

    __slots__ = ("_components",)

    def __init__(self, x: Any = 0.0, y: float = 0.0, z: float = 0.0, w: float = 1.0):
        if isinstance(x, (list, tuple)) and y == 0.0 and z == 0.0 and w == 1.0:
            self._components = _coerce_vec(x, 4)
        elif hasattr(x, "_components"):
            self._components = _coerce_vec(x, 4)
        else:
            self._components = [float(x), float(y), float(z), float(w)]

    @property
    def x(self) -> float: return self._components[0]
    @property
    def y(self) -> float: return self._components[1]
    @property
    def z(self) -> float: return self._components[2]
    @property
    def w(self) -> float: return self._components[3]

    def __getitem__(self, i: int) -> float: return self._components[i]
    def __setitem__(self, i: int, v: float) -> None: self._components[i] = float(v)
    def __iter__(self): return iter(self._components)
    def __len__(self): return 4

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, quat):
            return NotImplemented
        return self._components == other._components

    def __repr__(self) -> str:
        c = self._components
        return f"quat({c[0]}, {c[1]}, {c[2]}, {c[3]})"


class mat33:
    """3×3 row-major matrix — list-of-3-lists."""

    __slots__ = ("_rows",)

    def __init__(self, *args: Any):
        if len(args) == 0:
            self._rows = [[0.0]*3 for _ in range(3)]
        elif len(args) == 1:
            src = args[0]
            if hasattr(src, "_rows"):
                self._rows = [list(r) for r in src._rows]
            else:
                # Accept 9-flat or 3×3 nested list.
                if len(src) == 9:
                    flat = [float(v) for v in src]
                    self._rows = [flat[0:3], flat[3:6], flat[6:9]]
                else:
                    self._rows = [list(map(float, r)) for r in src]
        elif len(args) == 9:
            flat = [float(v) for v in args]
            self._rows = [flat[0:3], flat[3:6], flat[6:9]]
        else:
            raise ValueError(
                f"mat33(): expected 0 / 1 (matrix-like) / 9 (flat) args; got {len(args)}"
            )

    def __getitem__(self, key: Any) -> Union[float, List[float]]:
        if isinstance(key, tuple):
            r, c = key
            return self._rows[r][c]
        return self._rows[key]

    def __setitem__(self, key: Any, v: Any) -> None:
        if isinstance(key, tuple):
            r, c = key
            self._rows[r][c] = float(v)
        else:
            self._rows[key] = list(map(float, v))

    def __repr__(self) -> str:
        return f"mat33({self._rows})"


@dataclass
class transform:
    """SE(3) rigid transform — translation (vec3) + rotation (quat).

    Matches Isaac Lab convention: stored as 7-tuple (px, py, pz, qx, qy, qz, qw)
    when serialised; this class exposes them as separate components.
    """

    translation: vec3
    rotation: quat

    def __init__(self, translation: Any = None, rotation: Any = None):
        if translation is None:
            self.translation = vec3(0.0, 0.0, 0.0)
        elif isinstance(translation, vec3):
            self.translation = translation
        else:
            self.translation = vec3(*_coerce_vec(translation, 3))
        if rotation is None:
            self.rotation = quat(0.0, 0.0, 0.0, 1.0)
        elif isinstance(rotation, quat):
            self.rotation = rotation
        else:
            self.rotation = quat(*_coerce_vec(rotation, 4))


# ── array container ────────────────────────────────────────────────────────


class array:
    """Warp array — wraps a flat Python list[float | int].

    Constructor patterns:
        wp.array(dtype=wp.float32)           — empty type-annotation sentinel
        wp.array(data=[1.0, 2.0, 3.0])       — actual data
        wp.array(shape=N, dtype=wp.float32)  — zero-init length N
        wp.array([1, 2, 3])                  — positional data list

    Indexing returns / sets individual elements. `.shape` returns
    `(len,)` for 1-D arrays.
    """

    __slots__ = ("_data", "_dtype", "_shape", "device")

    def __init__(
        self,
        data: Any = None,
        dtype: Any = None,
        shape: Any = None,
        device: str = "cpu",
    ):
        self._dtype = dtype if dtype is not None else float32
        self.device = device
        if data is not None and not isinstance(data, (int, float)):
            # data is a sequence
            if hasattr(data, "__iter__"):
                self._data = list(data)
            else:
                self._data = [data]
            self._shape = (len(self._data),)
        elif shape is not None:
            n = shape if isinstance(shape, int) else int(shape[0])
            self._data = [0.0] * n
            self._shape = (n,)
        else:
            self._data = []
            self._shape = (0,)

    def __getitem__(self, i: int) -> Any:
        return self._data[i]

    def __setitem__(self, i: int, v: Any) -> None:
        self._data[i] = v

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    @property
    def shape(self) -> Tuple[int, ...]:
        return self._shape

    @property
    def dtype(self) -> Any:
        return self._dtype

    def fill_(self, value: Any) -> "array":
        """In-place fill (Warp's `array.fill_` alias)."""
        for i in range(len(self._data)):
            self._data[i] = value
        return self

    def numpy(self) -> List[Any]:
        """Return underlying data as a flat Python list (closest stdlib
        analog to `array.numpy()` — real Warp returns a numpy array)."""
        return list(self._data)

    def assign(self, src: Any) -> "array":
        """In-place assignment from an iterable of matching length."""
        new = list(src)
        if len(new) != len(self._data):
            raise ValueError(
                f"array.assign: length mismatch (have {len(self._data)}, got {len(new)})"
            )
        self._data = new
        return self


def zeros(shape: Any, dtype: Any = float32, device: str = "cpu") -> array:
    """Allocate a zero-initialised array of `shape`."""
    return array(shape=shape, dtype=dtype, device=device)


def empty(shape: Any, dtype: Any = float32, device: str = "cpu") -> array:
    """Allocate an uninitialised array (same as zeros under the stub)."""
    return array(shape=shape, dtype=dtype, device=device)


def from_numpy(data: Iterable[Any], dtype: Any = None, device: str = "cpu") -> array:
    """`wp.from_numpy(...)` — accept any sequence under the stub."""
    return array(data=list(data), dtype=dtype, device=device)


def index(arr: array, i: int) -> Any:
    """Alternative array read (matches `wp.index(arr, i)` real-API form)."""
    return arr[i]


# ── kernel + launch ────────────────────────────────────────────────────────


class kernel:
    """`@wp.kernel` decorator. In real Warp this triggers JIT compilation
    of the decorated function to GPU bytecode. Under the stub it stores
    the raw Python function and makes the kernel object callable directly
    via `wp.launch`.
    """

    def __init__(self, fn: Callable[..., None]):
        self._fn = fn
        self.__name__ = getattr(fn, "__name__", "kernel")
        self.__qualname__ = getattr(fn, "__qualname__", self.__name__)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Direct call — useful for unit tests that don't want to go through
        launch. Note that wp.tid() will raise unless invoked under launch."""
        return self._fn(*args, **kwargs)


def func(fn: Callable[..., Any]) -> Callable[..., Any]:
    """`@wp.func` decorator — annotates a helper function callable from
    inside a kernel. No-op under the stub."""
    return fn


def launch(
    kernel: Any,
    dim: Union[int, Tuple[int, ...]],
    inputs: Optional[List[Any]] = None,
    outputs: Optional[List[Any]] = None,
    device: str = "cpu",
    stream: Any = None,
) -> None:
    """Execute `kernel` sequentially across the launch grid.

    Args:
        kernel:   `@wp.kernel`-decorated function
        dim:      grid shape — int (1-D) or tuple (N-D, flattened)
        inputs:   positional kernel arguments
        outputs:  positional kernel arguments (after inputs)
        device:   device hint — ignored under the stub
        stream:   stream hint — ignored under the stub

    Semantics match real Warp: the kernel runs `prod(dim)` times with
    `wp.tid()` returning the linearised thread index 0..N-1. Real Warp
    runs these in parallel; this stub runs them sequentially in pure
    Python.
    """
    if isinstance(dim, int):
        total = dim
    else:
        total = 1
        for d in dim:
            total *= int(d)
    if total < 0:
        raise ValueError(f"wp.launch: dim must be ≥ 0; got {dim}")
    args: List[Any] = []
    if inputs:
        args.extend(inputs)
    if outputs:
        args.extend(outputs)
    prev_tid = getattr(_local, "tid", None)
    try:
        for i in range(total):
            _local.tid = i
            kernel(*args)
    finally:
        _local.tid = prev_tid


# ── scalar math (parity with `math.*` so kernels can use wp.* uniformly) ──

sin = _math.sin
cos = _math.cos
tan = _math.tan
atan2 = _math.atan2
sqrt = _math.sqrt
exp = _math.exp
log = _math.log
floor = _math.floor
ceil = _math.ceil


def abs(x: float) -> float:
    """`wp.abs` — accept Python float / int."""
    return _py_abs(x)


def min(a: Any, b: Any) -> Any:
    """`wp.min(a, b)` — element-wise min on vec types, scalar otherwise."""
    if isinstance(a, vec3):
        b3 = _coerce_vec(b, 3)
        return vec3(_py_min(a.x, b3[0]), _py_min(a.y, b3[1]), _py_min(a.z, b3[2]))
    if isinstance(a, vec4):
        b4 = _coerce_vec(b, 4)
        return vec4(_py_min(a.x, b4[0]), _py_min(a.y, b4[1]),
                     _py_min(a.z, b4[2]), _py_min(a.w, b4[3]))
    return _py_min(a, b)


def max(a: Any, b: Any) -> Any:
    """`wp.max(a, b)` — element-wise max on vec types, scalar otherwise."""
    if isinstance(a, vec3):
        b3 = _coerce_vec(b, 3)
        return vec3(_py_max(a.x, b3[0]), _py_max(a.y, b3[1]), _py_max(a.z, b3[2]))
    if isinstance(a, vec4):
        b4 = _coerce_vec(b, 4)
        return vec4(_py_max(a.x, b4[0]), _py_max(a.y, b4[1]),
                     _py_max(a.z, b4[2]), _py_max(a.w, b4[3]))
    return _py_max(a, b)


def clamp(x: float, low: float, high: float) -> float:
    """`wp.clamp(x, lo, hi)` — saturate scalar into [lo, hi]."""
    if x < low:
        return low
    if x > high:
        return high
    return x


# ── vector math ────────────────────────────────────────────────────────────


def length(v: Any) -> float:
    """`wp.length(v)` — Euclidean magnitude of a vec3/vec4."""
    c = _coerce_vec(v, len(v) if hasattr(v, "__len__") else 3)
    return _math.sqrt(sum(x * x for x in c))


def length_sq(v: Any) -> float:
    """`wp.length_sq(v)` — squared magnitude (no sqrt; cheaper)."""
    c = _coerce_vec(v, len(v) if hasattr(v, "__len__") else 3)
    return sum(x * x for x in c)


def normalize(v: Any) -> Any:
    """`wp.normalize(v)` — unit-length copy of vec3/vec4/quat. Returns
    a zero-vector when input has zero magnitude (matches real Warp)."""
    n = length(v)
    if n < 1e-12:
        if isinstance(v, vec3): return vec3(0, 0, 0)
        if isinstance(v, vec4): return vec4(0, 0, 0, 0)
        if isinstance(v, quat): return quat(0, 0, 0, 1)
        return v
    if isinstance(v, vec3):
        return vec3(v.x / n, v.y / n, v.z / n)
    if isinstance(v, vec4):
        return vec4(v.x / n, v.y / n, v.z / n, v.w / n)
    if isinstance(v, quat):
        return quat(v.x / n, v.y / n, v.z / n, v.w / n)
    c = _coerce_vec(v, len(v))
    return [x / n for x in c]


def dot(a: Any, b: Any) -> float:
    """`wp.dot(a, b)` — dot product. Length inferred from `a`."""
    n = len(a) if hasattr(a, "__len__") else 3
    a_c = _coerce_vec(a, n)
    b_c = _coerce_vec(b, n)
    return sum(a_c[i] * b_c[i] for i in range(n))


def cross(a: Any, b: Any) -> vec3:
    """`wp.cross(a, b)` — 3-vec cross product."""
    a_c = _coerce_vec(a, 3)
    b_c = _coerce_vec(b, 3)
    return vec3(
        a_c[1] * b_c[2] - a_c[2] * b_c[1],
        a_c[2] * b_c[0] - a_c[0] * b_c[2],
        a_c[0] * b_c[1] - a_c[1] * b_c[0],
    )


# ── quaternion math ────────────────────────────────────────────────────────


def quat_identity() -> quat:
    """`wp.quat_identity()` — (0, 0, 0, 1)."""
    return quat(0.0, 0.0, 0.0, 1.0)


def quat_from_axis_angle(axis: Any, angle: float) -> quat:
    """`wp.quat_from_axis_angle(axis, angle_rad)` — Hamilton convention.

    `axis` MAY be non-unit; it's normalised internally.
    """
    ax = _coerce_vec(axis, 3)
    n = _math.sqrt(ax[0] * ax[0] + ax[1] * ax[1] + ax[2] * ax[2])
    if n < 1e-12:
        return quat(0.0, 0.0, 0.0, 1.0)
    ax = [ax[0] / n, ax[1] / n, ax[2] / n]
    h = angle * 0.5
    s = _math.sin(h)
    return quat(ax[0] * s, ax[1] * s, ax[2] * s, _math.cos(h))


def quat_inverse(q: Any) -> quat:
    """`wp.quat_inverse(q)` — conjugate of a UNIT quat (xyz negated)."""
    qc = _coerce_vec(q, 4)
    return quat(-qc[0], -qc[1], -qc[2], qc[3])


def quat_mul(a: Any, b: Any) -> quat:
    """`wp.quat_mul(a, b)` — Hamilton quaternion product `a ⊗ b`."""
    ac = _coerce_vec(a, 4)
    bc = _coerce_vec(b, 4)
    ax, ay, az, aw = ac
    bx, by, bz, bw = bc
    return quat(
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def quat_rotate(q: Any, v: Any) -> vec3:
    """`wp.quat_rotate(q, v)` — rotate v by q (returns body-frame v_body)."""
    qc = _coerce_vec(q, 4)
    vc = _coerce_vec(v, 3)
    qx, qy, qz, qw = qc
    vx, vy, vz = vc
    # v' = v + 2 * q.xyz × (q.xyz × v + q.w * v)
    tx = qy * vz - qz * vy + qw * vx
    ty = qz * vx - qx * vz + qw * vy
    tz = qx * vy - qy * vx + qw * vz
    return vec3(
        vx + 2.0 * (qy * tz - qz * ty),
        vy + 2.0 * (qz * tx - qx * tz),
        vz + 2.0 * (qx * ty - qy * tx),
    )


def quat_rotate_inv(q: Any, v: Any) -> vec3:
    """`wp.quat_rotate_inv(q, v)` — rotate v by q⁻¹ (world→body when q is the
    body's world rotation)."""
    return quat_rotate(quat_inverse(q), v)


# ── transform math ─────────────────────────────────────────────────────────


def transform_identity() -> transform:
    """`wp.transform_identity()`."""
    return transform(vec3(0, 0, 0), quat(0, 0, 0, 1))


def transform_point(t: transform, p: Any) -> vec3:
    """`wp.transform_point(t, p)` — point under SE(3): rotate then translate."""
    rotated = quat_rotate(t.rotation, p)
    return rotated + t.translation


def transform_vector(t: transform, v: Any) -> vec3:
    """`wp.transform_vector(t, v)` — vector under SE(3): rotate only."""
    return quat_rotate(t.rotation, v)


def transform_get_translation(t: transform) -> vec3:
    """`wp.transform_get_translation(t)` — accessor parity."""
    return t.translation


def transform_get_rotation(t: transform) -> quat:
    """`wp.transform_get_rotation(t)` — accessor parity."""
    return t.rotation


def transform_multiply(a: transform, b: transform) -> transform:
    """`wp.transform_multiply(a, b)` — composes two SE(3) transforms
    a∘b such that `transform_point(a∘b, p) == transform_point(a, transform_point(b, p))`.

    Translation: a.t + a.q ⊗ b.t
    Rotation:    a.q ⊗ b.q
    """
    rot = quat_mul(a.rotation, b.rotation)
    trans = quat_rotate(a.rotation, b.translation) + a.translation
    return transform(trans, rot)


# ── atomic ops (single-threaded so just sequential read-modify-write) ────


def atomic_add(arr: array, i: int, v: Any) -> Any:
    """`wp.atomic_add(arr, i, v)` — returns the OLD value (matches real
    Warp's atomic_add return semantics)."""
    old = arr[i]
    arr[i] = old + v
    return old


def atomic_sub(arr: array, i: int, v: Any) -> Any:
    """`wp.atomic_sub(arr, i, v)` — returns the OLD value."""
    old = arr[i]
    arr[i] = old - v
    return old


def atomic_max(arr: array, i: int, v: Any) -> Any:
    """`wp.atomic_max(arr, i, v)` — returns the OLD value."""
    old = arr[i]
    arr[i] = old if old >= v else v
    return old


def atomic_min(arr: array, i: int, v: Any) -> Any:
    """`wp.atomic_min(arr, i, v)` — returns the OLD value."""
    old = arr[i]
    arr[i] = old if old <= v else v
    return old


__all__ = [
    # decorators / launch / kernel-body
    "kernel", "func", "launch", "tid", "init", "config",
    # dtypes
    "float32", "float64", "int32", "int64", "uint32", "uint8", "bool",
    # array container
    "array", "zeros", "empty", "from_numpy", "index",
    # linear-algebra value types
    "vec3", "vec4", "quat", "mat33", "transform",
    # scalar math
    "sin", "cos", "tan", "atan2", "sqrt", "exp", "log",
    "abs", "min", "max", "clamp", "floor", "ceil", "pi",
    # vec / quat / transform math
    "length", "length_sq", "normalize", "dot", "cross",
    "quat_identity", "quat_from_axis_angle", "quat_inverse",
    "quat_mul", "quat_rotate", "quat_rotate_inv",
    "transform_identity", "transform_point", "transform_vector",
    "transform_get_translation", "transform_get_rotation",
    "transform_multiply",
    # atomic ops
    "atomic_add", "atomic_sub", "atomic_max", "atomic_min",
]

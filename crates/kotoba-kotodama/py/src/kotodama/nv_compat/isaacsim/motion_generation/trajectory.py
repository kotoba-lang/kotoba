"""Joint-space trajectory generators — cubic / quintic polynomial mirror.

Tracks 40-engine/kami-engine/kami-genesis/src/trajectory.rs formula-for-formula.
Pair with isaacsim.core.api.controllers.ArticulationController to drive an
articulation through a smooth joint-space motion.
stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class JointTrajectory:
    """Base class. Subclasses implement duration() / sample(t) / dof()."""

    def duration(self) -> float:
        raise NotImplementedError

    def dof(self) -> int:
        raise NotImplementedError

    def sample(self, t: float) -> tuple:
        """Returns (q, qdot, qddot) as 3 lists at time t."""
        raise NotImplementedError


@dataclass
class CubicPolynomialTrajectory(JointTrajectory):
    q0: list
    qf: list
    qd0: list
    qdf: list
    duration_s: float

    def __post_init__(self):
        n = len(self.q0)
        assert len(self.qf) == n and len(self.qd0) == n and len(self.qdf) == n
        assert self.duration_s > 0
        t, t2, t3 = self.duration_s, self.duration_s ** 2, self.duration_s ** 3
        self._coeffs = []
        for i in range(n):
            a0 = self.q0[i]
            a1 = self.qd0[i]
            a2 = (3 * (self.qf[i] - self.q0[i]) - (2 * self.qd0[i] + self.qdf[i]) * t) / t2
            a3 = (2 * (self.q0[i] - self.qf[i]) + (self.qd0[i] + self.qdf[i]) * t) / t3
            self._coeffs.append((a0, a1, a2, a3))

    @staticmethod
    def stop_to_stop(q0: list, qf: list, duration: float) -> "CubicPolynomialTrajectory":
        z = [0.0] * len(q0)
        return CubicPolynomialTrajectory(q0=list(q0), qf=list(qf),
                                         qd0=z, qdf=list(z), duration_s=duration)

    def duration(self) -> float:
        return self.duration_s

    def dof(self) -> int:
        return len(self.q0)

    def sample(self, t: float) -> tuple:
        t = max(0.0, min(self.duration_s, t))
        n = len(self.q0)
        q = [0.0] * n
        qd = [0.0] * n
        qdd = [0.0] * n
        for i in range(n):
            a0, a1, a2, a3 = self._coeffs[i]
            q[i] = a0 + a1 * t + a2 * t * t + a3 * t * t * t
            qd[i] = a1 + 2 * a2 * t + 3 * a3 * t * t
            qdd[i] = 2 * a2 + 6 * a3 * t
        return (q, qd, qdd)


@dataclass
class QuinticPolynomialTrajectory(JointTrajectory):
    q0: list
    qf: list
    qd0: list
    qdf: list
    qdd0: list
    qddf: list
    duration_s: float

    def __post_init__(self):
        n = len(self.q0)
        for vec in (self.qf, self.qd0, self.qdf, self.qdd0, self.qddf):
            assert len(vec) == n
        assert self.duration_s > 0
        t = self.duration_s
        t2, t3, t4, t5 = t * t, t ** 3, t ** 4, t ** 5
        self._coeffs = []
        for i in range(n):
            a0 = self.q0[i]
            a1 = self.qd0[i]
            a2 = self.qdd0[i] / 2.0
            a3 = (20 * (self.qf[i] - self.q0[i])
                  - (8 * self.qdf[i] + 12 * self.qd0[i]) * t
                  - (3 * self.qdd0[i] - self.qddf[i]) * t2) / (2 * t3)
            a4 = (30 * (self.q0[i] - self.qf[i])
                  + (14 * self.qdf[i] + 16 * self.qd0[i]) * t
                  + (3 * self.qdd0[i] - 2 * self.qddf[i]) * t2) / (2 * t4)
            a5 = (12 * (self.qf[i] - self.q0[i])
                  - 6 * (self.qdf[i] + self.qd0[i]) * t
                  - (self.qdd0[i] - self.qddf[i]) * t2) / (2 * t5)
            self._coeffs.append((a0, a1, a2, a3, a4, a5))

    @staticmethod
    def min_jerk(q0: list, qf: list, duration: float) -> "QuinticPolynomialTrajectory":
        z = [0.0] * len(q0)
        return QuinticPolynomialTrajectory(
            q0=list(q0), qf=list(qf),
            qd0=list(z), qdf=list(z),
            qdd0=list(z), qddf=list(z),
            duration_s=duration,
        )

    def duration(self) -> float:
        return self.duration_s

    def dof(self) -> int:
        return len(self.q0)

    def sample(self, t: float) -> tuple:
        t = max(0.0, min(self.duration_s, t))
        t2, t3, t4, t5 = t * t, t ** 3, t ** 4, t ** 5
        n = len(self.q0)
        q = [0.0] * n
        qd = [0.0] * n
        qdd = [0.0] * n
        for i in range(n):
            a0, a1, a2, a3, a4, a5 = self._coeffs[i]
            q[i] = a0 + a1 * t + a2 * t2 + a3 * t3 + a4 * t4 + a5 * t5
            qd[i] = a1 + 2 * a2 * t + 3 * a3 * t2 + 4 * a4 * t3 + 5 * a5 * t4
            qdd[i] = 2 * a2 + 6 * a3 * t + 12 * a4 * t2 + 20 * a5 * t3
        return (q, qd, qdd)


class WaypointTrajectory(JointTrajectory):
    """Sequence of cubic segments through waypoints with centred-difference
    intermediate velocities and zero endpoint velocities."""

    def __init__(self, waypoints: list, segment_durations: list):
        assert len(waypoints) >= 2
        assert len(segment_durations) == len(waypoints) - 1
        dof = len(waypoints[0])
        n = len(waypoints)
        vels = [[0.0] * dof for _ in range(n)]
        for k in range(1, n - 1):
            dt_l = segment_durations[k - 1]
            dt_r = segment_durations[k]
            for j in range(dof):
                vels[k][j] = (waypoints[k + 1][j] - waypoints[k - 1][j]) / (dt_l + dt_r)
        self._segments = [
            CubicPolynomialTrajectory(
                q0=list(waypoints[k]), qf=list(waypoints[k + 1]),
                qd0=list(vels[k]), qdf=list(vels[k + 1]),
                duration_s=segment_durations[k],
            )
            for k in range(n - 1)
        ]
        self._cum_t = [0.0]
        acc = 0.0
        for dt in segment_durations:
            acc += dt
            self._cum_t.append(acc)
        self._dof = dof

    def duration(self) -> float:
        return self._cum_t[-1]

    def dof(self) -> int:
        return self._dof

    def sample(self, t: float) -> tuple:
        t = max(0.0, min(self.duration(), t))
        seg_idx = len(self._segments) - 1
        for k in range(len(self._segments)):
            if t <= self._cum_t[k + 1]:
                seg_idx = k
                break
        return self._segments[seg_idx].sample(t - self._cum_t[seg_idx])

"""Minimal Matrix Product State (MPS) engine for circuit simulation.

A qubit MPS is a list of rank-3 tensors ``A[i]`` of shape ``(Dl, 2, Dr)``:

    site 0      site 1            site n-1
    (1,2,D0) -- (D0,2,D1) -- ... -- (D_{n-2},2,1)

``Dl``/``Dr`` are the left/right *bond* dimensions and the middle index is the
physical (qubit) index of dimension 2.  Bond dimension is the resource that
controls how much entanglement the state can hold:  the Schmidt rank across the
cut between site ``i`` and ``i+1`` is exactly the bond dimension ``D_i``.

This module deliberately stays small and dependency-light (numpy only) so the
Shor experiments can read end-to-end.  It implements:

* exact construction from a state vector (sequential SVD),
* per-bond Schmidt spectra -> bond dimensions + entanglement entropy,
* 1- and 2-qubit gate application with SVD truncation (``chi_max`` / ``eps``),
* long-range 2-qubit gates via an adjacent-swap network,
* exact perfect sampling (Ferris-Vidal) from the represented distribution.
"""

from __future__ import annotations

import numpy as np


def _svd_truncate(theta, chi_max=None, eps=0.0):
    """SVD of a matrix with optional truncation.

    Returns ``U, S, Vh, discarded_weight`` where ``S`` is already truncated.
    """
    U, S, Vh = np.linalg.svd(theta, full_matrices=False)
    # Always drop numerically-zero singular values so the bond dimension reports
    # the *true* Schmidt rank (otherwise SVD returns min(rows,cols) values, many
    # of which are ~1e-16 and would inflate the bond dimension).
    if len(S) and S[0] > 0:
        nz = int(np.sum(S > 1e-12 * S[0]))
        S, U, Vh = S[:nz], U[:, :nz], Vh[:nz, :]
    total = float(np.sum(S ** 2))
    keep = len(S)
    if eps > 0.0 and total > 0.0:
        # keep the smallest prefix whose discarded weight <= eps
        tail = np.cumsum((S ** 2)[::-1])[::-1]  # tail[k] = sum_{j>=k} S_j^2
        # number to keep = first k where discarded weight (tail[k]) <= eps*total
        below = np.where(tail <= eps * total)[0]
        if len(below) > 0:
            keep = int(below[0])
    keep = max(1, keep)
    if chi_max is not None:
        keep = min(keep, chi_max)
    discarded = float(np.sum((S[keep:]) ** 2))
    return U[:, :keep], S[:keep], Vh[:keep, :], discarded


class MPS:
    def __init__(self, tensors, schmidt=None):
        self.A = [np.asarray(t, dtype=complex) for t in tensors]
        # Schmidt spectra captured at construction time (exact cuts).  Optional.
        self.schmidt = schmidt
        self.truncation_error = 0.0  # accumulated discarded weight from gates

    # ----------------------------------------------------------------- build
    @classmethod
    def from_statevector(cls, psi, n, chi_max=None, eps=0.0):
        """Exact (or truncated) MPS of an ``n``-qubit state vector.

        Site 0 is the most-significant qubit:  index = q0*2^(n-1) + ... + q_{n-1}.
        """
        psi = np.asarray(psi, dtype=complex).reshape(-1)
        assert psi.size == 2 ** n, (psi.size, n)
        tensors = []
        schmidt = []
        M = psi.reshape(1, 2 ** n)
        for _ in range(n - 1):
            Dl = M.shape[0]
            M = M.reshape(Dl * 2, -1)
            U, S, Vh, disc = _svd_truncate(M, chi_max=chi_max, eps=eps)
            keep = len(S)
            tensors.append(U.reshape(Dl, 2, keep))
            schmidt.append(S.copy())
            M = (S[:, None] * Vh)  # fold S into the remainder
        tensors.append(M.reshape(M.shape[0], 2, 1))
        return cls(tensors, schmidt=schmidt)

    def to_statevector(self):
        out = self.A[0]
        for t in self.A[1:]:
            out = np.tensordot(out, t, axes=([out.ndim - 1], [0]))
        return out.reshape(-1)

    @property
    def n(self):
        return len(self.A)

    # ------------------------------------------------------------ diagnostics
    def bond_dimensions(self):
        """Bond dimension to the right of each site (last bond is trivial)."""
        return [t.shape[2] for t in self.A[:-1]]

    def max_bond(self):
        bd = self.bond_dimensions()
        return max(bd) if bd else 1

    def schmidt_at(self, bond):
        """Normalised Schmidt spectrum across the cut after site ``bond``.

        Recomputed from the current tensors (works after gates), not the cached
        construction-time spectra.
        """
        # Left-canonical sweep up to `bond`, then SVD the boundary matrix.
        A = [t.copy() for t in self.A]
        M = A[0]
        for i in range(bond):
            Dl, d, Dr = M.shape
            M = M.reshape(Dl * d, Dr)
            U, S, Vh = np.linalg.svd(M, full_matrices=False)
            k = len(S)
            A[i] = U.reshape(Dl, d, k)
            M = (S[:, None] * Vh)
            M = np.tensordot(M, A[i + 1], axes=([1], [0]))
        # M now: (k, d, Dr_next...) collapse the cut
        Dl = M.shape[0]
        M2 = M.reshape(Dl * M.shape[1], -1) if M.ndim == 3 else M.reshape(Dl, -1)
        # Cut is between site `bond` and `bond+1`: matricise (left bonds | right)
        # Simpler: rebuild the bipartition matrix directly.
        s = np.linalg.svd(self._bipartition_matrix(bond), compute_uv=False)
        s = s[s > 1e-14]
        s = s / np.linalg.norm(s)
        return s

    def _bipartition_matrix(self, bond):
        """Matrix ``psi[(q0..q_bond), (q_{bond+1}..)]`` for the cut after ``bond``."""
        left = self.A[0]
        for t in self.A[1:bond + 1]:
            left = np.tensordot(left, t, axes=([left.ndim - 1], [0]))
        # left shape: (1, 2,2,...,2 [bond+1 of them], Dmid)
        right = self.A[bond + 1]
        for t in self.A[bond + 2:]:
            right = np.tensordot(right, t, axes=([right.ndim - 1], [0]))
        # right shape: (Dmid, 2,...,2, 1)
        Dmid = left.shape[-1]
        L = left.reshape(-1, Dmid)
        R = right.reshape(Dmid, -1)
        return L @ R

    def entropy_profile(self):
        """von Neumann entanglement entropy (bits) at every bond."""
        ent = []
        for b in range(self.n - 1):
            s = self.schmidt_at(b)
            p = s ** 2
            p = p[p > 1e-15]
            ent.append(float(-np.sum(p * np.log2(p))))
        return ent

    def norm(self):
        return float(np.linalg.norm(self.to_statevector()))

    # ----------------------------------------------------------------- gates
    def apply_1q(self, i, U):
        U = np.asarray(U, dtype=complex)  # (out, in)
        self.A[i] = np.einsum('ba,lar->lbr', U, self.A[i])

    def apply_2q(self, i, U, chi_max=None, eps=0.0):
        """Apply a 2-qubit gate to *adjacent* sites ``i, i+1``.

        ``U`` has shape ``(2,2,2,2)`` indexed ``(out_i, out_{i+1}, in_i, in_{i+1})``.
        """
        A1, A2 = self.A[i], self.A[i + 1]
        Dl = A1.shape[0]
        Dr = A2.shape[2]
        theta = np.tensordot(A1, A2, axes=([2], [0]))      # (Dl,2,2,Dr)
        theta = np.einsum('xyab,labr->lxyr', U, theta)     # apply gate
        mat = theta.reshape(Dl * 2, 2 * Dr)
        Ut, S, Vh, disc = _svd_truncate(mat, chi_max=chi_max, eps=eps)
        self.truncation_error += disc
        k = len(S)
        self.A[i] = Ut.reshape(Dl, 2, k)
        self.A[i + 1] = (S[:, None] * Vh).reshape(k, 2, Dr)

    _SWAP = np.array([[1, 0, 0, 0],
                      [0, 0, 1, 0],
                      [0, 1, 0, 0],
                      [0, 0, 0, 1]], dtype=complex).reshape(2, 2, 2, 2)

    def swap(self, i, chi_max=None, eps=0.0):
        self.apply_2q(i, self._SWAP, chi_max=chi_max, eps=eps)

    def apply_2q_long(self, c, t, U, chi_max=None, eps=0.0):
        """Apply a 2-qubit gate between possibly non-adjacent sites ``c`` and ``t``.

        Brings the two qubits adjacent via a swap network, applies the gate, then
        swaps back so the global qubit order is preserved.  ``U`` is indexed in
        the original ``(c, t)`` order.
        """
        if c == t:
            raise ValueError("control and target must differ")
        if abs(c - t) == 1:
            lo = min(c, t)
            if c < t:
                self.apply_2q(lo, U, chi_max=chi_max, eps=eps)
            else:
                # reverse the gate's qubit order
                Ur = np.einsum('xyab->yxba', U)
                self.apply_2q(lo, Ur, chi_max=chi_max, eps=eps)
            return
        # Move t next to c by adjacent swaps, apply, then move back.
        if c < t:
            # bubble t down to c+1
            for j in range(t - 1, c, -1):
                self.swap(j, chi_max=chi_max, eps=eps)
            self.apply_2q(c, U, chi_max=chi_max, eps=eps)
            for j in range(c + 1, t):
                self.swap(j, chi_max=chi_max, eps=eps)
        else:
            for j in range(t, c - 1):
                self.swap(j, chi_max=chi_max, eps=eps)
            # now control at c, target at c-1
            Ur = np.einsum('xyab->yxba', U)
            self.apply_2q(c - 1, Ur, chi_max=chi_max, eps=eps)
            for j in range(c - 2, t - 1, -1):
                self.swap(j, chi_max=chi_max, eps=eps)

    # -------------------------------------------------------------- sampling
    def right_canonicalize(self):
        """Make every tensor a right-isometry; orthogonality center -> site 0."""
        A = [t.copy() for t in self.A]
        for i in range(self.n - 1, 0, -1):
            Dl, d, Dr = A[i].shape
            mat = A[i].reshape(Dl, d * Dr)
            U, S, Vh = np.linalg.svd(mat, full_matrices=False)
            k = len(S)
            A[i] = Vh.reshape(k, d, Dr)
            US = U * S[None, :]
            A[i - 1] = np.tensordot(A[i - 1], US, axes=([2], [0]))
        self.A = A
        return self

    def sample(self, rng, shots=1):
        """Exact perfect sampling.  Returns a list of integer measurement outcomes
        (qubit 0 = MSB), drawing from |amplitude|^2 of the represented state."""
        self.right_canonicalize()
        results = []
        for _ in range(shots):
            v = np.ones((1,), dtype=complex)  # left boundary
            bits = 0
            for i in range(self.n):
                B = self.A[i]                       # (Dl, 2, Dr)
                w0 = v @ B[:, 0, :]
                w1 = v @ B[:, 1, :]
                p0 = float(np.vdot(w0, w0).real)
                p1 = float(np.vdot(w1, w1).real)
                tot = p0 + p1
                if tot <= 0:
                    p0 = p1 = 0.5
                else:
                    p0, p1 = p0 / tot, p1 / tot
                a = 0 if rng.random() < p0 else 1
                v = (w0 if a == 0 else w1)
                nv = np.linalg.norm(v)
                if nv > 0:
                    v = v / nv
                bits = (bits << 1) | a
            results.append(bits)
        return results

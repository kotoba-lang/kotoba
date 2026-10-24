(ns kotoba.sm.gtg
  "Gauge Theory Gravity (Lasenby-Doran-Gull 1998, 'Gravity, gauge theories and
  geometric algebra') -- ROTATION-GAUGE SECTOR (Phase 0a), POSITION-GAUGE
  SECTOR (Phase 0b), A NARROWLY-SCOPED CURVATURE QUADRATIC INVARIANT
  (Phase 0c, h = position-gauge-identity ONLY -- NOT the LDG curvature
  scalar), A GENERAL-h RECIPROCAL FRAME (Phase 0d), A GA-NATIVE
  MINKOWSKI-PAIRED RECIPROCAL FRAME (Phase 0e), AND -- NEW IN THIS PHASE --
  THE VACUUM/SOURCE-FREE FIELD EQUATION Omega(h) (Phase 1) ONLY. See the
  'Scope' section of the repo README for the ADR reference.

  PHASE 1 (ADR-2607102300) is the first FIELD EQUATION implemented in this
  namespace -- everything before it (Phase 0a-0e) built the KINEMATIC
  machinery (gauge potentials, curvature-as-a-functional-of-a-connection,
  reciprocal frames) without ever deriving Omega_mu FROM h_mu; Phase 1 adds
  `omega-from-h` (LDG eq 4.53, the closed-form VACUUM/SPIN-FREE solution of
  the rotation-gauge field equation given a position-gauge field h), the
  covariant Riemann map `riemann-map`/`riemann-map-matrix` (eq 4.48), and
  (having independently verified the pipeline against LDG's own Schwarzschild
  solution, and (native regression test, not merely a docs-only sign-
  convention investigation) LDG's own pure-de-Sitter cosmological solution,
  both to finite-difference precision, see gtg_test.cljc) the true LDG
  Ricci SCALAR `curvature-scalar` that Phase 0c/0d/0e each investigated and
  each declined to implement. See this namespace's 'PHASE 1' section below
  for the full derivation and gtg_test.cljc for the Schwarzschild-solution
  and FRW-cosmology regression tests this phase is built and checked
  against. Phase 1 is DELIBERATELY SCOPED to the VACUUM, SPIN-FREE field
  equation ONLY -- see the PHASE 1 section's own scope note for exactly what
  remains out of scope (matter/source-coupled, i.e. T_ab != 0, cosmology --
  a T_ab=0-plus-cosmological-constant, i.e. pure de Sitter, solution IS now
  covered -- the full field equation with torsion, the Einstein tensor, and
  the action principle).

  GTG's central observation (well known in the literature, not a new result
  of this namespace) is that the restricted Lorentz group SO(1,3)+ can be
  gauged exactly like the internal Yang-Mills groups already implemented in
  `kotoba.sm.gauge`: the six bivector generators T^{ab} of so(1,3), built
  from `kotoba.sm.spinor`'s existing Dirac gamma matrices, plug directly into
  `kotoba.sm.gauge`'s *generic* (not hard-coded to U(1)/SU(2)/SU(3))
  structure-constant / covariant-derivative / field-strength functions and
  reproduce the rotation-gauge-field curvature R_mu-nu -- the GTG analogue of
  the Yang-Mills field strength -- as a direct instance of that same generic
  machinery.

  SCOPE -- this namespace implements ONLY:
    1. the six so(1,3) bivector generators T^{ab} = (i/4)[gamma^a,gamma^b],
       a<b, as 4x4 complex matrices (`generators`, `generator`).
    2. a numeric check (in gtg_test.cljc) that these six generators close the
       Lorentz Lie algebra: [T^{ab},T^{cd}] = i(eta^{bc}T^{ad} - eta^{ac}T^{bd}
       - eta^{bd}T^{ac} + eta^{ad}T^{bc}) (`lorentz-algebra-rhs`).
    3. an HONEST numeric check of whether `kotoba.sm.gauge`'s (as of Phase 0a)
       compact-group trace normalization Tr(T^aT^b) = 1/2 delta^ab carries
       over to this noncompact generator set. IT DID NOT -- see
       `generator-trace-gram`, `true-structure-constants`,
       `compact-group-trace-normalization-holds?` and gtg_test.cljc for the
       actual numbers and the failure mode this Phase 0a check exposed in
       `kotoba.sm.gauge/structure-constants`'s output (a factor of 2*K[C][C]
       off, wrong SIGN for boost-type indices). THIS HAS SINCE BEEN FIXED:
       `kotoba.sm.gauge/structure-constants` was generalized (post-Phase-0a)
       to compute its own generator set's trace-Gram matrix K[A][B]=Tr(T_AT_B)
       instead of assuming it is 1/2delta^AB, so it is no longer restricted to
       the compact-group normalization and its output for this so(1,3)
       generator set is now the GENUINE structure constants -- see
       `rotation-raw-structure-constants` and gtg_test.cljc's
       `structure-constants-now-match-genuine-values-after-gauge-fix` (the
       renamed/inverted former `raw-structure-constants-diverge-from-genuine-ones`).
       This section's functions (`generator-trace-gram`, `true-structure-constants`,
       `compact-group-trace-normalization-holds?`, `basis-projection`) are KEPT as
       an independent derivation of the genuine structure constants and a live,
       re-checkable record of WHY Tr(T^aT^b)=1/2delta^ab fails to hold for a
       noncompact generator set -- useful documentation and cross-check value
       even though `kotoba.sm.gauge/structure-constants` no longer needs the
       workaround.
       A related, independently-checked noncompactness symptom (gtg_test.cljc,
       'generators-are-4x4-complex-matrices'): the 3 boost-type generators
       T^{0i} are ANTI-Hermitian, not Hermitian, while the 3 rotation-type
       generators T^{ij} are Hermitian -- the textbook reason (Peskin &
       Schroeder section 3.2, whose S^{mu-nu}=(i/4)[gamma^mu,gamma^nu] is
       literally this namespace's T^{ab}) the Dirac spinor representation of
       the Lorentz group is not unitary.
    4. the rotation gauge field Omega_mu (a 6-component real bivector-valued
       gauge potential, same data shape `kotoba.sm.gauge` already uses for
       A_mu^a) and its field strength / curvature bivector R_mu-nu, obtained
       by handing this generator set to `kotoba.sm.gauge/field-strength`
       unmodified (`rotation-field-strength`). R_mu-nu^k = -R_nu-mu^k
       (the physically required antisymmetry) now holds for EVERY excited
       Omega component, including mixed boost/rotation self-interaction --
       `kotoba.sm.gauge/self-interaction-term` had an independent,
       since-fixed structure-constant slot-order bug (invisible for compact
       U(1)/SU(2)/SU(3) groups, but visible here because this generator
       set's trace-Gram matrix is diagonal yet non-uniform) that used to
       break this antisymmetry for mixed boost/rotation excitations; see
       `rotation-field-strength`'s docstring and gtg_test.cljc's
       `rotation-field-strength-self-interaction-now-antisymmetric-*` tests
       for the before/after record.
    5. the spin-connection covariant derivative on a Dirac spinor,
       D_mu psi = d_mu psi - i g Omega_mu^{ab} T_{ab} psi, obtained by
       handing this generator set to `kotoba.sm.gauge/covariant-derivative`
       unmodified (`spinor-covariant-derivative`).
    6. a flat-limit check (in gtg_test.cljc) that with Omega_mu = 0
       everywhere, the covariant Dirac residual built on top of (5) is
       EXACTLY (not just approximately) `kotoba.sm.spinor`'s existing free
       Dirac-equation residual (`dirac-residual-with-rotation-gauge`).

  PHASE 0b (position-gauge sector) adds:
    7. the position gauge field h_mu(x): at each spacetime point, an
       invertible linear map from gauge coordinates to physical spacetime,
       represented as a 4x4 real matrix `h[mu][nu]` = h_mu^nu (row `mu` IS
       the physical four-vector h_mu, in the same [t x y z] component
       convention `kotoba.sm.tensor`/`kotoba.sm.vector-field` use everywhere
       else). `position-gauge-identity` is the trivial choice h_mu^nu =
       delta_mu^nu ('gauge coordinates = physical coordinates'). AT PHASE 0b
       TIME this namespace did not implement a general matrix inverse to
       check h's invertibility numerically or to build a reciprocal frame for
       general h (the same deliberate omission `kotoba.sm.gauge` documents
       for its own structure-constant derivation) -- invertibility was a
       precondition on `h`, not something computed. PHASE 0d (item 11 below)
       adds a general NxN matrix inverse (`kotoba.sm.tensor/mat-inverse`) and
       uses it to build a reciprocal frame `reciprocal-frame` for ANY
       invertible h, not just `position-gauge-identity` -- invertibility is
       now CHECKED (throws `ex-info` on a ~0 determinant) rather than merely
       assumed.
    8. the derived metric g_mu-nu(x) = h_mu(x) . h_nu(x) = eta_ab h_mu^a(x)
       h_nu^b(x) (`derived-metric`, `derived-metric-field`), computed by
       treating each row of `h` as an upper-index four-vector and reusing
       `kotoba.sm.tensor/dot` (the existing Minkowski inner product) row by
       row -- no new inner-product machinery. A flat-limit check (in
       gtg_test.cljc) that at h = `position-gauge-identity` this is EXACTLY
       (bit-for-bit, integer arithmetic throughout, not merely close)
       `kotoba.sm.tensor/metric`.
    9. a consistency check that `kotoba.sm.vector-field`'s PRE-EXISTING
       global SO(3,1)+ representation (`boost`/`rotation-x`/`rotation-y`/
       `rotation-z`) is CONTAINED in this sector as the special case
       'h_mu = a constant Lorentz matrix, Omega_mu = 0' -- a constant h built
       from any Lorentz transformation reproduces the flat metric exactly
       (up to floating-point roundoff from sqrt/cos/sin), because
       Lambda^T eta Lambda = eta (`vector-field/lorentz?`'s defining
       property) algebraically implies Lambda eta Lambda^T = eta, which is
       exactly what `derived-metric` computes row-by-row for h = Lambda --
       see the section-7 header comment below for the derivation, and
       gtg_test.cljc's
       `global-lorentz-transformations-are-the-constant-flat-special-case`
       for the numeric check (several concrete boosts and rotations).
       `derived-metric-matches-flat?` packages this equality check (used for
       both (8)'s exact identity case and (9)'s Lorentz-matrix case).

  PHASE 0c (curvature quadratic invariant, DELIBERATELY NARROW SCOPE) adds:
    10. `curvature-quadratic-invariant`: a scalar built from the rotation-gauge
       curvature bivector R_mu-nu ALONE (`rotation-field-strength`'s output),
       by lowering both spacetime indices with `kotoba.sm.tensor/lower2` and
       fully contracting with `kotoba.sm.tensor/full-contract` (reusing
       `kotoba.sm.tensor`'s EXISTING rank-2 raise/lower/contract machinery,
       no new tensor primitives), per bivector-generator component k, then
       summing the 6 components weighted by this namespace's own diagonal
       Killing-form-like trace pairing `generator-trace-gram` (section 3
       above) -- i.e. I = sum_k K[k][k] (R_mu-nu^k R^{mu-nu}_k), the
       'eta^mu-rho eta^nu-sigma R_mu-nu . R_rho-sigma' quadratic contraction
       collapsed via the diagonal metric.
       THIS IS DELIBERATELY NOT the Lasenby-Doran-Gull curvature scalar
       R = h^mu ^ h^nu . R(h-bar_nu, h-bar_mu). That definition needs the
       position gauge field's RECIPROCAL FRAME h-bar, i.e. a general 4x4
       matrix inverse, which is not implemented ANYWHERE in this codebase
       (see item 7's note and `kotoba.sm.gauge`'s own analogous documented
       omission) -- computing R for a general h is explicitly OUT OF SCOPE
       and deferred (see below). The one case where h-bar IS trivial to get
       right is h = `position-gauge-identity` (h-bar = h = the identity), so
       `curvature-quadratic-invariant` is scoped to being INTERPRETABLE only
       in that special case; it does not take an `h` argument at all because
       R_mu-nu itself (Phase 0a) is computed independently of h (Phase 0b) --
       see the FULL COMBINED covariant derivative note below, still deferred.
       EVEN AT h = `position-gauge-identity`, `curvature-quadratic-invariant`
       is honestly NOT a port of the LDG R: working through the definition,
       R = h^mu ^ h^nu . R(h-bar_nu, h-bar_mu) is a single LINEAR contraction
       of R_mu-nu (dot the FIXED bivector h^mu^h^nu, which does not depend on
       R at all, against R -- bilinear in two DIFFERENT bivectors, one of
       which is a constant), the same relationship the ordinary linear Ricci
       scalar R has to the full Riemann tensor. `curvature-quadratic-invariant`
       is instead QUADRATIC in R_mu-nu (R contracted against itself) -- the
       same relationship the (quadratic) Kretschmann scalar R_abcd R^abcd has
       to the Riemann tensor in ordinary GR. Ricci scalar and Kretschmann
       scalar are DIFFERENT invariants of DIFFERENT degree in the curvature:
       related only in that both vanish exactly when the full curvature
       vanishes (gtg_test.cljc's flat-limit check for this one), not
       proportional to each other and not interchangeable in general. This
       namespace does not implement the true linear LDG contraction either --
       doing so correctly requires pinning down, from the LDG geometric-
       algebra convention (not guessed at here), exactly which of R_mu-nu's
       two spacetime indices pairs with which of the curvature bivector's own
       two indices, and there is no independent literature reference value in
       this codebase to test that pairing against -- so it is left as a
       named, explicit follow-up rather than risked as a plausible-looking
       but silently wrong implementation. `curvature-quadratic-invariant` is
       also NOT guaranteed non-negative: `generator-trace-gram`'s K is
       indefinite (+1 rotation-type, -1 boost-type), so a boost-dominated
       curvature can make it negative -- a further symptom, like
       `compact-group-trace-normalization-holds?`'s finding, of this
       generator set's noncompactness.

  PHASE 0d (general-position-gauge reciprocal frame, DELIBERATELY STAGED --
  see the README's Phase 0d section for the two-stage split) adds:
    11. a GENERAL NxN matrix inverse (`kotoba.sm.tensor/mat-det`,
       `mat-minor`, `mat-adjugate`, `mat-inverse` -- ordinary Laplace-
       expansion/adjugate linear algebra, no physics convention involved,
       throws `ex-info` on a ~0 determinant rather than dividing by it, same
       spirit as `kotoba.sm.gauge/diagonal-gram-real`'s guard) and
       `reciprocal-frame`: the GTG reciprocal (dual) frame h-bar^mu of a
       GENERAL invertible position-gauge-field VALUE h (not just
       `position-gauge-identity` or a constant Lorentz matrix, Phase 0b's
       scope), defined by the STANDARD linear-algebra dual-basis
       biorthogonality relation h-bar^mu . h_nu = delta^mu_nu, where '.' here
       is the PLAIN component (Kronecker) pairing sum_a h-bar^mu[a] h_nu[a]
       -- NOT `kotoba.sm.tensor/dot`'s Minkowski-metric pairing. Given this
       pairing, biorthogonality is a matrix equation Hbar . H^T = I, so
       Hbar = (H^-1)^T -- `reciprocal-frame` computes exactly this, via
       `mat-inverse` then `kotoba.sm.tensor/mat-transpose`; gtg_test.cljc
       checks the biorthogonality relation holds numerically for a concrete
       non-identity invertible h, that h*h^-1=I for that same h, that a
       singular (determinant-0) h throws `ex-info`, and that at
       h = `position-gauge-identity`, h-bar = h EXACTLY (the identity matrix
       is its own inverse and its own transpose).

       *** HONESTY NOTE ***: this is the ORDINARY linear-algebra dual basis
       of the ROWS of h, treating them as an abstract basis of R^4 under the
       PLAIN component pairing -- it is deliberately NOT asserted to be an
       ingredient of the Lasenby-Doran-Gull curvature scalar. A literature
       follow-up (stage 2 of this phase, see `reciprocal-frame`'s own
       docstring and the README's Phase 0d section for the full writeup and
       both source URLs) found TWO independent, mutually-corroborating
       primary sources (Lasenby/Doran/Gull 1998/2004, arXiv gr-qc/0405033;
       Lewis/Doran/Lasenby 1999, arXiv gr-qc/9910039) pinning down the
       ACTUAL Ricci-scalar formula's high-level structure -- and it turns
       out that formula's outer contraction uses the FIXED BACKGROUND
       frame's OWN reciprocal (trivial under the metric, no matrix inverse
       of h needed at all), NOT `reciprocal-frame` (a reciprocal frame OF h)
       as originally guessed. So `reciprocal-frame` is confirmed NOT to be
       what R needs, rather than left merely unconfirmed either way. R
       itself remains unimplemented because a DIFFERENT step -- translating
       the confirmed formula's 'vector . bivector' Clifford-algebra
       contraction into this codebase's six-generator-component array
       representation -- has its own unresolved index/sign risk that this
       pass could not independently verify (see `reciprocal-frame`'s
       docstring for the details). `reciprocal-frame` remains useful in its
       own right as h's standard dual basis (e.g. for a future combined
       covariant derivative, still out of scope), just not as a confirmed
       LDG-R ingredient.

  PHASE 0e (GA-native Minkowski-paired reciprocal frame, PLUS a bounded,
  DECLINED stage-2 curvature-scalar investigation) adds:
    13. `reciprocal-frame-minkowski`: the GA-NATIVE reciprocal (dual) frame
       h-bar^mu_eta of a GENERAL invertible position-gauge-field VALUE `h`,
       defined by the SAME biorthogonality relation `reciprocal-frame` (item
       11) uses, h-bar^mu . h_nu = delta^mu_nu, but THIS TIME with '.' =
       `kotoba.sm.tensor/dot`, the Minkowski invariant inner product -- the
       pairing Geometric Algebra / GTG actually use for a reciprocal frame,
       NOT `reciprocal-frame`'s plain component/Kronecker pairing. This is
       exactly the 'Hbar_eta' alternative `reciprocal-frame`'s own HONESTY
       NOTE (item 11) already worked out algebraically (Hbar_eta =
       (H^-1)^T . eta, re-derived and numerically checked independently here
       rather than taken on faith) but stopped short of implementing --
       `reciprocal-frame-minkowski` implements and verifies exactly that.
       VERIFIED (gtg_test.cljc): (a) the Minkowski-paired biorthogonality
       relation holds for a concrete non-identity invertible h, and the
       result is numerically DIFFERENT from `reciprocal-frame`'s
       plain-pairing output for the SAME h (they agree on the timelike
       column and differ in SIGN on every spatial column, exactly as the
       Hbar_eta = Hbar_flat . eta column-scaling derivation predicts). (b)
       at h = `position-gauge-identity`, h-bar_eta = eta EXACTLY
       (bit-for-bit): h-bar^0 = h_0 but h-bar^i = -h_i for the 3 spatial
       rows -- genuinely DIFFERENT from `reciprocal-frame`'s h-bar = h at
       the same point, confirming (not merely restating) the divergence
       `reciprocal-frame`'s HONESTY NOTE predicted without numerically
       checking it. (c) for a CONSTANT Lorentz transformation h = Lambda
       (`kotoba.sm.vector-field`'s existing boost/rotation matrices),
       h-bar_eta = eta . Lambda EXACTLY (up to floating-point roundoff) -- a
       closed form derived from `vf/lorentz?`'s defining property
       Lambda^T eta Lambda = eta (see `reciprocal-frame-minkowski`'s own
       docstring for the derivation), checked for several concrete
       boosts/rotations, not merely argued.
    14. A BOUNDED, DECLINED attempt at independently verifying (via linearized
       weak-field General Relativity, NOT a further literature read of the
       LDG papers, per this phase's task instructions) Phase 0d stage 2's
       still-open question -- the true LDG curvature scalar R. The plan: (i)
       pick a small metric perturbation h_mu-nu(x) with a KNOWN linearized-GR
       Ricci scalar R^(1) = d^mu d^nu h_mu-nu - Box h (a standard textbook
       result, independent of any GTG-paper convention); (ii) build a
       position-gauge field h_mu(x) = delta_mu^nu + (1/2) h_mu^nu(x)
       reproducing it via `derived-metric` to linear order (this step is
       genuinely easy and was worked out: `derived-metric` of that h equals
       eta_mu-nu + h_mu-nu(x) + O(h^2) exactly as expected, since
       `derived-metric`'s h_mu.h_nu bilinear form is already the correct one
       -- no new machinery needed for this step alone); (iii) obtain the
       CORRESPONDING rotation-gauge field Omega_mu(x) from h_mu(x)'s
       derivatives; (iv) run `rotation-field-strength`; (v) test a candidate
       R[mu][nu][k]->scalar formula against R^(1). THIS ATTEMPT STOPPED AT
       STEP (iii): this codebase has NO h_mu(x)->Omega_mu(x) correspondence
       ANYWHERE (grep-confirmed -- consistent with this docstring's own
       'ALSO OUT OF SCOPE' note below, which already says Phase 0a's
       covariant derivative and Phase 0b's derived metric 'are developed
       independently of each other... not yet combined'). Unlike the
       ORDINARY general-relativity vierbein-postulate torsion-free spin
       connection (which relates a curved-spacetime tetrad e^a_mu -- ONE flat
       index a, ONE curved-coordinate index mu -- to Christoffel symbols),
       GTG's h_mu^nu has BOTH indices as components of the SAME flat
       background vector space (h maps a flat gauge-coordinate direction to a
       flat physical-spacetime direction; there is no curved-coordinate side
       to import the ordinary tetrad-postulate formula onto verbatim). The
       genuine GTG-specific 'intrinsic' Omega-from-h relation (part of LDG's
       own gauge-invariance/field-equation construction) is exactly the kind
       of GTG-paper-specific, index/sign-convention-bearing formula this pass
       was told NOT to re-derive from the literature this round, and it
       cannot be safely reconstructed from generic (non-GTG) general-
       relativity textbook knowledge, because ordinary tetrad calculus does
       not carry over to GTG's flat, non-curved-coordinate formalism without
       exactly the kind of paper-specific translation step this codebase's
       own established practice (see `rotation-field-strength`'s and
       `curvature-quadratic-invariant`'s docstrings) already treats as too
       risky to guess at without an independent reference value. So this
       investigation stopped at the SAME CLASS of blocker Phase 0d stage 2
       hit (an unverifiable index/sign convention, no independent numeric
       reference value to test a candidate against), one step EARLIER in the
       pipeline (h->Omega, rather than R->scalar) -- per the task's own
       explicit instruction, this is reported honestly rather than guessed
       at, and `curvature-scalar` remains unimplemented (AS OF Phase 0e --
       Phase 1, item 15 below, resolves exactly this blocker).

  PHASE 1 (field equation Omega(h), the covariant Riemann map, and the true
  LDG Ricci scalar -- ADR-2607102300) adds:
    15. `omega-from-h`: the VACUUM, SPIN-FREE closed-form solution of the
       rotation-gauge field equation, LDG eq (4.53)
       omega(a) = -H(a) + (1/2) a.(d_b^H(b)), with
       H(a) = hbar(grad ^ hbar^-1(a))  (eq 4.49, `H-field`) and
       hbar = `frame-adjoint` of the position-gauge field h (eq 2.46,
       a.f(b)=fbar(a).b -- the SAME adjoint relation used throughout this
       namespace's Phase 0d/0e reciprocal-frame work, applied here to h
       itself rather than to a constant matrix VALUE). Takes an h-FIELD
       (x -> 4x4 matrix, SAME shape as `derived-metric-field`'s h-field
       argument) and a spacetime point x, returns Omega_mu(x) (a 4x6 array,
       the SAME shape `rotation-field-strength` already consumes) --
       THIS IS THE FIRST TIME IN THIS NAMESPACE Omega_mu IS DERIVED FROM h_mu
       RATHER THAN SUPPLIED INDEPENDENTLY. The closed form was derived from
       LDG eqs (4.42)/(4.46)/(4.48)/(4.49)/(4.53) and cross-derived via an
       independent, standalone Python/numpy+sympy verification script
       (checked into the task's scratchpad, not this repo) that reproduces
       LDG's own closed-form Schwarzschild solution (eq 6.73) to ~1e-13
       (machine/finite-difference-truncation precision) BEFORE any of this
       namespace's Clojure code was written -- see gtg_test.cljc's
       Schwarzschild-solution regression tests for the SAME check ported to
       this codebase's 4x4-matrix/6-component-bivector representation.
       `H-field`, `bivector-commutator`, `wedge-vectors`,
       `vector-dot-bivector`, `bivector->matrix`, `matrix->bivector` are the
       minimal new GA-flavored primitives this required (NOT a general
       from-scratch geometric-algebra engine -- see this function's own
       docstring and the PHASE 1 header comment below for exactly which
       identity each one implements and how each was independently
       numerically cross-checked before being trusted).
    16. `riemann-basis-pair`/`riemann-map-matrix`/`riemann-map`: the
       COVARIANT Riemann map R(a^b), LDG eq (4.48)
       R(a^b) = L_a omega(b) - L_b omega(a) + omega(a)xomega(b) - omega(c(a,b)),
       c(a,b) = a.omega(b) - b.omega(a) (eq 4.46, valid for POSITION-
       INDEPENDENT a,b), L_a = a.hbar(grad) = h(a).grad (eq 4.42, the
       identity a.hbar(grad)=h(a).grad -- L_a is the ordinary directional
       derivative of the omega FIELD along h(a)(x), NOT the flat d_mu of
       Phase 0a's `rotation-gauge-field-gradient`/`rotation-field-strength`
       -- see `riemann-basis-pair`'s own docstring for why these are
       genuinely DIFFERENT connections and reusing Phase 0a's machinery here
       would be WRONG, the exact silent failure mode (identically-zero,
       teleparallel curvature) an earlier investigation hit and diagnosed,
       see the standalone verification script's own header comment).
       `riemann-map`/`riemann-map-matrix` extend R to a genuine LINEAR map
       on the full 6-dimensional bivector space (R is defined on the basis
       bivectors e_mu^e_nu by eq 4.48, and a linear map is fully determined
       by its action on a basis), so `riemann-map` accepts ANY bivector
       argument, including one built from POSITION-DEPENDENT vectors (e.g.
       `wedge-vectors` of two position-gauge-field rows h_mu(x), needed by
       item 17 below) -- not just a fixed-frame basis pair.
    17. `curvature-scalar`: the TRUE Lasenby-Doran-Gull Ricci SCALAR
       R = sum_{a,b} gamma^a.(gamma^b.R(h_b^h_a)) -- the formula Phase 0d
       stage 2 (item 12 above) and Phase 0e (item 14 above) each
       independently confirmed the STRUCTURE of (two independent primary
       literature sources agreeing) but declined to implement, because
       translating 'gamma^b.R(h_b^h_a)' into this codebase's array
       representation needed a bilinear extension of R to GENERAL (not
       basis-pair) bivectors that did not exist yet. Item 16's `riemann-map`
       supplies exactly that missing piece, so this formula is now directly
       transcribable with no remaining index/sign ambiguity: gamma^a =
       `tensor/raise` of the FIXED background basis vector e_a (trivial
       under the metric, confirmed by BOTH literature sources to be the
       correct outer-contraction frame -- NOT `reciprocal-frame`/
       `reciprocal-frame-minkowski`, which are reciprocal frames OF h, a
       DIFFERENT and NOT-needed-here construction, per item 12's finding);
       h_b = h-field(x)[b] = h(e_b) (Phase 0b's existing `h`); R(h_b^h_a) is
       `riemann-map` applied to `wedge-vectors(h_b,h_a)`. VERIFIED
       (gtg_test.cljc): matches 0.0 (LDG's own vacuum Ricci-scalar
       expectation for the Schwarzschild solution -- a vacuum solution of
       Einstein's equation has R_ab=0, hence R=0 as a direct special case)
       to within finite-difference-truncation tolerance at the SAME
       Schwarzschild test points item 15/16 are checked against, and EXACTLY
       0.0 (not merely close) at the flat limit (h=`position-gauge-identity`,
       where every derivative involved vanishes identically, not just
       numerically). This is honestly the FIRST curvature-scalar result in
       this namespace's whole Phase 0a-1 history that Phase 0c, Phase 0d
       stage 2, and Phase 0e's stage-2 investigation each in turn declined
       to reach -- reached here only because item 16 removed the specific,
       previously-unverifiable index/sign step that blocked every prior
       attempt, not by relaxing this namespace's verification discipline.

    PHASE 1 SCOPE NOTE: `omega-from-h`/`curvature-scalar` implement ONLY the
    VACUUM (source-free, T_ab=0), SPIN-FREE (no intrinsic angular-momentum
    matter coupling) closed-form solution (eq 4.53) -- NOT the general GTG
    field equation with a matter/torsion source term, NOT the Einstein
    tensor/multivector G(a) (needed to couple to a general stress-energy
    tensor), NOT the GTG action principle (the Lagrangian this closed form
    is the EULER-LAGRANGE solution of is not derived or checked here), and
    verified against exactly TWO known exact solutions -- Schwarzschild
    (Painleve-Gullstrand/Newtonian gauge, R=0) and, as of gtg_test.cljc's
    `curvature-scalar-matches-minus-4-lambda-for-pure-de-sitter-cosmology`,
    LDG's pure-de-Sitter cosmological solution (section 6.6 'Cosmology',
    Table 6/eq 6.169 at rho=p=0, R=-4*Lambda -- still T_ab=0, so still
    squarely within this VACUUM scope, just with Lambda != 0) -- NOT a
    general proof that this namespace's pipeline reproduces GR for arbitrary
    h, and NOT (a nonzero-density, e.g. dust, extension was investigated and
    declined -- see that test file section's header comment) a confirmation
    that this closed form extends correctly to matter-sourced (T_ab != 0)
    cosmological solutions. See the EXPLICITLY OUT OF SCOPE paragraph below
    for the full list still deferred.

    *** CONFIRMED, UNRESOLVED BUG for GENUINELY TIME-DEPENDENT h (read before
    trusting a `curvature-scalar` result for any h-field where Hdot!=0,
    i.e. the Hubble-like rate itself changes with time -- NOT merely
    time-dependent components, since de Sitter's h IS time-dependent but has
    Hdot=0 identically): *** investigating a nonzero-density FRW cosmology
    extension (matter-dominated Einstein-de-Sitter dust, H(t)=2/(3t),
    Hdot(t)=-2/(3t^2)) found `curvature-scalar` returns EXACTLY 7x the
    correct value -- reproduced independently by two people, stable to
    ~7 significant figures across fd-h in [5e-5,1e-3] and t in [1.5,10] (a
    clean algebraic factor, not finite-difference truncation noise). An
    independent, GTG/geometric-algebra-free derivation (ordinary Christoffel
    symbols from the metric this h-field represents) confirms the CORRECT
    answer is R=-12*H^2-6*Hdot; this pipeline instead computes
    -12*H^2+6*Hdot -- the Hdot (time-derivative) contribution alone has the
    WRONG SIGN, while the H^2 (non-derivative) contribution is exactly
    correct. Root-caused as narrowly as two independent, multi-hour
    investigations could manage (both scratch-verified, not landed as repo
    code): `H-field`, `omega-from-h` (checked directly against LDG eq 4.49/
    4.50 using the code's OWN outputs, and cross-verified against an
    independent Python geometric-algebra reference engine), and
    `riemann-basis-pair`'s formula-level structure (checked term-by-term
    against a hand re-derivation of eqs 4.44/4.46/4.47/4.48) each
    individually reproduce their OWN defining equation correctly when tested
    in isolation with concrete numeric or symbolic inputs -- yet the
    end-to-end composition is measurably wrong specifically in the
    time-derivative channel. A candidate one-line patch (negating `L-a-omega`'s
    rho=0/time-direction contribution only) numerically fixes the dust
    reproduction case and provably does not change the Schwarzschild/de-Sitter
    regression results (both have zero rho=0 contribution structurally) --
    but was NOT applied, because it directly contradicts a separate, simpler
    numeric check of the identity `L-a-omega` is supposed to implement
    (a.hbar(grad)F = h(a).grad F, verified directly on a plain scalar test
    function F(x)=t, a=e_0) -- applying the patch would make THAT simpler
    identity check fail. This is flagged as symptom-suppression, not a
    verified fix, and deliberately left OUT of this codebase. DO NOT trust
    `curvature-scalar` (or `riemann-map`/`riemann-basis-pair`/`omega-from-h`
    composed end-to-end) for any h-field with Hdot!=0 until this is properly
    resolved -- Schwarzschild (static) and de Sitter (Hdot=0) remain
    verified and safe to rely on.

  EXPLICITLY OUT OF SCOPE, NOT IMPLEMENTED HERE (Phase 0a+0b+0c+0d+0e+1):
  the Einstein tensor/multivector G(a), the GTG action principle, the general
  (matter/torsion-sourced) field equation (only the vacuum/spin-free closed
  form (4.53) is implemented, item 15 above), any proof of equivalence to
  General Relativity for GENERAL h (item 17's `curvature-scalar` is verified
  against exactly two known exact solutions, not a general equivalence
  proof), and any dark-matter/dark-energy (nonzero-matter-density,
  T_ab != 0) cosmological extension -- a PURE vacuum-plus-cosmological-
  constant (T_ab=0, Lambda != 0, de Sitter) solution IS now covered (see the
  PHASE 1 SCOPE NOTE just above and gtg_test.cljc's FRW-cosmology section);
  a genuine matter-coupled (T_ab != 0) extension was investigated and
  declined, and remains out of scope. ALSO OUT OF SCOPE: a
  general (non-vacuum) combined h_mu+Omega_mu GTG covariant derivative with
  torsion -- Phase 0a's covariant derivative (5) still stands independently
  of the vacuum connection Phase 1 derives (5) was built for a SUPPLIED
  Omega_mu, not the field-equation solution; wiring Phase 1's `omega-from-h`
  into (5) to get a genuine matter-coupled covariant Dirac equation in curved
  spacetime is a legitimate, much larger follow-up, deliberately deferred to
  a later phase. This namespace is a limited, literature-faithful port of the
  rotation-gauge and position-gauge SECTORS, one narrowly-scoped curvature
  invariant, two dual-basis reciprocal-frame constructions (plain-pairing and
  Minkowski-pairing), and the VACUUM/SPIN-FREE field equation with its
  covariant Riemann map and Ricci scalar ONLY, and must not be read as 'GTG
  is fully implemented here' or as any kind of general-purpose gravity
  engine."
  (:require [kotoba.sm.complex :as c]
            [kotoba.sm.tensor :as tensor]
            [kotoba.sm.spinor :as spinor]
            [kotoba.sm.gauge :as gauge]
            [kotoba.sm.vector-field :as vf]))

(defn- abs-num [x] (if (neg? x) (- x) x))

;; ---------------------------------------------------------------------------
;; 1. so(1,3) bivector generators T^{ab} = (i/4)[gamma^a,gamma^b], a<b
;; ---------------------------------------------------------------------------

(def generator-index-pairs
  "The 6 independent (a,b), a<b index pairs, in the fixed enumeration order
  used throughout this namespace to index the 6-component rotation-gauge
  field / generator vector: 0=(0 1) 'boost-x', 1=(0 2) 'boost-y',
  2=(0 3) 'boost-z', 3=(1 2) 'rotation-z', 4=(1 3) 'rotation-y',
  5=(2 3) 'rotation-x' (the usual identification of the 3 boost + 3 rotation
  generators of the restricted Lorentz group)."
  [[0 1] [0 2] [0 3] [1 2] [1 3] [2 3]])

(defn bivector-generator
  "T^{ab} = (i/4)[gamma^a,gamma^b] for a<b, a 4x4 complex matrix. Built from
  `kotoba.sm.spinor`'s existing Dirac gamma matrices and
  `kotoba.sm.complex`'s matrix ops; equal to (1/2) `kotoba.sm.spinor/sigma-munu`
  (sigma^{ab} = (i/2)[gamma^a,gamma^b] is already defined there as 'the
  antisymmetric tensor bilinear generator' -- reused here rather than
  reimplementing the same commutator)."
  [a b]
  (c/m-rscale 0.5 (spinor/sigma-munu a b)))

(def generators
  "The 6 so(1,3) generators, in `generator-index-pairs` order. This is the
  generator SET this whole namespace hands to `kotoba.sm.gauge`'s generic
  functions in place of the SU(2)/SU(3) generator sets they were originally
  exercised against."
  (mapv (fn [[a b]] (bivector-generator a b)) generator-index-pairs))

(defn generator
  "T^{ab} for ANY a,b in 0..3 (not just a<b), via antisymmetry T^{ba}=-T^{ab}
  and T^{aa}=0 (the zero 4x4 matrix). Needed because the Lorentz-algebra
  commutation relation (`lorentz-algebra-rhs`) references T^{ad} etc. for
  index orderings outside the a<b enumeration of `generators`."
  [a b]
  (cond
    (= a b) (c/m-zero 4 4)
    (< a b) (bivector-generator a b)
    :else (c/m-rscale -1 (bivector-generator b a))))

;; ---------------------------------------------------------------------------
;; 2. Lorentz algebra closure: [T^{ab},T^{cd}] = i(eta^{bc}T^{ad} - eta^{ac}T^{bd}
;;    - eta^{bd}T^{ac} + eta^{ad}T^{bc})
;; ---------------------------------------------------------------------------

(defn- eta [i j] (get-in tensor/metric [i j]))

(defn lorentz-algebra-rhs
  "The right-hand side of the defining so(1,3) commutation relation
  [T^{ab},T^{cd}] = i(eta^{bc}T^{ad} - eta^{ac}T^{bd} - eta^{bd}T^{ac} +
  eta^{ad}T^{bc}), evaluated with this namespace's generators and
  `kotoba.sm.tensor`'s mostly-minus metric. gtg_test.cljc checks this against
  the actual commutator `kotoba.sm.complex/m-commutator` of the corresponding
  generators, for every a<b, c<d pair."
  [a b c d]
  (let [term1 (c/m-rscale (eta b c) (generator a d))
        term2 (c/m-rscale (- (eta a c)) (generator b d))
        term3 (c/m-rscale (- (eta b d)) (generator a c))
        term4 (c/m-rscale (eta a d) (generator b c))
        total (reduce c/m-add [term1 term2 term3 term4])]
    (c/m-scale c/i total)))

;; ---------------------------------------------------------------------------
;; 3. Trace-normalization honesty check -- Tr(T^aT^b)=1/2delta^ab (the
;;    compact-group normalization `kotoba.sm.gauge/structure-constants` used
;;    to hard-code) does NOT hold for these noncompact so(1,3) generators.
;;    Phase 0a recorded this as a live, re-checkable predicate/value (not
;;    just asserted in the test file), and it exposed a real bug in
;;    `kotoba.sm.gauge/structure-constants` (see `rotation-raw-structure-constants`).
;;    That bug has SINCE BEEN FIXED: `kotoba.sm.gauge/structure-constants` now
;;    computes its OWN generator set's trace-Gram matrix instead of assuming
;;    it is 1/2delta^AB, so it is correct for this so(1,3) generator set too.
;;    The functions below are KEPT (not deleted) as an independent derivation
;;    of the genuine structure constants and documentation of WHY the old
;;    compact-group assumption fails here -- useful on their own merits, and
;;    now doubling as the reference oracle that proves the gauge.cljc fix is
;;    correct (gtg_test.cljc's
;;    `structure-constants-now-match-genuine-values-after-gauge-fix`).
;; ---------------------------------------------------------------------------

(defn generator-trace-gram
  "K[A][B] = Tr(T_A T_B) for the 6 basis generators (`generator-index-pairs`
  order) -- the so(1,3) analogue of the compact-group normalization
  Tr(T^aT^b)=1/2delta^ab that `kotoba.sm.gauge/structure-constants` used to
  hard-code (it now computes this same kind of Gram matrix generically from
  whatever generator set it is given, `kotoba.sm.gauge/generator-gram`).
  Returned as a plain 6x6 real matrix; gtg_test.cljc additionally checks the
  imaginary part of every trace is ~0 before this real part is taken at face
  value."
  []
  (vec (for [A (range 6)]
         (vec (for [B (range 6)]
                (c/re (c/m-trace (c/m-mul (nth generators A) (nth generators B)))))))))

(defn compact-group-trace-normalization-holds?
  "Does Tr(T^A T^B) = 1/2 delta^AB hold for these so(1,3) generators?
  Numerically: NO. `generator-trace-gram` is diagonal (off-diagonal terms
  vanish, as for the compact groups) but the diagonal entries are +/-1, not a
  uniform +1/2: -1 for the 3 boost-type generators (index 0,1,2 = pairs
  containing the timelike index 0) and +1 for the 3 rotation-type generators
  (index 3,4,5 = purely spatial pairs) -- the indefinite Minkowski signature
  shows up directly in the generators' own Killing-form-like trace pairing.
  This predicate is exposed live (not just asserted once in the test file) as
  a permanent record of why this generator set needed
  `kotoba.sm.gauge/structure-constants`'s Gram-matrix generalization (it is
  diagonal, so that generalization applies -- see the `kotoba.sm.gauge`
  namespace docstring's SCOPE note on non-diagonal Gram matrices)."
  ([] (compact-group-trace-normalization-holds? 1e-9))
  ([eps]
   (let [K (generator-trace-gram)]
     (every? true?
             (for [A (range 6) B (range 6)]
               (< (abs-num (- (get-in K [A B]) (if (= A B) 0.5 0.0))) eps))))))

(defn- basis-projection
  "Coefficient of generator C in a bivector-space matrix X = sum_D coeff_D T_D
  -- valid because `generator-trace-gram` is DIAGONAL in this basis (checked
  by gtg_test.cljc), so coeff_C = Tr(X T_C) / K[C][C] with no cross terms."
  [X C K]
  (/ (c/re (c/m-trace (c/m-mul X (nth generators C))))
     (get-in K [C C])))

(defn true-structure-constants
  "The GENUINE so(1,3) structure constants in this basis, f-true[A][B][C],
  defined by [T_A,T_B] = i f-true[A][B][C] T_C (sum over C) -- obtained by
  taking the actual commutator of the basis generators and projecting it back
  onto the basis via `basis-projection` (using the REAL, non-1/2 trace
  pairing `generator-trace-gram`), independently of
  `kotoba.sm.gauge/structure-constants`'s implementation. Now that
  `kotoba.sm.gauge/structure-constants` has been generalized to compute its
  own Gram matrix, this independently-derived value and
  `rotation-raw-structure-constants` MATCH (gtg_test.cljc's
  `structure-constants-now-match-genuine-values-after-gauge-fix`) -- this
  function is kept anyway as an independent cross-check/derivation, not
  merely a historical artifact."
  []
  (let [K (generator-trace-gram)]
    (vec (for [A (range 6)]
           (vec (for [B (range 6)]
                  (let [[a b] (nth generator-index-pairs A)
                        [c d] (nth generator-index-pairs B)
                        comm (c/m-commutator (generator a b) (generator c d))
                        ;; comm = i * (sum_C f[C] T_C)  =>  (sum_C f[C] T_C) = -i * comm
                        y (c/m-scale (c/c 0 -1) comm)]
                    (vec (for [C (range 6)]
                           (basis-projection y C K))))))))))

(defn rotation-raw-structure-constants
  "`kotoba.sm.gauge/structure-constants` applied to this namespace's 6 so(1,3)
  generators. Named so `rotation-field-strength` and the test suite share one
  computed value instead of recomputing it ad hoc; kept its Phase-0a name
  ('raw') for continuity even though it is no longer 'raw' in the sense of
  being uncorrected -- see FIXED note below.

  FIXED (previously a CAVEAT -- see `compact-group-trace-normalization-holds?`
  / `true-structure-constants` / gtg_test.cljc): Phase 0a found that
  `kotoba.sm.gauge/structure-constants` assumed Tr(T^aT^b)=1/2delta^ab, which
  does NOT hold for this generator set, making its output for this call off
  from the genuine so(1,3) structure constants by a factor of 2*K[C][C] --
  i.e. +2 for a rotation-type third index and -2 (wrong SIGN, not just wrong
  magnitude) for a boost-type third index. `kotoba.sm.gauge/structure-constants`
  has SINCE BEEN GENERALIZED to compute its own generator set's trace-Gram
  matrix K[A][B]=Tr(T_AT_B) (which for THIS generator set is diagonal, so the
  generalization applies cleanly -- see `kotoba.sm.gauge`'s namespace
  docstring) instead of assuming it is 1/2delta^AB, so this call now returns
  the GENUINE so(1,3) structure constants, numerically matching
  `true-structure-constants` (verified in gtg_test.cljc)."
  []
  (gauge/structure-constants generators))

;; ---------------------------------------------------------------------------
;; 4. rotation gauge field Omega_mu and its field strength (curvature bivector)
;;    R_mu-nu, via kotoba.sm.gauge/field-strength applied to `generators`.
;; ---------------------------------------------------------------------------

(defn rotation-gauge-field-gradient
  "d Omega_nu^k / d x^mu via central finite differences, for a rotation-gauge
  field function Omega-field: R^4 -> (vector-of-4 vector-of-6 reals),
  Omega-field(x)[nu][k] = Omega_nu^k(x) (k indexes `generator-index-pairs`).
  A thin, GTG-named pass-through to `kotoba.sm.gauge/gauge-field-gradient` --
  this namespace does not reimplement finite differencing."
  ([Omega-field x] (gauge/gauge-field-gradient Omega-field x))
  ([Omega-field x h] (gauge/gauge-field-gradient Omega-field x h)))

(defn rotation-field-strength
  "R_mu-nu = d_mu Omega_nu - d_nu Omega_mu + g f^abc Omega_mu^b Omega_nu^c,
  the GTG curvature bivector, via `kotoba.sm.gauge/field-strength` applied to
  this namespace's 6 so(1,3) generators -- Lasenby-Doran-Gull 1998's
  observation that this is exactly the non-abelian Yang-Mills field-strength
  formula, unmodified, with the Lorentz-algebra bivector generators standing
  in for an internal gauge group.

  `d-Omega[mu][nu][k]` = d Omega_nu^k / d x^mu (see
  `rotation-gauge-field-gradient`); `Omega[mu][k]` = Omega_mu^k(x) at the same
  spacetime point. The CURL term d_mu Omega_nu - d_nu Omega_mu is pure
  antisymmetric differencing and never depended on the structure-constant
  normalization; the SELF-INTERACTION term g f^abc Omega_mu^b Omega_nu^c uses
  `rotation-raw-structure-constants`, which (see the FIXED note there) now
  returns the genuine so(1,3) structure constants.

  R_mu-nu^k = -R_nu-mu^k (the physically required curvature-bivector
  antisymmetry) NOW HOLDS EVEN WHEN THE EXCITED Omega COMPONENTS MIX
  BOOST-TYPE AND ROTATION-TYPE INDICES. This used to fail for mixed
  boost/rotation self-interaction: `kotoba.sm.gauge/self-interaction-term`
  read the structure-constant array with the output/free index `a` in the
  wrong array slot (a bug independent of, and found after, the Phase-0a
  trace-Gram-normalization fix noted above), which is numerically invisible
  for compact groups (U(1)/SU(2)/SU(3), whose structure constants are
  totally antisymmetric under any index permutation) but broke R's
  mu<->nu antisymmetry here whenever the self-interaction term's two
  summed-over Omega components had DIFFERENT `generator-trace-gram` signs
  (one boost K=-1, one rotation K=+1) -- see
  `kotoba.sm.gauge`'s `self-interaction-term` docstring for the fix and
  `gtg_test.cljc`'s
  `rotation-field-strength-self-interaction-now-antisymmetric-for-mixed-trace-gram-sign-components-after-index-order-fix`
  for the before/after numeric record."
  [d-Omega Omega g]
  (gauge/field-strength (rotation-raw-structure-constants) g d-Omega Omega))

;; ---------------------------------------------------------------------------
;; 5. spin-connection covariant derivative on a Dirac spinor
;; ---------------------------------------------------------------------------

(defn spinor-covariant-derivative
  "The spin-connection covariant derivative on a Dirac spinor,
  D_mu psi = d_mu psi - i g Omega_mu^{k} T_k psi (sum over the 6 generators,
  k indexing `generator-index-pairs`), via
  `kotoba.sm.gauge/covariant-derivative` applied to this namespace's 6 so(1,3)
  generators -- unmodified, the same generic function `kotoba.sm.standard-model`
  already reuses for the 3 internal SM gauge groups.

  `d-mu-psi` is the ordinary partial derivative of psi along this direction;
  `Omega-mu` is the 6-vector of rotation-gauge components Omega_mu^k(x) at
  this point; `g` is a coupling constant. At Omega-mu = [0 0 0 0 0 0] this
  reduces EXACTLY to `d-mu-psi` (checked in gtg_test.cljc against
  `kotoba.sm.spinor`'s free Dirac-equation residual, not just numerically
  close)."
  [d-mu-psi Omega-mu g psi]
  (gauge/covariant-derivative d-mu-psi generators Omega-mu g psi))

;; ---------------------------------------------------------------------------
;; 6. flat-limit check support: covariant Dirac-equation residual under the
;;    rotation gauge connection
;; ---------------------------------------------------------------------------

(defn dirac-residual-with-rotation-gauge
  "(i gamma^mu D_mu - m) psi(x), the covariant Dirac-equation residual under
  the rotation-gauge (spin) connection Omega_mu, evaluated numerically:
  the ordinary derivative via `kotoba.sm.spinor/spinor-four-gradient` (reused,
  not reimplemented), then `spinor-covariant-derivative`'s gauge correction on
  top. `Omega-mu-field` is a function R^4 -> (vector-of-4 vector-of-6 reals),
  same shape as `rotation-gauge-field-gradient`'s `Omega-field` argument.

  At Omega-mu-field = (constantly [[0 0 0 0 0 0] [0 0 0 0 0 0] [0 0 0 0 0 0]
  [0 0 0 0 0 0]]), this is EXACTLY (bit-identical, since
  `kotoba.sm.gauge/gauge-correction` returns the literal zero vector when
  every A_mu^a is 0 -- not merely small) `kotoba.sm.spinor/dirac-residual` on
  the same `psi-field`/`m`/`x` -- the flat-limit check in gtg_test.cljc."
  [psi-field Omega-mu-field m g x]
  (let [dpsi (spinor/spinor-four-gradient psi-field x)
        psi-x (psi-field x)
        Omega-x (Omega-mu-field x)
        D-psi (vec (for [mu (range 4)]
                      (spinor-covariant-derivative (nth dpsi mu) (nth Omega-x mu) g psi-x)))
        terms (for [mu (range 4)] (c/m-vec (nth spinor/gammas mu) (nth D-psi mu)))
        slash-D (reduce c/v-add (vec (repeat 4 c/zero)) terms)
        i-slash-D (c/v-scale c/i slash-D)
        m-psi (c/v-scale (c/c m 0) psi-x)]
    (c/v-sub i-slash-D m-psi)))

;; ---------------------------------------------------------------------------
;; 7+8+9. position gauge field h_mu(x) and the derived metric g_mu-nu(x),
;;    Phase 0b -- see the namespace docstring's Phase-0b SCOPE note (items
;;    7-9) for the full description.
;;
;;    COMPATIBILITY WITH THE EXISTING GLOBAL SO(3,1)+ REPRESENTATION (item 9):
;;    a CONSTANT position-gauge field h = Lambda, built from ANY
;;    `kotoba.sm.vector-field/boost`/`rotation-x`/`rotation-y`/`rotation-z`
;;    matrix (with Omega_mu = 0, i.e. no rotation-gauge connection -- Phase
;;    0a's sector switched off), is included in this sector as a special case
;;    that reproduces the flat metric EXACTLY, not approximately. Derivation:
;;    `vector-field/lorentz?` checks Lambda^T eta Lambda = eta. Right-multiply
;;    both sides by Lambda^-1: Lambda^T eta = eta Lambda^-1, then left-
;;    multiply by eta^-1 = eta (eta is its own inverse in this basis):
;;    Lambda^-1 = eta Lambda^T eta. Substitute into Lambda Lambda^-1 = I:
;;    Lambda eta Lambda^T eta = I, then right-multiply by eta^-1 = eta:
;;    Lambda eta Lambda^T = eta. So Lambda^T eta Lambda = eta ALSO implies the
;;    'other' contraction Lambda eta Lambda^T = eta -- and `derived-metric`
;;    applied to h = Lambda computes exactly
;;    (derived-metric Lambda)[mu][nu] = sum_a eta[a][a] Lambda[mu][a] Lambda[nu][a]
;;    which IS (Lambda eta Lambda^T)[mu][nu] (eta diagonal collapses the
;;    double sum to the single shared index a). Hence `derived-metric` of any
;;    Lorentz matrix equals `kotoba.sm.tensor/metric` exactly (up to
;;    floating-point roundoff from the sqrt/cos/sin inside `boost`/
;;    `rotation-*`), numerically checked in gtg_test.cljc's
;;    `global-lorentz-transformations-are-the-constant-flat-special-case`.
;; ---------------------------------------------------------------------------

(def position-gauge-identity
  "The trivial position gauge field h_mu^nu = delta_mu^nu (the 4x4 identity
  matrix): 'gauge coordinates = physical coordinates'. `h[mu][nu]` is
  h_mu^nu -- the physical-spacetime component `nu` of the image, under the
  position-gauge map h, of the gauge-coordinate-direction-`mu` basis vector,
  so row `mu` of this matrix IS the physical four-vector h_mu (same
  [t x y z]-component convention `kotoba.sm.tensor`/`kotoba.sm.vector-field`
  use everywhere else). Kept as plain integers (not floats) so that
  `derived-metric` applied to it stays exact integer arithmetic throughout,
  for a bit-for-bit (not merely approximate) flat-limit check against
  `kotoba.sm.tensor/metric` -- see gtg_test.cljc's
  `flat-limit-h-reproduces-minkowski-metric-exactly`."
  [[1 0 0 0]
   [0 1 0 0]
   [0 0 1 0]
   [0 0 0 1]])

(defn derived-metric
  "The GTG derived metric g_mu-nu = h_mu . h_nu = eta_ab h_mu^a h_nu^b, for a
  position-gauge-field VALUE `h` (a 4x4 real matrix, row `mu` = the physical
  four-vector h_mu -- see `position-gauge-identity`) AT A SINGLE spacetime
  point. Computed by treating each row of `h` as an upper-index four-vector
  and taking `kotoba.sm.tensor/dot` (the EXISTING Minkowski inner product,
  eta = diag(1,-1,-1,-1)) of every pair of rows -- this function supplies
  only the h_mu . h_nu bookkeeping on top of that existing inner product, no
  new linear-algebra machinery.

  Returned as a plain 4x4 real matrix, the same shape as
  `kotoba.sm.tensor/metric` itself -- which is exactly what this reduces to
  at `h` = `position-gauge-identity` (gtg_test.cljc's
  `flat-limit-h-reproduces-minkowski-metric-exactly`), and, more generally,
  at `h` = any constant Lorentz transformation matrix from
  `kotoba.sm.vector-field` (this namespace's Phase-0b section-7 header
  comment above, and gtg_test.cljc's
  `global-lorentz-transformations-are-the-constant-flat-special-case`)."
  [h]
  (vec (for [mu (range 4)]
         (vec (for [nu (range 4)]
                (tensor/dot (nth h mu) (nth h nu)))))))

(defn derived-metric-field
  "g_mu-nu(x) for a position-gauge FIELD function h-field: R^4 -> 4x4 matrix
  (h-field(x)[mu][nu] = h_mu^nu(x)), at spacetime point x -- `derived-metric`
  applied to (h-field x). The field-valued analogue of `derived-metric`, the
  same relationship `rotation-gauge-field-gradient`/`rotation-field-strength`
  already have to a single `Omega` VALUE via their `Omega-field` argument."
  [h-field x]
  (derived-metric (h-field x)))

(defn derived-metric-matches-flat?
  "Does the derived metric g_mu-nu built from position-gauge-field VALUE `h`
  equal `kotoba.sm.tensor/metric`, component by component, within `eps`?
  Used both for the exact flat-limit check (`h` = `position-gauge-identity`)
  and the global-Lorentz-as-special-case check (`h` = a constant Lorentz
  matrix from `kotoba.sm.vector-field`) -- see this namespace's Phase-0b
  section-7 header comment above for why both are expected to hold exactly,
  up to floating-point roundoff."
  ([h] (derived-metric-matches-flat? h 1e-9))
  ([h eps]
   (let [g (derived-metric h)]
     (every? true?
             (for [mu (range 4) nu (range 4)]
               (< (abs-num (- (get-in g [mu nu]) (get-in tensor/metric [mu nu]))) eps))))))

;; ---------------------------------------------------------------------------
;; 10. Phase 0c -- curvature quadratic invariant, narrowly scoped to
;;    h = position-gauge-identity. See the namespace docstring's Phase-0c
;;    SCOPE note (item 10) for the full derivation and, crucially, for why
;;    this is honestly NOT the Lasenby-Doran-Gull curvature scalar R.
;; ---------------------------------------------------------------------------

(defn curvature-bivector-component
  "R_mu-nu^k (`rotation-field-strength`'s output `R[mu][nu][k]`) with the
  bivector-generator index `k` held FIXED, reshaped into a plain 4x4 real
  rank-2 tensor R^{mu-nu} (upper spacetime indices) -- exactly the shape
  `kotoba.sm.tensor`'s raise/lower/contract functions (`lower2`,
  `full-contract`) already expect. Internal-use helper for
  `curvature-quadratic-invariant`, exposed because it is independently
  useful/checkable (e.g. against `rotation-field-strength-curl-term-matches-
  yang-mills-form`'s hand-built `R`)."
  [R k]
  (vec (for [mu (range 4)]
         (vec (for [nu (range 4)]
                (get-in R [mu nu k]))))))

(defn curvature-quadratic-invariant
  "A curvature INVARIANT built from the rotation-gauge curvature bivector
  R_mu-nu (`rotation-field-strength`'s output) ALONE:

    I = sum_k K[k][k] * (R_mu-nu^k R^{mu-nu}_k)

  where, for each of the 6 bivector-generator components `k`
  (`generator-index-pairs`), `R_mu-nu^k R^{mu-nu}_k` is
  `kotoba.sm.tensor/full-contract` of `curvature-bivector-component`'s
  fixed-k rank-2 slice against its own `kotoba.sm.tensor/lower2` (BOTH
  spacetime indices lowered via the Minkowski metric eta -- `tensor.cljc`'s
  EXISTING raise/lower/contract machinery, reused unmodified, no new
  tensor-algebra primitives added here), and `K` is `generator-trace-gram`
  (this namespace's own diagonal so(1,3) Killing-form-like trace pairing from
  section 3 above: +1 for the 3 rotation-type generators, -1 for the 3
  boost-type ones). This is exactly the
  'eta^mu-rho eta^nu-sigma R_mu-nu . R_rho-sigma' quadratic contraction (a
  bivector-valued Yang-Mills-field-strength-squared-style invariant, the
  so(1,3) analogue of F_mu-nu^a F^mu-nu_a), collapsed via the diagonal metric
  so only rho=mu, sigma=nu survive.

  *** HONESTY NOTE, READ BEFORE USING THIS AS 'the curvature scalar': *** this
  is NOT the Lasenby-Doran-Gull (1998) curvature scalar
  R = h^mu ^ h^nu . R(h-bar_nu, h-bar_mu). That true definition, even
  restricted to h = `position-gauge-identity` (the one case where the
  reciprocal frame h-bar = h = the identity trivially, needing no matrix
  inverse), is a SINGLE LINEAR contraction of R_mu-nu against the FIXED
  bivector h^mu^h^nu (which does not itself depend on R) -- the same
  relationship the (linear) Ricci scalar has to the full Riemann tensor. This
  function computes a QUADRATIC (R contracted against itself) invariant
  instead -- the same relationship the Kretschmann scalar R_abcd R^abcd has
  to the Riemann tensor in ordinary GR. Ricci scalar and Kretschmann scalar
  are DIFFERENT invariants of DIFFERENT degree in the curvature: related only
  in that both vanish exactly when the full curvature vanishes (see
  gtg_test.cljc's flat-limit test), NOT proportional to each other and NOT
  interchangeable in general -- so this function's numeric output should not
  be read as 'the GTG curvature scalar' or used as a stand-in for it. The
  true linear LDG contraction is deliberately NOT implemented here either
  (see the namespace docstring's Phase-0c SCOPE note, item 10, for why:
  pinning down which spacetime index pairs with which bivector-value index
  needs an LDG-convention detail this pass has no independent literature
  value to test against, so it is left as a named follow-up rather than
  guessed at).

  Also NOT guaranteed non-negative: `generator-trace-gram`'s K is indefinite
  (+1/-1), so a boost-dominated curvature can make this negative -- a further
  symptom, like `compact-group-trace-normalization-holds?`'s finding, of this
  generator set's noncompactness."
  [R]
  (let [K (generator-trace-gram)]
    (reduce +
            (for [k (range 6)]
              (let [Rk (curvature-bivector-component R k)
                    Rk-lower (tensor/lower2 Rk)]
                (* (get-in K [k k]) (tensor/full-contract Rk Rk-lower)))))))

;; ---------------------------------------------------------------------------
;; 11. Phase 0d -- reciprocal (dual) frame h-bar^mu for a GENERAL invertible
;;    position-gauge field h, via `kotoba.sm.tensor/mat-inverse` (a general
;;    NxN matrix inverse, ordinary linear algebra, no physics convention).
;;    See the namespace docstring's Phase-0d SCOPE note (item 11) for the
;;    full derivation and, crucially, for the honesty note on why this is a
;;    standard dual-basis construction and NOT asserted to be a literature-
;;    exact port of the Lasenby-Doran-Gull geometric-algebra reciprocal frame
;;    for a general h.
;; ---------------------------------------------------------------------------

(defn reciprocal-frame
  "The reciprocal (dual) frame h-bar^mu of a GENERAL invertible position-gauge
  field VALUE `h` (a 4x4 real matrix, row `mu` = the physical four-vector
  h_mu -- same layout as `position-gauge-identity`/`derived-metric`, see item
  7's docstring), defined by the STANDARD linear-algebra dual-basis
  biorthogonality relation

    h-bar^mu . h_nu = delta^mu_nu

  where '.' here is the PLAIN component (Kronecker) pairing
  sum_a h-bar^mu[a] h_nu[a] -- the ordinary dual-basis construction for ANY
  basis {h_mu} of R^4, independent of any metric and independent of any
  GTG-paper-specific convention (see this function's HONESTY NOTE below for
  exactly how this differs from, and is NOT verified against, the
  Lasenby-Doran-Gull geometric-algebra reciprocal frame, which uses the
  Minkowski-metric pairing `kotoba.sm.tensor/dot` instead of this plain
  component pairing).

  DERIVATION: write `h` as a 4x4 matrix H (row `mu` = h_mu) and the sought
  reciprocal frame as a 4x4 matrix Hbar (row `mu` = h-bar^mu). The
  biorthogonality condition, component by component, is
  sum_a Hbar[mu][a] * H[nu][a] = delta[mu][nu]; the left side is exactly
  (Hbar . H^T)[mu][nu] (ordinary matrix product), so the condition is the
  matrix equation Hbar . H^T = I, i.e. Hbar = (H^T)^-1 = (H^-1)^T. This
  function computes exactly that: `kotoba.sm.tensor/mat-inverse` (throws if
  `h` is singular) then `kotoba.sm.tensor/mat-transpose`.

  VERIFICATION (gtg_test.cljc): (a) for a concrete invertible, non-identity
  4x4 matrix, `kotoba.sm.tensor/mat-inverse` genuinely satisfies
  h * h^-1 = h^-1 * h = the 4x4 identity. (b) the biorthogonality relation
  h-bar^mu . h_nu = delta^mu_nu (plain component pairing) holds numerically
  for that same non-identity h. (c) at h = `position-gauge-identity`,
  h-bar = h EXACTLY (the identity matrix is its own inverse and its own
  transpose, so Hbar = (I^-1)^T = I^T = I = H -- bit-for-bit, not merely
  close). (d) a singular (determinant ~0) h throws `ex-info` (propagated
  from `mat-inverse`) rather than silently dividing by ~0 or returning a
  garbage matrix.

  HONESTY NOTE, READ BEFORE USING THIS AS 'the LDG reciprocal frame' for a
  general h: *** this function's biorthogonality pairing is the PLAIN
  component/Kronecker pairing, NOT the Minkowski-metric GA scalar product
  `kotoba.sm.tensor/dot` that a GA-native reciprocal frame would generally be
  defined with. *** Working the Minkowski-pairing version through the same
  derivation: sum_a eta[a][a] Hbar[mu][a] H[nu][a] = delta[mu][nu] is the
  matrix equation Hbar . eta . H^T = I, giving Hbar_eta = (H^-1)^T . eta (eta
  is its own inverse in this basis) -- a DIFFERENT matrix from this
  function's Hbar in general, and in particular at h =
  `position-gauge-identity` it gives Hbar_eta = eta = diag(1,-1,-1,-1), i.e.
  h-bar^0 = h_0 but h-bar^i = -h_i for the 3 spatial rows -- NOT h-bar = h.

  *** FOLLOW-UP LITERATURE CHECK (Phase 0d, stage 2 investigation): this
  function's h-of-h reciprocal frame turns out NOT to be what the actual
  Lasenby-Doran-Gull curvature scalar needs at all. *** Reading the primary
  source directly (Lasenby, Doran & Gull, 'Gravity, Gauge Theories and
  Geometric Algebra', Phil. Trans. R. Soc. Lond. A (1998) 356 487-582,
  updated arXiv version gr-qc/0405033, section 4 'The field equations',
  eqns 4.9, 4.11, 4.12) and a second, independent, mutually-corroborating
  source by two of the same three authors (Lewis, Doran & Lasenby,
  'Quadratic Lagrangians and Topology in Gauge Theory Gravity',
  arXiv gr-qc/9910039, section 2, eqns 5, 6, 12, 14), the Ricci SCALAR is:

    R = sum_{a,b} gamma^a . (gamma^b . R(h_b ^ h_a))

  where h_b = h(gamma_b) (source 1's h_mu, EXACTLY this namespace's Phase 0b
  `h`/`position-gauge-identity` convention -- gr-qc/0405033 eq 3.35's
  g_mu = h^-1(e_mu) is a DIFFERENT, h^-1-built quantity, not this one),
  gamma^a is the reciprocal of the FIXED BACKGROUND orthonormal frame
  gamma_a (TRIVIAL under the Minkowski metric -- gamma^0=gamma_0,
  gamma^i=-gamma_i, i.e. `kotoba.sm.tensor/raise` applied to the ordinary
  basis vectors, NOT a reciprocal frame of h at all), and R(x^y) is the
  BILINEAR extension of Phase 0a's `rotation-field-strength` to an arbitrary
  bivector argument (justified rigorously, not guessed: R_ab is DEFINED as
  D_a Omega_b - D_b Omega_a + Omega_a x Omega_b, manifestly bilinear in a,b
  since Omega(a) is itself linear in a by construction -- so
  R(h_b^h_a) = sum_{rho,sigma} h[b][rho] h[a][sigma] R[rho][sigma] follows
  from `rotation-field-strength`'s own defining bilinearity, needing no new
  literature confirmation).

  Both sources independently agree on this formula's STRUCTURE, and in
  particular BOTH show the outer contraction uses the FIXED frame's OWN
  reciprocal (gamma^a, no inverse of h needed), NOT `reciprocal-frame`
  (h-bar of h) as originally guessed when this function was written -- a
  genuine, literature-grounded correction to that initial assumption.
  HOWEVER, translating 'gamma^b . R(h_b^h_a)' (a vector . bivector -> vector
  Clifford-algebra contraction) into this codebase's R[mu][nu][k]
  six-generator-component array representation (rather than a native GA
  multivector) requires an ADDITIONAL, nontrivial contraction step -- which
  of R's spacetime-index/generator-index slots the contracting vector's
  index pairs with, and with what sign/factor -- that NEITHER source spells
  out in a form directly transcribable to this array representation, and
  that this pass could not independently re-derive with confidence within a
  bounded research effort (a hand re-derivation via the standard GA identity
  v.(a^b)=(v.a)b-(v.b)a produced a candidate formula but with unresolved
  factor-of-2/sign risk once expressed over the SIX generator components
  rather than a full antisymmetric rank-2 slice, and no independent
  numeric-example reference value was found to test a candidate against).
  This is exactly the class of error this codebase's own established
  practice already treats as too risky to guess at without independent
  verification -- see `kotoba.sm.gauge/self-interaction-term`'s
  since-fixed slot-order bug (gtg.cljc's rotation-field-strength docstring)
  and `curvature-quadratic-invariant`'s own honesty note (item 10) for two
  prior instances of the SAME 'which index pairs with which' risk in this
  exact curvature-scalar problem. `curvature-scalar` is therefore
  DELIBERATELY NOT implemented in this namespace -- see the README's Phase
  0d section for the fuller writeup of this investigation, including both
  source URLs. `reciprocal-frame` is offered only as a standard,
  independently-correct dual-basis construction of h's own reciprocal frame
  (useful in its own right, e.g. for a future combined covariant derivative,
  still out of scope -- see the namespace docstring's out-of-scope list),
  not asserted to be an ingredient of the LDG curvature scalar for a general
  h."
  ([h] (reciprocal-frame h 1e-9))
  ([h eps]
   (tensor/mat-transpose (tensor/mat-inverse h eps))))

;; ---------------------------------------------------------------------------
;; 12. Phase 0e -- GA-native, Minkowski-paired reciprocal frame. Completes the
;;    'Hbar_eta' alternative `reciprocal-frame`'s own HONESTY NOTE (item 11
;;    above) already derives algebraically but stops short of implementing.
;;    See the namespace docstring's Phase-0e SCOPE note (item 13) for the
;;    summary and item 14 for the separate, DECLINED stage-2
;;    curvature-scalar investigation this phase also attempted.
;; ---------------------------------------------------------------------------

(defn reciprocal-frame-minkowski
  "The Geometric-Algebra-NATIVE reciprocal (dual) frame h-bar^mu_eta of a
  GENERAL invertible position-gauge field VALUE `h` (same 4x4-matrix layout
  as `reciprocal-frame`/`derived-metric`/`position-gauge-identity` -- row
  `mu` = the physical four-vector h_mu), defined by the biorthogonality
  relation

    h-bar^mu . h_nu = delta^mu_nu

  where THIS TIME '.' is `kotoba.sm.tensor/dot`, the Minkowski INVARIANT
  inner product (eta = diag(1,-1,-1,-1)) -- NOT `reciprocal-frame`'s (Phase
  0d, item 11) plain component/Kronecker pairing. The Minkowski pairing is
  the one Geometric Algebra / GTG actually use for a scalar product (the GA
  scalar product IS the Minkowski-metric contraction), so THIS function --
  not `reciprocal-frame` -- is the one that deserves to be called 'the GTG
  reciprocal frame' of a general h. Given a separate, distinctly-named
  function (not a second arity of `reciprocal-frame`) so both pairings stay
  independently callable/checkable, and `reciprocal-frame`'s existing
  plain-pairing tests keep exercising exactly the function they were written
  against.

  DERIVATION (this is the same derivation `reciprocal-frame`'s own HONESTY
  NOTE already writes out algebraically -- re-derived and numerically
  checked here from scratch, not taken on faith): write `h` as a 4x4 matrix
  H (row `mu` = h_mu) and the sought frame as Hbar (row `mu` = h-bar^mu).
  Component by component, the Minkowski-paired biorthogonality condition is
  sum_a eta[a][a] Hbar[mu][a] H[nu][a] = delta[mu][nu]. Writing eta as the
  diagonal 4x4 matrix `kotoba.sm.tensor/metric`, the left side is exactly
  (Hbar . eta . H^T)[mu][nu] (ordinary matrix product, eta between Hbar and
  H^T because it is eta[a][a] that sits between the two matching index-`a`
  factors), so the condition is the matrix equation Hbar . eta . H^T = I,
  i.e. Hbar = (eta . H^T)^-1 = (H^T)^-1 . eta^-1 = (H^-1)^T . eta (eta is its
  own matrix inverse in this basis, eta . eta = I -- the same fact
  `kotoba.sm.tensor`'s own `raise`/`lower` docstrings already rely on). This
  function computes exactly that: `kotoba.sm.tensor/mat-inverse` (throws on
  a ~0 determinant, same guard `reciprocal-frame` uses), then
  `kotoba.sm.tensor/mat-transpose`, then right-multiply by
  `kotoba.sm.tensor/metric` via `kotoba.sm.tensor/mat-mat`.

  VERIFICATION (gtg_test.cljc): (a) for `a-non-identity-invertible-h` (the
  same concrete non-identity invertible h `reciprocal-frame`'s own tests
  use), the Minkowski-paired biorthogonality relation
  h-bar^mu . h_nu = delta^mu_nu (`kotoba.sm.tensor/dot`, NOT plain-component
  pairing) holds numerically for every (mu,nu) pair -- and the resulting
  Hbar is numerically DIFFERENT from `reciprocal-frame`'s plain-pairing
  output for the SAME h: concretely, h-bar_eta^0 = [0.5 0 0.5 0] versus
  `reciprocal-frame`'s h-bar^0 = [0.5 0 -0.5 0] -- the two agree on the
  timelike (index-0) column and differ in SIGN on every spatial column,
  exactly as predicted by Hbar_eta = Hbar_flat . eta (right-multiplying by
  the diagonal eta scales column `a` by eta[a][a], i.e. negates the 3
  spatial columns and leaves the timelike column alone). (b) at
  h = `position-gauge-identity`, h-bar_eta = eta EXACTLY (bit-for-bit,
  integer arithmetic throughout, not merely close): h-bar^0 = h_0 =
  [1 0 0 0], but h-bar^i = -h_i for the 3 spatial rows (e.g.
  h-bar^1 = [0 -1 0 0]) -- genuinely DIFFERENT from `reciprocal-frame`'s
  h-bar = h at the very same point, confirming (not merely restating) the
  divergence `reciprocal-frame`'s own HONESTY NOTE predicted without
  numerically checking it. (c) for a CONSTANT Lorentz transformation
  h = Lambda (any of `kotoba.sm.vector-field`'s existing boost/rotation
  matrices), h-bar_eta = eta . Lambda EXACTLY (up to floating-point roundoff
  from `boost`/`rotation-*`'s sqrt/cos/sin) -- a closed form derivable from
  `vf/lorentz?`'s defining property Lambda^T eta Lambda = eta: right-
  multiplying both sides by Lambda^-1 gives Lambda^T eta = eta Lambda^-1, so
  Lambda^-1 = eta Lambda^T eta (eta^-1 = eta), hence
  Hbar_eta = (Lambda^-1)^T . eta = (eta Lambda^T eta)^T . eta =
  eta Lambda eta . eta = eta Lambda (eta symmetric, eta . eta = I) -- i.e.
  row `mu` of Hbar_eta is row `mu` of Lambda scaled by eta[mu][mu] (+1 for
  mu=0, -1 for mu=1,2,3). Checked for several concrete boosts/rotations, not
  merely argued for one.

  HONESTY NOTE: this completes the Minkowski-paired reciprocal frame that
  `reciprocal-frame`'s own docstring derives but stops short of implementing
  -- it does NOT by itself resolve Phase 0d stage 2's open question (see
  `reciprocal-frame`'s docstring's FOLLOW-UP LITERATURE CHECK): the true LDG
  curvature scalar R's outer contraction uses the FIXED background frame's
  OWN reciprocal gamma^a (trivial under the metric, `tensor/raise` of the
  ordinary basis vectors), NOT a reciprocal frame OF h at all -- whether
  Minkowski-paired (this function) or plain-paired (`reciprocal-frame`). See
  the namespace docstring's item 14 for this phase's separate, DECLINED
  attempt to make further progress on R via independent numerical
  verification (linearized weak-field GR), and exactly where that attempt
  stopped (the h_mu(x)->Omega_mu(x) correspondence itself, needed even
  before R's own outer-contraction ambiguity comes into play, is not
  established anywhere in this codebase). This function is offered as h's
  standard GA-native dual basis in its own right (e.g. for a future combined
  covariant derivative, still out of scope), the same status
  `reciprocal-frame` already has for the plain-pairing version -- not
  asserted to be an ingredient of the LDG curvature scalar for a general h."
  ([h] (reciprocal-frame-minkowski h 1e-9))
  ([h eps]
   (tensor/mat-mat (tensor/mat-transpose (tensor/mat-inverse h eps)) tensor/metric)))

;; ---------------------------------------------------------------------------
;; PHASE 1 -- the vacuum/spin-free field equation Omega(h) (eq 4.53), the
;;    covariant Riemann map R(a^b) (eq 4.48), and the true LDG Ricci scalar
;;    (item 15/16/17 above). See the namespace docstring's PHASE 1 section
;;    for the full scope statement and literature derivation; this section's
;;    per-function docstrings carry the exact formula and verification notes.
;;
;;    DATA REPRESENTATION, kept deliberately close to Phase 0a-0e: a bivector
;;    is a 6-component real vector in `generator-index-pairs` order (the SAME
;;    shape Omega_mu/R_mu-nu^k already use); a position-gauge field VALUE is
;;    a 4x4 real matrix, row mu = h(e_mu) (the SAME STORED layout `h`,
;;    `position-gauge-identity`, `derived-metric` already use); a
;;    position-gauge FIELD is a function x -> that 4x4 matrix (the SAME shape
;;    `derived-metric-field`'s `h-field` argument already uses). No new
;;    multivector/full-geometric-algebra representation is introduced -- the
;;    handful of primitives below (`frame-adjoint`, `bivector->matrix`,
;;    `matrix->bivector`, `wedge-vectors`, `vector-dot-bivector`,
;;    `bivector-commutator`) are the MINIMAL set needed to transcribe LDG's
;;    eqs (4.42)/(4.46)/(4.48)/(4.49)/(4.53), each one independently
;;    numerically cross-checked (not merely hand-derived) against a
;;    standalone Python/numpy geometric-algebra reference engine before being
;;    trusted here -- see each function's own docstring for exactly which
;;    identity it implements.
;;
;;    NUMERICAL METHOD: both the position-gauge field `h` and the rotation-
;;    gauge field this phase derives from it, Omega(h), are evaluated purely
;;    numerically (central finite differences, `kotoba.sm.vector-field`'s
;;    existing `four-gradient-vec` for the INNER derivative inside `H-field`,
;;    `kotoba.sm.gauge`'s existing `gauge-field-gradient` for the OUTER
;;    derivative inside `L-a-omega`) -- there is no symbolic-differentiation
;;    layer in this codebase (see `kotoba.sm.vector-field`'s own namespace
;;    docstring). This means BOTH derivative levels needed by eq (4.49)'s
;;    curl-of-hbar-inverse (inner) and eq (4.48)'s L_a (outer) carry their
;;    own finite-difference truncation error, and the two compound. The
;;    default step sizes below (`default-fd-h` = 2e-4 at BOTH levels) were
;;    picked by an independent numerical experiment (the same standalone
;;    Python verification script, run with FD substituted for its otherwise-
;;    symbolic inner derivative, to confirm the FD/FD pipeline this namespace
;;    actually uses -- not the symbolic/FD hybrid the reference script uses
;;    by default -- still reproduces LDG's closed-form Schwarzschild solution
;;    to ~1e-9..1e-10, well within gtg_test.cljc's ~1e-9 tolerance) rather
;;    than guessed at; see gtg_test.cljc's own Schwarzschild-regression tests
;;    for the achieved precision on THIS codebase's actual Clojure
;;    implementation. Every function below takes `fd-h`/`fd-h-inner`+
;;    `fd-h-outer` as explicit optional arguments (no dynamic-var coupling
;;    leaks across this section's public API) so a caller needing tighter or
;;    looser precision, or a smoother/rougher field, can override the
;;    default.
;; ---------------------------------------------------------------------------

(def default-fd-h
  "Default central-finite-difference step used at BOTH derivative levels
  (`H-field`'s inner curl, `L-a-omega`'s outer directional derivative) by
  every Phase 1 function's zero/two-arg arity -- see this section's header
  comment for how this value was picked."
  2.0e-4)

(defn- standard-basis-vector
  "e_mu as an ordinary 4-component vector (e.g. mu=1 -> [0.0 1.0 0.0 0.0]),
  mu in 0..3. Internal helper -- Phase 1's vector/bivector primitives below
  are built on top of this rather than a symbolic 'gamma_mu' object."
  [mu]
  (assoc [0.0 0.0 0.0 0.0] mu 1.0))

(defn frame-adjoint
  "The GTG/Clifford-algebra adjoint fbar of a position-gauge-field-SHAPED 4x4
  matrix VALUE `f` (`f[mu][nu]` = f_mu^nu, row mu = f(e_mu) -- the SAME
  STORED layout `h`/`position-gauge-identity`/`derived-metric` already use),
  defined by LDG eq (2.46): a.f(b) = fbar(a).b for all vectors a,b (`.` =
  `kotoba.sm.tensor/dot`, the Minkowski invariant inner product) -- the SAME
  adjoint relation Phase 0d/0e's reciprocal-frame derivations already invoke
  (`reciprocal-frame`/`reciprocal-frame-minkowski`'s own docstrings), applied
  here to a general FIELD VALUE `f` (needed: hbar := frame-adjoint of h)
  rather than only ever appearing inside a reciprocal-frame formula.

  DERIVATION: write `f` as a 4x4 matrix F (row mu = f(e_mu), this namespace's
  STORED convention) and STANDARD-CONVENTION matrix M_f (M_f @ a = f(a) for a
  a column vector) -- since row mu of F is f(e_mu) = column mu of M_f,
  M_f = `tensor/mat-transpose` F. Component-by-component, a.f(b) = fbar(a).b
  is a^T eta (M_f b) = (M_fbar a)^T eta b for all a,b, i.e. the matrix
  equation eta M_f = M_fbar^T eta, so M_fbar = eta M_f^T eta (eta is its own
  inverse in this basis) = eta @ F @ eta (since M_f^T = F). Converting back
  to STORED form (fbar's row mu = fbar(e_mu) = column mu of M_fbar, i.e.
  `tensor/mat-transpose` M_fbar): Fbar = (eta @ F @ eta)^T = eta @ F^T @ eta
  (eta symmetric). This function computes exactly that: `tensor/mat-mat`
  `tensor/metric` ( `tensor/mat-mat` (`tensor/mat-transpose` f) `tensor/metric` ).

  SELF-INVERSE (`frame-adjoint` (`frame-adjoint` f) = f, an algebraic
  consequence of eq 2.46 being symmetric under swapping f<->fbar and a<->b,
  NOT merely a coincidence of this codebase's convention): applying the
  formula twice, Fbarbar = eta @ Fbar^T @ eta = eta @ (eta F^T eta)^T @ eta =
  eta @ eta @ F @ eta @ eta = F (eta@eta=I). This means the SAME function
  both derives hbar from a h-FIELD (Phase 1's actual production use, inside
  `H-field`) and, symmetrically, can recover h from a literature hbar-first
  solution like LDG's own Schwarzschild eq (6.79) (used in gtg_test.cljc to
  build the test's h-field from the paper's hbar-first statement of that
  solution) -- gtg_test.cljc numerically verifies BOTH the involution
  property and, independently, that this formula reproduces a ground-truth
  h<->hbar pair computed via a standalone (Python/numpy) implementation of
  the SAME eq-(2.46) derivation, to machine precision."
  [f]
  (tensor/mat-mat tensor/metric (tensor/mat-mat (tensor/mat-transpose f) tensor/metric)))

(defn bivector->matrix
  "A 6-component bivector (`generator-index-pairs` order) -> the antisymmetric
  4x4 matrix it represents (Bmat[a][b] = B[k] for (a,b) = `generator-index-
  pairs`[k], Bmat[b][a] = -B[k], Bmat[a][a] = 0) -- the same convention a
  Python ga_algebra reference implementation's `bivector_to_matrix` uses,
  independently cross-checked against it. `matrix->bivector` is the inverse."
  [b]
  (reduce (fn [m [[a bb] val]]
            (-> m (assoc-in [a bb] val) (assoc-in [bb a] (- val))))
          (vec (repeat 4 (vec (repeat 4 0.0))))
          (map vector generator-index-pairs b)))

(defn matrix->bivector
  "An antisymmetric 4x4 matrix -> the 6-component bivector (`generator-index-
  pairs` order) it represents -- reads off `m[a][b]` for each (a,b) =
  `generator-index-pairs`[k]. Inverse of `bivector->matrix`."
  [m]
  (mapv (fn [[a bb]] (get-in m [a bb])) generator-index-pairs))

(defn wedge-vectors
  "u^v, the outer/wedge product of two ordinary 4-vectors u,v, as a
  6-component bivector: (u^v)_k = u[a]*v[b] - u[b]*v[a] for (a,b) =
  `generator-index-pairs`[k] -- the standard GA wedge product of two grade-1
  blades, independently cross-checked against a Python ga_algebra reference
  engine's `wedge` on random vector pairs."
  [u v]
  (mapv (fn [[a b]] (- (* (nth u a) (nth v b)) (* (nth u b) (nth v a)))) generator-index-pairs))

(defn vector-dot-bivector
  "v.B, the Hestenes inner product of an ordinary 4-vector v with a
  6-component bivector B, producing a vector: (v.B)^beta = sum_rho v_rho
  Bmat[rho][beta], v_rho = `tensor/lower` v (the standard GA grade-lowering
  contraction <vB>_1). DERIVATION: writing B as its antisymmetric matrix
  representation (`bivector->matrix`), this is the row-vector-times-matrix
  product `tensor/lower`(v) @ Bmat, i.e. `tensor/mat-vec` applied to
  `tensor/mat-transpose` of Bmat (so that summing over the FIRST matrix index
  against `tensor/lower`(v) lands in the right slot) -- independently cross-
  checked against a Python ga_algebra reference engine's `idot(v,B,1,2)` on
  both physically-generated and random bivectors."
  [v b]
  (tensor/mat-vec (tensor/mat-transpose (bivector->matrix b)) (tensor/lower v)))

(defn bivector-commutator
  "[B1,B2], the so(1,3) Lie bracket ('omega(a) x omega(b)' in LDG notation)
  of two bivector-coefficient-vectors B1,B2 (6-component, `generator-index-
  pairs` order): [B1,B2][a] = sum_{b,c} f-abc[b][c][a] B1[b] B2[c] -- the
  SAME f-abc[b][c][a] slot convention `kotoba.sm.gauge/self-interaction-term`
  already established for exactly this so(1,3) self-interaction structure
  (its own docstring has the derivation of why the output/target index sits
  in the THIRD slot for this generator set's non-uniform trace-Gram matrix);
  `f-abc` is `rotation-raw-structure-constants`. This is the REAL-coefficient
  (not complex-matrix) realization of the bivector cross product, already
  implicitly trusted by `rotation-field-strength`'s self-interaction term
  (Phase 0a) -- reused here as a standalone operation on two ARBITRARY
  bivectors (not necessarily Omega_mu, Omega_nu at fixed spacetime indices)."
  [f-abc B1 B2]
  (vec (for [a (range 6)]
         (reduce + (for [b (range 6) cc (range 6)]
                     (* (get-in f-abc [b cc a]) (nth B1 b) (nth B2 cc)))))))

(defn- congruence
  "F @ M @ F^T for 4x4 matrices F,M -- the matrix congruence transform
  underlying the outermorphism extension of a linear map to a bivector
  (`outermorphism` below). Internal-use helper (no independent GA meaning at
  this general-matrix level; `outermorphism` is the named, tested GA
  operation)."
  [F M]
  (tensor/mat-mat (tensor/mat-mat F M) (tensor/mat-transpose F)))

(defn outermorphism
  "F(B), the outermorphism extension of a linear map to a bivector B
  (6-component): if F is a linear map with F(u^v) = F(u)^F(v) for vectors
  u,v, then in matrix form (F given in STANDARD convention, F @ a = F(a) for
  a column vector a; B given via `bivector->matrix`), F(B)'s matrix is the
  congruence transform F @ Bmat @ F^T -- independently cross-checked against
  a Python ga_algebra reference engine's `outermorphism` (same congruence
  formula) on both physically-generated and random (F,B) pairs. Used by
  `H-field` to apply hbar (as an outermorphism) to the curl bivector."
  [F-standard b]
  (matrix->bivector (congruence F-standard (bivector->matrix b))))

(defn H-field
  "H(e_mu), mu=0..3, LDG eq (4.49) first form: H(a) = hbar(grad ^ hbar^-1(a)),
  for a position-gauge FIELD `h-field` (x -> 4x4 matrix, STORED convention,
  SAME shape `derived-metric-field`'s `h-field` argument), at spacetime point
  `x`. Returns a 4-element vector of 6-component bivectors,
  [H(e_0) H(e_1) H(e_2) H(e_3)].

  For each fixed frame vector a=e_mu (a is held CONSTANT, i.e. NOT itself
  position-dependent -- only hbar^-1 is differentiated): `grad ^ hbar^-1(a)`
  is the curl (antisymmetrized gradient) of the VECTOR FIELD x -> hbar^-1(a)
  at x, computed here via `kotoba.sm.vector-field/four-gradient-vec`
  (`vf/*h*` bound to `fd-h` for the duration of this call -- the INNER
  derivative level, see this section's header comment); hbar^-1(a) at a
  point xx is `(tensor/mat-vec (tensor/mat-inverse (tensor/mat-transpose
  (frame-adjoint (h-field xx)))) a)` (the STANDARD-convention matrix inverse
  of hbar, applied to a). The curl, C[alpha][beta] = eta_alpha
  d_alpha(hbar^-1(a))^beta - eta_beta d_beta(hbar^-1(a))^alpha, is exactly
  `grad^V` for a vector field V written out in components (`grad` = the
  Dirac/vector derivative gamma^mu d_mu = sum_mu eta_mu gamma_mu d_mu) --
  independently cross-checked against a Python ga_algebra reference engine's
  symbolic-derivative version of the SAME curl on the Schwarzschild solution.
  Then hbar is applied to that curl bivector via `outermorphism`, using hbar
  EVALUATED AT x (not differentiated, the OUTER hbar application in eq
  4.49 is NOT part of the derivative)."
  ([h-field x] (H-field h-field x default-fd-h))
  ([h-field x fd-h]
   (let [hbar-x (frame-adjoint (h-field x))
         M-hbar-x (tensor/mat-transpose hbar-x)] ;; standard conv: M-hbar-x @ a = hbar(a)
     (vec
      (for [mu (range 4)]
        (let [a (standard-basis-vector mu)
              hbar-inv-of-a (fn [xx]
                               (let [hbar-xx (frame-adjoint (h-field xx))
                                     M-hbar-xx (tensor/mat-transpose hbar-xx)
                                     M-hbar-inv (tensor/mat-inverse M-hbar-xx)]
                                 (tensor/mat-vec M-hbar-inv a)))
              J (binding [vf/*h* fd-h] (vf/four-gradient-vec hbar-inv-of-a x))
              ;; J[alpha][beta] = d (hbar^-1 a)^beta / dx^alpha
              C (vec (for [alpha (range 4)]
                       (vec (for [beta (range 4)]
                              (- (* (eta alpha alpha) (get-in J [alpha beta]))
                                 (* (eta beta beta) (get-in J [beta alpha])))))))]
          (matrix->bivector (congruence M-hbar-x C))))))))

(defn omega-from-h
  "The VACUUM, SPIN-FREE closed-form solution of the rotation-gauge field
  equation, LDG eq (4.53): omega(a) = -H(a) + (1/2) a.(d_b^H(b)). For a
  position-gauge FIELD `h-field` (SAME shape `H-field`/`derived-metric-field`
  take), at spacetime point `x`, returns Omega_mu(x) = omega(e_mu) for
  mu=0..3 as a 4x6 array -- the SAME shape `rotation-field-strength` already
  consumes as its `Omega` argument, and `rotation-gauge-field-gradient`/
  `rotation-field-strength` already consume as an `Omega-field`'s per-point
  value.

  DERIVATION of the closed form actually implemented below (a.(d_b^H(b)) is
  a vector-dot-trivector contraction LDG's own GA notation leaves implicit;
  this codebase deliberately does NOT introduce a trivector representation
  -- see this section's header comment -- so the closed form is rewritten,
  via the standard GA identity a.(u^B) = (a.u)B - u^(a.B) for vector a,u and
  bivector B (independently numerically cross-checked against a Python
  ga_algebra reference engine's `idot`/`wedge` on random bivectors before
  being trusted), applied term-by-term to d_b^H(b) = sum_nu eta_nu
  e_nu^H(e_nu):

    a.(d_b^H(b)) = sum_nu eta_nu [ (a.e_nu)H(e_nu) - e_nu^(a.H(e_nu)) ]

  For a=e_mu, (a.e_nu) = eta_mu delta_{mu,nu}, so the first term's sum
  collapses to the single nu=mu term, eta_mu*eta_mu*H(e_mu) = H(e_mu)
  (eta_mu^2=1). Substituting back into (4.53) and simplifying (both
  independently re-derived by hand AND numerically verified end-to-end
  against the SAME Python ga_algebra reference engine's direct trivector
  computation, to floating-point-exact agreement on random test bivectors,
  before being trusted here):

    omega(e_mu) = -(1/2)H(e_mu) - (1/2) sum_nu eta_nu (e_nu ^ (e_mu.H(e_nu)))

  `e_mu.H(e_nu)` is `vector-dot-bivector`; `e_nu ^ (...)` is `wedge-vectors`.
  `fd-h` is the finite-difference step passed straight through to `H-field`
  (the ONLY differentiation this function itself performs is inside
  `H-field` -- `omega-from-h` itself has no additional derivative)."
  ([h-field x] (omega-from-h h-field x default-fd-h))
  ([h-field x fd-h]
   (let [Hs (H-field h-field x fd-h)]
     (vec
      (for [mu (range 4)]
        (let [e-mu (standard-basis-vector mu)
              H-mu (nth Hs mu)
              correction (reduce
                          (fn [acc nu]
                            (let [e-nu (standard-basis-vector nu)
                                  v-dot-B (vector-dot-bivector e-mu (nth Hs nu))
                                  w (wedge-vectors e-nu v-dot-B)]
                              (tensor/v+ acc (tensor/v-scale (eta nu nu) w))))
                          (vec (repeat 6 0.0))
                          (range 4))]
          (tensor/v+ (tensor/v-scale -0.5 H-mu) (tensor/v-scale -0.5 correction))))))))

(defn L-a-omega
  "L_{e_a-idx} omega(e_nu) for all nu=0..3, LDG eq (4.42): L_a := a.hbar(grad)
  -- via the identity a.hbar(grad) = h(a).grad (h = `frame-adjoint` of hbar,
  independently confirmed against a standalone Python/numpy reference
  computation before being trusted -- see `frame-adjoint`'s own docstring),
  i.e. L_a is the ordinary DIRECTIONAL DERIVATIVE of the omega FIELD
  (`omega-from-h`) along the vector h(e_a-idx)(x) = row `a-idx` of
  `h-field`(x).

  *** DELIBERATELY NOT Phase 0a's flat d_mu: *** this is a GENUINELY
  DIFFERENT differential operator from `rotation-gauge-field-gradient`'s
  ordinary partial derivative along the FIXED coordinate axis e_mu -- L_a
  differentiates along the (position-dependent, curved) vector FIELD h(a)(x)
  instead. Reusing Phase 0a's flat-d_mu-based `rotation-field-strength`
  machinery here (i.e. solving the field equation with the ROTATION-gauge-
  only-covariant D_mu = d_mu + Omega_mu x of eq 3.26 in place of the
  POSITION-gauge-covariant calligraphic-D of eq 3.72-3.78 this phase
  actually needs) was independently tried and diagnosed as the exact
  silent-failure mode this namespace's Phase 1 work deliberately avoids: it
  constructs a Weitzenbock/teleparallel connection that is a pure gauge
  transform of the flat connection, whose curvature is IDENTICALLY ZERO by
  construction for ANY h -- not a sign/convention slip, a structurally wrong
  equation (documented in the standalone verification script this phase's
  formulas were cross-checked against, not re-derived from scratch here).

  `d-omega[rho][nu][k]` = d Omega_nu^k / dx^rho, via
  `kotoba.sm.gauge/gauge-field-gradient` applied to the FIELD
  x -> (omega-from-h h-field x fd-h-inner) -- the OUTER derivative level
  (`fd-h-outer`, see this section's header comment). Returns a 4x6 array,
  row nu = L_{e_a-idx} omega(e_nu)."
  ([h-field x a-idx] (L-a-omega h-field x a-idx default-fd-h default-fd-h))
  ([h-field x a-idx fd-h-inner fd-h-outer]
   (let [Omega-fn (fn [xx] (omega-from-h h-field xx fd-h-inner))
         d-omega (gauge/gauge-field-gradient Omega-fn x fd-h-outer)
         direction (nth (h-field x) a-idx)]
     (vec
      (for [nu (range 4)]
        (reduce (fn [acc rho]
                  (tensor/v+ acc (tensor/v-scale (nth direction rho) (get-in d-omega [rho nu]))))
                (vec (repeat 6 0.0))
                (range 4)))))))

(defn riemann-basis-pair
  "R(e_mu ^ e_nu), the COVARIANT Riemann map, LDG eq (4.48):

    R(a^b) = L_a omega(b) - L_b omega(a) + omega(a) x omega(b) - omega(c(a,b))
    c(a,b) = a.omega(b) - b.omega(a)                                   (4.46)

  for a GENERAL invertible position-gauge FIELD `h-field`, at spacetime point
  `x`, with a=e_mu, b=e_nu FIXED (position-INDEPENDENT) frame vectors -- eq
  (4.46)'s c(a,b) formula is valid exactly in this case (LDG's own note that
  L_a b = L_b a = 0 for a,b treated as independent of position, i.e. NOT
  vector FIELDS being differentiated themselves). `mu`,`nu` range over ALL of
  0..3 (not restricted to mu<nu): R(e_nu^e_mu) = -R(e_mu^e_nu) and
  R(e_mu^e_mu) = 0 hold AUTOMATICALLY as an algebraic consequence of (4.48)'s
  own antisymmetry in a,b (swap a<->b: the L-term negates and swaps, the
  commutator negates by antisymmetry, and omega(c(b,a)) = omega(-c(a,b)) =
  -omega(c(a,b)) since c(b,a)=-c(a,b) and omega is LINEAR -- so the whole
  RHS negates) -- NOT separately enforced/special-cased below.

  `omega(a)xomega(b)` is `bivector-commutator` (using
  `rotation-raw-structure-constants`); `a.omega(b)` is `vector-dot-bivector`;
  `omega(c(a,b))`, since omega is LINEAR in its argument, is
  `sum_rho c(a,b)^rho * omega(e_rho)` (a linear combination of the ALREADY-
  computed omega field values at x, not a fresh `omega-from-h` call on a
  non-basis vector).

  Independently numerically cross-checked (both this closed-form derivation
  and its finite-difference-based Clojure translation) against LDG's own
  Schwarzschild solution (eq 6.73) via a standalone Python/numpy verification
  script BEFORE this Clojure port was written -- see gtg_test.cljc for the
  same check ported to this codebase."
  ([h-field x mu nu] (riemann-basis-pair h-field x mu nu default-fd-h default-fd-h))
  ([h-field x mu nu fd-h-inner fd-h-outer]
   (let [f-abc (rotation-raw-structure-constants)
         omega-x (omega-from-h h-field x fd-h-inner)
         om-mu (nth omega-x mu)
         om-nu (nth omega-x nu)
         La-omega-b (nth (L-a-omega h-field x mu fd-h-inner fd-h-outer) nu)
         Lb-omega-a (nth (L-a-omega h-field x nu fd-h-inner fd-h-outer) mu)
         comm (bivector-commutator f-abc om-mu om-nu)
         e-mu (standard-basis-vector mu)
         e-nu (standard-basis-vector nu)
         c-vec (tensor/v- (vector-dot-bivector e-mu om-nu) (vector-dot-bivector e-nu om-mu))
         omega-c (reduce (fn [acc rho]
                            (tensor/v+ acc (tensor/v-scale (nth c-vec rho) (nth omega-x rho))))
                          (vec (repeat 6 0.0))
                          (range 4))]
     (tensor/v- (tensor/v+ (tensor/v- La-omega-b Lb-omega-a) comm) omega-c))))

(defn riemann-map-matrix
  "The covariant Riemann map R: bivectors -> bivectors (LDG eq 4.48) as a 6x6
  real matrix, at spacetime point `x` for position-gauge FIELD `h-field` --
  column k = R(`generator-index-pairs`[k]) (`riemann-basis-pair` on each of
  the 6 canonical basis-bivector pairs). R is LINEAR on the 6-dimensional
  bivector space (eq 4.48 is bilinear in its vector-argument slots a,b when
  those are basis vectors, and {e_mu^e_nu} spans the whole bivector space),
  so a linear map is fully determined by its action on that basis -- hence
  `(tensor/mat-vec (riemann-map-matrix h-field x) B)` gives R(B) for ANY
  6-component bivector B, not only a basis pair (see `riemann-map` below)."
  ([h-field x] (riemann-map-matrix h-field x default-fd-h default-fd-h))
  ([h-field x fd-h-inner fd-h-outer]
   (tensor/mat-transpose
    (vec (for [[mu nu] generator-index-pairs]
           (riemann-basis-pair h-field x mu nu fd-h-inner fd-h-outer))))))

(defn riemann-map
  "R(B), the covariant Riemann map (LDG eq 4.48) applied to a GENERAL
  6-component bivector B (not necessarily a basis pair -- e.g. one built via
  `wedge-vectors` from two arbitrary, possibly position-dependent vectors,
  the case `curvature-scalar` below needs) -- `(tensor/mat-vec
  (riemann-map-matrix h-field x fd-h-inner fd-h-outer) B)`."
  ([h-field x B] (riemann-map h-field x B default-fd-h default-fd-h))
  ([h-field x B fd-h-inner fd-h-outer]
   (tensor/mat-vec (riemann-map-matrix h-field x fd-h-inner fd-h-outer) B)))

(defn curvature-scalar
  "The TRUE Lasenby-Doran-Gull Ricci SCALAR, LDG eq (4.11)-(4.12):

    Ricci(b) = sum_a gamma^a . R(e_a ^ b)                              (4.11)
    R = sum_b gamma^b . Ricci(b) = sum_{a,b} gamma^a.(gamma^b.R(e_a^e_b))  (4.12)

  *** CONFIRMED, UNRESOLVED BUG for h-fields with Hdot!=0 -- see this
  namespace's PHASE 1 SCOPE NOTE (top of namespace docstring) for the full
  writeup. Summary: returns exactly 7x the correct value for a genuine
  matter-dominated FRW dust solution (Hdot!=0); only verified correct for
  Schwarzschild (static) and de Sitter (Hdot=0 identically). DO NOT trust
  this function for any h-field whose expansion/Hubble-like rate itself
  changes with time until this is resolved. ***

  *** BUG FIX (found by independent adversarial review, see git history/PR
  description): *** an earlier version of this function computed
  'gamma^a.(gamma^b.R(h_b^h_a))' -- contracting the ALREADY-COVARIANT Riemann
  map `riemann-map`/`riemann-basis-pair` (eq 4.48, which internally uses
  L_a=a.hbar(grad), i.e. is already built FROM h) against a bivector
  `wedge-vectors`(h_b,h_a) built from POSITION-GAUGE-FIELD ROWS instead of the
  FIXED frame basis vectors e_a,e_b. Since `riemann-basis-pair`(a,b) computes
  the LDG-covariant R(e_a^e_b) -- LDG's own eq (4.9), R(B)=R(h(B)) for a FLAT
  R and BASIS bivector B, shows the h-dependence is already baked into HOW
  `riemann-basis-pair` computes its answer, not into WHICH bivector argument
  it is fed -- wedging h_b^h_a on top applied h a SECOND time (this codebase's
  `riemann-basis-pair` corresponds to LDG's calligraphic, already-covariant
  'script-R', which both eq (4.11) and the independent second source, Lewis/
  Doran/Lasenby gr-qc/9910039 eq (12)/(14), contract with FLAT frame vectors
  only, never with h(e_a)/h(e_b)). The bug was NOT caught by this namespace's
  Schwarzschild regression test because that test only checks the SCALAR
  (trace); the erroneous double-h ONLY affects terms whose free index is 0 (in
  LDG's own Schwarzschild solution h(e_1)=e_1, h(e_2)=e_2, h(e_3)=e_3 exactly,
  so double-applying h is a no-op on purely-spatial index pairs), and those
  erroneous ~1e-4-magnitude off-diagonal Ricci-TENSOR terms happen to cancel
  in the trace for this particular solution -- independently confirmed by
  computing the FULL Ricci tensor (not just its trace) both ways: the buggy
  formula gives an ASYMMETRIC tensor (e.g. R_10~1.9e-4 vs R_01~9e-11) while
  this fixed formula gives a properly symmetric, uniformly-~0 (FD-noise-level)
  tensor, as GR's vacuum condition requires (R_ab=0 for ALL a,b, not merely
  its trace).

  Correct formula (this implementation): gamma^a, gamma^b = `tensor/raise` of
  the FIXED background orthonormal basis vectors e_a,e_b (BOTH literature
  sources agree this uses the fixed frame's OWN reciprocal, NOT a reciprocal
  frame OF h -- i.e. NOT `reciprocal-frame`/`reciprocal-frame-minkowski`, a
  DIFFERENT construction `reciprocal-frame`'s own docstring already found does
  NOT belong here). No `wedge-vectors`/general `riemann-map` call needed,
  since both indices here are always fixed basis vectors, never
  position-gauge-field rows -- `riemann-basis-pair` DIRECTLY.

  ARGUMENT-ORDER (SIGN CONVENTION), NOW NUMERICALLY CONFIRMED: the code below
  calls `riemann-basis-pair` h-field x b a (b first, a second), matching which
  gamma contracts FIRST (gamma-b, the inner `vector-dot-bivector` call)
  against which slot of eq (4.11)'s R(e_a^b) -- re-derived by hand from
  (4.11)/(4.12)'s structure (Ricci(free-index) = sum_{summed-index}
  gamma^{summed}.R(e_{summed}^e_{free}), the summed index occupying R's FIRST
  slot). Because `riemann-basis-pair` is antisymmetric (R(a^b)=-R(b^a)),
  swapping this argument order flips the SIGN of the returned scalar, and
  LDG's Schwarzschild solution (R=0 identically) cannot empirically
  distinguish this choice from its negative on its own -- so this order was
  independently checked a SECOND way, against a NONZERO worked example:
  LDG 1998 section 6.6 'Cosmology' (PDF pages 72-78, read as page IMAGES, not
  `pdftotext`), Table 6's homogeneous perfect-fluid-plus-Lambda solution and
  its closed-form covariant curvature, eq (6.169). Contracting LDG's own field
  equation (4.36), G(a)-Lambda*a=kappa*T(a), with the SAME frame trace
  identity this function uses (sum_a gamma^a.e_a=4) gives, independently of
  any implementation choice, R_expected = -8*pi*(rho-3*p) - 4*Lambda for a
  perfect fluid T(a)=(rho+p)(a.e_t)e_t-p*a. Built eq (6.169)'s R(B) as an
  explicit bivector-map and ran it through the SAME contraction this function
  performs (both argument orders) at 4 independent (rho,p,Lambda) points
  (general fluid+Lambda, pure dust, pure de Sitter, p=-rho): riemann-basis-pair
  h-field x b a (a first, a second) MATCHED R_expected in all 4 cases; the
  flipped order matched its negation in all 4 -- e.g. rho=0.7,p=0,Lambda=0 ->
  R_expected=-17.592919 matched the (b,a) order exactly, not the (a,b) order.
  Independently re-derived R_expected=-8*pi*(rho-3*p)-4*Lambda by hand from
  eq (4.36) and confirmed all 4 reported values arithmetically before trusting
  this conclusion. Further corroborated by matching index-order notation
  (summed index first) in two other independent primary sources: Lewis/Doran/
  Lasenby gr-qc/9910039 eq (14) (R_a=gamma^b.R_ba, R=gamma^a.R_a) and Francis/
  Kosowsky gr-qc/0311007 eq (2.26)/(2.29). This upgrades the sign convention
  from 'algebraically re-derived only' (as an earlier version of this
  docstring said) to numerically confirmed against a non-trivial published
  closed-form solution. This confirmation was originally done in a
  standalone scratch script (Python, reusing the `ga_algebra.py` reference
  engine already used to validate the Schwarzschild pipeline) that hand-built
  eq (6.169)'s Riemann OPERATOR in isolation and fed it through the SAME
  outer double-contraction this function performs -- it did NOT run this
  namespace's actual h-field -> `omega-from-h` -> `riemann-basis-pair` ->
  `curvature-scalar` finite-difference PIPELINE end to end (Schwarzschild is
  the only case that exercises the real pipeline, and Schwarzschild has R=0
  identically, so it cannot itself confirm a sign). THIS GAP IS NOW CLOSED:
  gtg_test.cljc's `curvature-scalar-matches-minus-4-lambda-for-pure-de-
  sitter-cosmology` ports the k=0 (spatially flat), rho=p=0, Lambda>0 special
  case of Table 6 (a PURE DE SITTER solution -- T_ab=0, so it is a genuine
  instance of this function's already-documented VACUUM scope, not an
  extension beyond it) into a native h-field and runs it through the REAL
  pipeline, confirming R=-4*Lambda at 3 independent (spatial point, Lambda)
  combinations to finite-difference precision (see that deftest's own
  docstring for the closed-form re-derivation and the Euclidean-vs-Minkowski
  'a.e_r' convention confirmation, independently re-verified from PDF page
  images, same discipline as `schwarzschild-hbar`'s own convention note). A
  genuine nonzero-DENSITY extension (T_ab != 0, e.g. dust) was investigated
  but declined -- see that same test file section's header comment for the
  specific, honestly-reported reason (an unresolved vector.bivector
  contraction-order question in eq (6.169)'s (rho+p) term, which is
  identically zero and therefore moot for the pure-de-Sitter case landed
  here) -- so matter-coupled cosmology remains unverified and out of scope.

  VERIFIED (gtg_test.cljc): 0.0, within finite-difference-truncation
  tolerance, for LDG's own Schwarzschild vacuum solution (eq 6.79) at
  multiple test points/mass parameters, AND (the strengthened check this fix
  adds) the FULL Ricci TENSOR (not just its trace) is uniformly ~0 at those
  same points, at the FD-noise floor (~1e-10, matching this pipeline's
  documented FD tolerance elsewhere) -- the properly vacuum-consistent result
  the buggy version's scalar-only check could not distinguish from the true
  answer (the buggy version's spurious ~1e-4 asymmetric components were
  ~2000x above this noise floor, not explainable as truncation error).
  ALSO VERIFIED: -4*Lambda, within finite-difference-truncation tolerance,
  for LDG's own pure-de-Sitter cosmological solution (Table 6/eq 6.169 at
  rho=p=0) at 3 independent (spatial point, Lambda) combinations -- the
  first NONZERO curvature-scalar value this namespace's pipeline has been
  checked against end to end (Schwarzschild's R=0 cannot itself confirm a
  sign or a nonzero magnitude). EXACTLY 0.0 (not merely close) at the flat
  limit h=`position-gauge-identity`, where every derivative this pipeline
  computes vanishes identically rather
  than merely numerically.

  This is the first curvature-SCALAR result this namespace's Phase 0a
  through Phase 1 history reaches -- Phase 0c's `curvature-quadratic-
  invariant` is a QUADRATIC, differently-scoped invariant (its own docstring
  has the distinction), and Phase 0d stage 2 / Phase 0e's own stage-2
  investigation each independently declined to implement this exact formula
  for the same, now-resolved, reason. Reached here only because `riemann-map`
  removed that specific blocker, not by relaxing this namespace's
  verification discipline (Schwarzschild-solution AND de-Sitter-cosmology
  regression tests, not a bare assertion, back this function -- see
  gtg_test.cljc)."
  ([h-field x] (curvature-scalar h-field x default-fd-h default-fd-h))
  ([h-field x fd-h-inner fd-h-outer]
   (reduce +
           (for [a (range 4) b (range 4)]
             (let [gamma-a (tensor/raise (standard-basis-vector a))
                   gamma-b (tensor/raise (standard-basis-vector b))
                   R-ba (riemann-basis-pair h-field x b a fd-h-inner fd-h-outer)
                   inner (vector-dot-bivector gamma-b R-ba)]
                 (tensor/dot gamma-a inner))))))

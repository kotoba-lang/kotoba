//! # Capability policy (`compile_safe_clj` phase S0)
//!
//! A [`Policy`] is the *deny-by-default* capability grant a safe-clj module is
//! compiled against. It is the language-side half of kotoba's
//! capability-confinement design (see `docs/ADR-safe-capability-language.md`).
//!
//! ## Why this is the whole ballgame
//!
//! The legacy [`crate::compile_str`] path is **ambient-authority**: every host
//! call a program *writes* (`kqe-assert!`, `llm-infer`, …) silently grows a
//! wasm import wired to the `kotoba:kais` world, and the runtime binds the lot.
//! A program that can name a capability has it.
//!
//! [`crate::compile_safe_clj`] inverts that. It collects the host imports a
//! program actually uses ([`crate::codegen::used_host_imports`]) and **refuses
//! to emit the module** unless every one of them is granted by the policy.
//! Because the emitted module's import section is therefore a subset of the
//! granted capabilities, the runtime — which can only bind imports the module
//! *declares* — can never wire ambient authority for that module. Confinement
//! is enforced at compile time and realised in the bytes, not checked at run
//! time.
//!
//! ```
//! use kotoba_clj::{compile_safe_clj, policy::Policy};
//!
//! // deny-all policy: a program that touches the graph will not compile.
//! let policy = Policy::deny_all();
//! let denied = compile_safe_clj("(defn run [g] (kqe-assert! g \"s\" \"p\" g))", &policy);
//! assert!(denied.is_err());
//!
//! // grant graph-write to one graph cid: now it compiles.
//! let policy = Policy::deny_all().grant_graph_write(["bafyGraphA"]);
//! let ok = compile_safe_clj("(defn run [g] (kqe-assert! g \"s\" \"p\" g))", &policy);
//! assert!(ok.is_ok());
//! ```

use std::collections::BTreeSet;

use kotoba_edn::EdnValue;

use crate::ast::HostImport;
use crate::CljError;

/// The capability *class* a host import requires. Deny-by-default: a class is
/// only reachable if the policy grants it. Each class maps 1:1 to a
/// `:imports` key in the policy EDN.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CapClass {
    /// Read a graph: `kqe.get-objects` / `kqe.query`. Granted by `:graph-read`.
    GraphRead,
    /// Mutate a graph: `kqe.assert-quad` / `kqe.retract-quad`. Granted by
    /// `:graph-write`. Deliberately split from [`CapClass::GraphRead`] —
    /// read-only code never gains write authority.
    GraphWrite,
    /// Run model inference: `llm.infer`. Granted by `:infer`.
    Infer,
    /// Introspect the caller's own CACAO: `auth.has-capability`. Granted by
    /// `:auth`.
    Auth,
}

impl CapClass {
    /// The capability class a host import belongs to.
    pub fn of(imp: HostImport) -> CapClass {
        match imp {
            HostImport::KqeGetObjects | HostImport::KqeQuery => CapClass::GraphRead,
            HostImport::KqeAssertQuad | HostImport::KqeRetractQuad => CapClass::GraphWrite,
            HostImport::LlmInfer => CapClass::Infer,
            HostImport::HasCapability => CapClass::Auth,
        }
    }

    /// The `:imports` EDN keyword that grants this class.
    pub fn policy_key(self) -> &'static str {
        match self {
            CapClass::GraphRead => "graph-read",
            CapClass::GraphWrite => "graph-write",
            CapClass::Infer => "infer",
            CapClass::Auth => "auth",
        }
    }
}

/// Resource quotas a safe module must declare. There is no permissive default:
/// [`crate::compile_safe_clj`] rejects a policy whose `fuel` or `memory_pages`
/// is zero, mirroring the runtime's `gas_limit = 0` ban — gasless/quota-less
/// execution is forbidden by construction.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Limits {
    /// Max linear-memory pages (64 KiB each).
    pub memory_pages: u32,
    /// Fuel / gas ceiling. Wired to the runtime's gas accounting by the caller.
    pub fuel: u64,
    /// Max call depth (recursion bound).
    pub max_call_depth: u32,
    /// Max bytes a module may return.
    pub max_output_bytes: u32,
}

impl Limits {
    /// Conservative non-zero defaults used when a policy omits a limit field.
    /// `memory_pages`/`fuel` still must be positive or compilation is rejected,
    /// so these defaults only fill the *optional* fields.
    pub fn defaults() -> Limits {
        Limits {
            memory_pages: 4,
            fuel: 1_000_000,
            max_call_depth: 128,
            max_output_bytes: 65_536,
        }
    }
}

/// A deny-by-default capability grant + resource quota a safe-clj module is
/// compiled against.
///
/// Allowlists (`graph_read`, `graph_write`, `infer`, `egress`, `secrets`) carry
/// the concrete cids/endpoints a future phase (S4) will statically bind call
/// sites against. In phase **S0** a class counts as *granted* iff its allowlist
/// is non-empty (or the relevant boolean is set); the per-cid match of a
/// string-literal argument against the allowlist is deferred to S4.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Policy {
    /// Graph cids the module may read.
    pub graph_read: BTreeSet<String>,
    /// Graph cids the module may mutate.
    pub graph_write: BTreeSet<String>,
    /// Model cids the module may run inference against.
    pub infer: BTreeSet<String>,
    /// Whether the module may introspect its own CACAO (`has-capability?`).
    pub auth: bool,
    /// Whether the module may observe wall-clock (timing-channel surface).
    /// Reserved — no host import maps to it yet.
    pub clock: bool,
    /// Whether the module may draw non-determinism. Reserved.
    pub random: bool,
    /// HTTP egress allowlist. Reserved — no host import maps to it yet.
    pub egress: BTreeSet<String>,
    /// Secret references the module may read. Reserved.
    pub secrets: BTreeSet<String>,
    /// Resource quotas.
    pub limits: Limits,
}

impl Policy {
    /// The empty, fully-confined policy: no capability, default quotas. A
    /// program compiled against this must be pure (no host imports) or it will
    /// be rejected.
    pub fn deny_all() -> Policy {
        Policy {
            graph_read: BTreeSet::new(),
            graph_write: BTreeSet::new(),
            infer: BTreeSet::new(),
            auth: false,
            clock: false,
            random: false,
            egress: BTreeSet::new(),
            secrets: BTreeSet::new(),
            limits: Limits::defaults(),
        }
    }

    /// Builder: grant read access to the given graph cids.
    pub fn grant_graph_read<I, S>(mut self, cids: I) -> Policy
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.graph_read.extend(cids.into_iter().map(Into::into));
        self
    }

    /// Builder: grant write access to the given graph cids.
    pub fn grant_graph_write<I, S>(mut self, cids: I) -> Policy
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.graph_write.extend(cids.into_iter().map(Into::into));
        self
    }

    /// Builder: grant inference against the given model cids.
    pub fn grant_infer<I, S>(mut self, cids: I) -> Policy
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.infer.extend(cids.into_iter().map(Into::into));
        self
    }

    /// Builder: allow CACAO self-introspection (`has-capability?`).
    pub fn grant_auth(mut self) -> Policy {
        self.auth = true;
        self
    }

    /// Builder: override the resource quotas.
    pub fn with_limits(mut self, limits: Limits) -> Policy {
        self.limits = limits;
        self
    }

    /// Whether a capability class is granted at all (phase-S0 granularity).
    pub fn class_granted(&self, class: CapClass) -> bool {
        match class {
            CapClass::GraphRead => !self.graph_read.is_empty(),
            CapClass::GraphWrite => !self.graph_write.is_empty(),
            CapClass::Infer => !self.infer.is_empty(),
            CapClass::Auth => self.auth,
        }
    }

    /// Check a single host import against the policy. `Err` carries a
    /// human-readable denial reason naming the import and the missing grant.
    pub fn permits(&self, imp: HostImport) -> Result<(), String> {
        let class = CapClass::of(imp);
        if self.class_granted(class) {
            return Ok(());
        }
        let (module, field) = imp.module_field();
        Err(format!(
            "host import `{module}/{field}` needs capability `:{}`, which the \
             policy does not grant (deny-by-default). Add `:{} [...]` to the \
             policy `:imports` to authorize it.",
            class.policy_key(),
            class.policy_key()
        ))
    }

    /// Per-cid (instance-level) check of resource-targeting host calls (phase S4).
    ///
    /// A host call whose first argument is a **string literal** resource id must
    /// name a resource the policy grants:
    /// - `(kqe-assert! <g> …)` / `(kqe-retract! <g> …)` → `:graph-write`
    /// - `(kqe-get-objects <g> …)` → `:graph-read`
    /// - `(llm-infer <model> …)` → `:infer`
    ///
    /// A `"*"` entry in an allowlist means "any resource of this class" (the
    /// phase-S0 class-level behaviour). A non-literal (dynamic) argument cannot
    /// be checked statically and falls back to the class-level
    /// [`Policy::permits`] gate.
    ///
    /// This tightens **T3** from class granularity ("may write *some* graph",
    /// "may run *some* model") to instance granularity ("may write *only* graph
    /// X", "may run *only* model M") — the compile-time twin of CACAO's
    /// `leaf.graph ⊆ root.graph` attenuation.
    pub fn check_resource_targets(&self, forms: &[EdnValue]) -> Result<(), CljError> {
        for f in forms {
            self.check_value_targets(f)?;
        }
        Ok(())
    }

    /// The (`:imports` key, allowlist) a resource-targeting builtin scopes its
    /// first string-literal argument against.
    fn resource_target_of(&self, name: &str) -> Option<(&'static str, &BTreeSet<String>)> {
        match name {
            "kqe-assert!" | "kqe-retract!" => Some(("graph-write", &self.graph_write)),
            "kqe-get-objects" => Some(("graph-read", &self.graph_read)),
            "llm-infer" => Some(("infer", &self.infer)),
            _ => None,
        }
    }

    fn check_value_targets(&self, v: &EdnValue) -> Result<(), CljError> {
        match v {
            EdnValue::List(items) => {
                if let Some(EdnValue::Symbol(head)) = items.first() {
                    // Inert forms (quote/var/comment) are never executed — no
                    // resource access; don't gate their contents.
                    if crate::ast::is_inert_form(&head.name) {
                        return Ok(());
                    }
                    if let Some((key, allow)) = self.resource_target_of(&head.name) {
                        if let Some(EdnValue::String(cid)) = items.get(1) {
                            if !(allow.contains("*") || allow.contains(cid)) {
                                return Err(CljError::Policy(format!(
                                    "`{cid}` is not in the policy's `:{key}` allowlist — this \
                                     capability is scoped per resource (T3 instance-level). \
                                     Grant `:{key} [\"{cid}\"]` (or `\"*\"` for any) to \
                                     authorize it."
                                )));
                            }
                        }
                    }
                }
                for it in items {
                    self.check_value_targets(it)?;
                }
            }
            EdnValue::Vector(items) => {
                for it in items {
                    self.check_value_targets(it)?;
                }
            }
            EdnValue::Set(items) => {
                for it in items {
                    self.check_value_targets(it)?;
                }
            }
            EdnValue::Map(m) => {
                for (k, val) in m {
                    self.check_value_targets(k)?;
                    self.check_value_targets(val)?;
                }
            }
            EdnValue::Tagged { value, .. } => self.check_value_targets(value)?,
            _ => {}
        }
        Ok(())
    }

    /// Validate the resource quotas. Rejects a quota-less policy.
    pub fn validate_limits(&self) -> Result<(), CljError> {
        if self.limits.fuel == 0 {
            return Err(CljError::Policy(
                "policy `:limits :fuel` must be > 0 — gasless execution is forbidden".into(),
            ));
        }
        if self.limits.memory_pages == 0 {
            return Err(CljError::Policy(
                "policy `:limits :memory-pages` must be > 0 — a module needs a bounded heap".into(),
            ));
        }
        // wasm32 linear memory tops out at 2^16 pages (4 GiB); a larger cap
        // would emit an invalid module that fails to instantiate.
        const WASM32_MAX_PAGES: u32 = 65_536;
        if self.limits.memory_pages > WASM32_MAX_PAGES {
            return Err(CljError::Policy(format!(
                "policy `:limits :memory-pages` = {} exceeds the wasm32 maximum of \
                 {WASM32_MAX_PAGES} pages (4 GiB)",
                self.limits.memory_pages
            )));
        }
        Ok(())
    }

    /// Serialize this policy back to EDN (the `policy.edn` form). Round-trips
    /// with [`Policy::parse_edn`] for the gated fields. Reserved fields (egress,
    /// secrets, clock, random) are emitted too so the artifact is complete.
    pub fn to_edn(&self) -> String {
        let strs = |s: &BTreeSet<String>| {
            EdnValue::vector(s.iter().map(|x| EdnValue::string(x.clone())))
        };
        let imports = EdnValue::map([
            (EdnValue::kw_bare("graph-read"), strs(&self.graph_read)),
            (EdnValue::kw_bare("graph-write"), strs(&self.graph_write)),
            (EdnValue::kw_bare("infer"), strs(&self.infer)),
            (EdnValue::kw_bare("auth"), EdnValue::bool(self.auth)),
            (EdnValue::kw_bare("egress"), strs(&self.egress)),
            (EdnValue::kw_bare("secrets"), strs(&self.secrets)),
            (EdnValue::kw_bare("clock"), EdnValue::bool(self.clock)),
            (EdnValue::kw_bare("random"), EdnValue::bool(self.random)),
        ]);
        let limits = EdnValue::map([
            (
                EdnValue::kw_bare("memory-pages"),
                EdnValue::int(self.limits.memory_pages as i64),
            ),
            (
                EdnValue::kw_bare("fuel"),
                EdnValue::int(self.limits.fuel as i64),
            ),
            (
                EdnValue::kw_bare("max-call-depth"),
                EdnValue::int(self.limits.max_call_depth as i64),
            ),
            (
                EdnValue::kw_bare("max-output-bytes"),
                EdnValue::int(self.limits.max_output_bytes as i64),
            ),
        ]);
        let top = EdnValue::map([
            (EdnValue::kw_bare("imports"), imports),
            (EdnValue::kw_bare("limits"), limits),
        ]);
        kotoba_edn::to_string_pretty(&top)
    }

    /// Parse a policy from EDN text (the on-disk `policy.edn` form). See the ADR
    /// §4 for the schema.
    pub fn parse_edn(src: &str) -> Result<Policy, CljError> {
        let forms = kotoba_edn::parse_all(src)
            .map_err(|e| CljError::Policy(format!("policy EDN parse error: {e}")))?;
        let top = forms
            .first()
            .ok_or_else(|| CljError::Policy("empty policy".into()))?;
        let map = top
            .as_map()
            .ok_or_else(|| CljError::Policy("policy must be an EDN map".into()))?;

        let mut policy = Policy::deny_all();

        if let Some(imports) = map.get(&EdnValue::kw_bare("imports")) {
            let imports = imports
                .as_map()
                .ok_or_else(|| CljError::Policy("`:imports` must be a map".into()))?;
            if let Some(v) = imports.get(&EdnValue::kw_bare("graph-read")) {
                policy.graph_read = str_set(v, ":imports :graph-read")?;
            }
            if let Some(v) = imports.get(&EdnValue::kw_bare("graph-write")) {
                policy.graph_write = str_set(v, ":imports :graph-write")?;
            }
            if let Some(v) = imports.get(&EdnValue::kw_bare("infer")) {
                policy.infer = str_set(v, ":imports :infer")?;
            }
            if let Some(v) = imports.get(&EdnValue::kw_bare("egress")) {
                policy.egress = str_set(v, ":imports :egress")?;
            }
            if let Some(v) = imports.get(&EdnValue::kw_bare("secrets")) {
                policy.secrets = str_set(v, ":imports :secrets")?;
            }
            if let Some(v) = imports.get(&EdnValue::kw_bare("auth")) {
                policy.auth = v
                    .as_bool()
                    .ok_or_else(|| CljError::Policy("`:imports :auth` must be a boolean".into()))?;
            }
            if let Some(v) = imports.get(&EdnValue::kw_bare("clock")) {
                policy.clock = v.as_bool().ok_or_else(|| {
                    CljError::Policy("`:imports :clock` must be a boolean".into())
                })?;
            }
            if let Some(v) = imports.get(&EdnValue::kw_bare("random")) {
                policy.random = v.as_bool().ok_or_else(|| {
                    CljError::Policy("`:imports :random` must be a boolean".into())
                })?;
            }
        }

        if let Some(limits) = map.get(&EdnValue::kw_bare("limits")) {
            let limits = limits
                .as_map()
                .ok_or_else(|| CljError::Policy("`:limits` must be a map".into()))?;
            let mut l = Limits::defaults();
            if let Some(v) = limits.get(&EdnValue::kw_bare("memory-pages")) {
                l.memory_pages = u32_field(v, ":limits :memory-pages")?;
            }
            if let Some(v) = limits.get(&EdnValue::kw_bare("fuel")) {
                l.fuel = u64_field(v, ":limits :fuel")?;
            }
            if let Some(v) = limits.get(&EdnValue::kw_bare("max-call-depth")) {
                l.max_call_depth = u32_field(v, ":limits :max-call-depth")?;
            }
            if let Some(v) = limits.get(&EdnValue::kw_bare("max-output-bytes")) {
                l.max_output_bytes = u32_field(v, ":limits :max-output-bytes")?;
            }
            policy.limits = l;
        }

        Ok(policy)
    }
}

/// Report this policy's **over-grants** relative to a cell: capabilities it
/// grants that the cell (`forms`) never targets. The least-privilege linter —
/// the complement of [`infer_minimal`]. Each finding is a human-readable string
/// naming the excess grant.
///
/// Conservative (no false "unused" claims): if the cell targets a class
/// *dynamically* (a non-literal resource id), no specific cid in that class is
/// reported — any of them might be needed at run time. A `"*"` grant is treated
/// as intentionally broad and never flagged. An empty result means the policy
/// is already least-privilege for this cell.
impl Policy {
    pub fn unused_grants(&self, forms: &[EdnValue]) -> Vec<String> {
        let needed = infer_minimal(forms);
        let mut out = Vec::new();
        diff_class(&mut out, "graph-write", &self.graph_write, &needed.graph_write);
        diff_class(&mut out, "graph-read", &self.graph_read, &needed.graph_read);
        diff_class(&mut out, "infer", &self.infer, &needed.infer);
        if self.auth && !needed.auth {
            out.push("auth: granted but `has-capability?` is never used".to_string());
        }
        out
    }
}

/// Append findings for one resource class: an entirely-unused class, or
/// specific granted cids the cell never targets.
fn diff_class(out: &mut Vec<String>, key: &str, granted: &BTreeSet<String>, needed: &BTreeSet<String>) {
    if granted.is_empty() {
        return; // nothing granted → cannot over-grant
    }
    if needed.is_empty() {
        out.push(format!("{key}: entire capability granted but the cell never uses it"));
        return;
    }
    // Dynamic need (`"*"`) → any cid might be required at run time; don't flag.
    // A wildcard *grant* is deliberately broad → don't flag.
    if needed.contains("*") || granted.contains("*") {
        return;
    }
    for cid in granted {
        if !needed.contains(cid) {
            out.push(format!("{key}: `{cid}` granted but never targeted by the cell"));
        }
    }
}

/// Synthesize the **minimal** (least-privilege) policy that lets `forms`
/// compile under safe-clj: it grants exactly the resources the code targets and
/// nothing more.
///
/// - a literal resource id (`(kqe-assert! "graphA" …)`, `(llm-infer "modelA"
///   …)`) becomes a specific allowlist entry;
/// - a *dynamic* target for a class (`(kqe-assert! g …)`, or a graph-scope-free
///   call like `kqe-query`) widens that class to `"*"` — the least we can
///   statically prove sufficient;
/// - pure code yields [`Policy::deny_all`].
///
/// Invariant: `compile_safe_clj(src, &infer_minimal(parse(src)))` succeeds — the
/// synthesized policy is sufficient by construction — while removing any grant
/// makes it fail. This is least-privilege policy generation: point it at an
/// untrusted cell to see (and pin) exactly what it needs.
pub fn infer_minimal(forms: &[EdnValue]) -> Policy {
    let mut acc = MinAcc::default();
    for f in forms {
        collect_min(f, &mut acc);
    }
    let resolve = |dynamic: bool, cids: BTreeSet<String>| -> BTreeSet<String> {
        if dynamic {
            BTreeSet::from(["*".to_string()])
        } else {
            cids
        }
    };
    let mut p = Policy::deny_all();
    p.graph_write = resolve(acc.write_dynamic, acc.write);
    p.graph_read = resolve(acc.read_dynamic, acc.read);
    p.infer = resolve(acc.infer_dynamic, acc.infer);
    p.auth = acc.auth;
    p
}

/// Accumulator for [`infer_minimal`]: per-class literal ids + a "saw a dynamic
/// target" flag (which forces `"*"`).
#[derive(Default)]
struct MinAcc {
    write: BTreeSet<String>,
    write_dynamic: bool,
    read: BTreeSet<String>,
    read_dynamic: bool,
    infer: BTreeSet<String>,
    infer_dynamic: bool,
    auth: bool,
}

fn collect_min(v: &EdnValue, acc: &mut MinAcc) {
    match v {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                // Inert forms (quote/var/comment) are never executed → no
                // capability.
                if crate::ast::is_inert_form(&head.name) {
                    return;
                }
                let literal = match items.get(1) {
                    Some(EdnValue::String(s)) => Some(s.clone()),
                    _ => None,
                };
                match head.name.as_str() {
                    "kqe-assert!" | "kqe-retract!" => match literal {
                        Some(s) => {
                            acc.write.insert(s);
                        }
                        None => acc.write_dynamic = true,
                    },
                    "kqe-get-objects" => match literal {
                        Some(s) => {
                            acc.read.insert(s);
                        }
                        None => acc.read_dynamic = true,
                    },
                    // `kqe-query` reads but names no specific graph → needs the
                    // graph-read class with no pinnable cid.
                    "kqe-query" => acc.read_dynamic = true,
                    "llm-infer" => match literal {
                        Some(s) => {
                            acc.infer.insert(s);
                        }
                        None => acc.infer_dynamic = true,
                    },
                    "has-capability?" => acc.auth = true,
                    _ => {}
                }
            }
            for it in items {
                collect_min(it, acc);
            }
        }
        EdnValue::Vector(items) => {
            for it in items {
                collect_min(it, acc);
            }
        }
        EdnValue::Set(items) => {
            for it in items {
                collect_min(it, acc);
            }
        }
        EdnValue::Map(m) => {
            for (k, val) in m {
                collect_min(k, acc);
                collect_min(val, acc);
            }
        }
        EdnValue::Tagged { value, .. } => collect_min(value, acc),
        _ => {}
    }
}

/// Parse an EDN vector/list/set of strings into a [`BTreeSet`].
fn str_set(v: &EdnValue, ctx: &str) -> Result<BTreeSet<String>, CljError> {
    let items = v
        .as_vector()
        .or_else(|| v.as_list())
        .or_else(|| v.as_seq())
        .ok_or_else(|| CljError::Policy(format!("`{ctx}` must be a vector of strings")))?;
    items
        .iter()
        .map(|e| {
            e.as_string()
                .map(str::to_string)
                .ok_or_else(|| CljError::Policy(format!("`{ctx}` entries must be strings")))
        })
        .collect()
}

fn u64_field(v: &EdnValue, ctx: &str) -> Result<u64, CljError> {
    let i = v
        .as_integer()
        .ok_or_else(|| CljError::Policy(format!("`{ctx}` must be an integer")))?;
    u64::try_from(i).map_err(|_| CljError::Policy(format!("`{ctx}` must be non-negative")))
}

fn u32_field(v: &EdnValue, ctx: &str) -> Result<u32, CljError> {
    let i = v
        .as_integer()
        .ok_or_else(|| CljError::Policy(format!("`{ctx}` must be an integer")))?;
    u32::try_from(i).map_err(|_| CljError::Policy(format!("`{ctx}` out of u32 range")))
}

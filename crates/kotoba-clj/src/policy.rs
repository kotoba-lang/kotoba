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
        Ok(())
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
                policy.auth = v.as_bool().ok_or_else(|| {
                    CljError::Policy("`:imports :auth` must be a boolean".into())
                })?;
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

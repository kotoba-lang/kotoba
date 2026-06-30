//! # Capability policy (`compile_safe_kotoba` phase S0)
//!
//! A [`Policy`] is the *deny-by-default* capability grant a safe Kotoba module is
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
//! [`crate::compile_safe_kotoba`] inverts that. It collects the host imports a
//! program actually uses ([`crate::codegen::used_host_imports`]) and **refuses
//! to emit the module** unless every one of them is granted by the policy.
//! Because the emitted module's import section is therefore a subset of the
//! granted capabilities, the runtime — which can only bind imports the module
//! *declares* — can never wire ambient authority for that module. Confinement
//! is enforced at compile time and realised in the bytes, not checked at run
//! time.
//!
//! ```
//! use kotoba_clj::{compile_safe_kotoba, policy::Policy};
//!
//! // deny-all policy: a program that touches the graph will not compile.
//! let policy = Policy::deny_all();
//! let denied = compile_safe_kotoba("(defn run [g] (kqe-assert! g \"s\" \"p\" g))", &policy);
//! assert!(denied.is_err());
//!
//! // grant graph-write to one graph cid: now it compiles.
//! let policy = Policy::deny_all().grant_graph_write(["bafyGraphA"]);
//! let ok = compile_safe_kotoba("(defn run [g] (kqe-assert! g \"s\" \"p\" g))", &policy);
//! assert!(ok.is_ok());
//! ```

use std::collections::{BTreeSet, HashMap, HashSet};

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
/// [`crate::compile_safe_kotoba`] rejects a policy whose `fuel` or `memory_pages`
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

/// A deny-by-default capability grant + resource quota a safe Kotoba module is
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
        // S4b (1-level interprocedural): a literal cid passed to a user function
        // that uses *that parameter* directly as a host-call resource target is
        // checked against the same allowlist — per-cid confinement flows through
        // one call layer, not just direct host calls. Conservative (single-arity
        // defns, unshadowed direct param use, literal call arguments only), so a
        // legitimate call whose cid *is* granted is never flagged.
        let param_targets = collect_cid_param_targets(forms);
        if !param_targets.is_empty() {
            for f in forms {
                self.check_param_cid_calls(f, &param_targets)?;
            }
        }
        Ok(())
    }

    /// The (`:imports` key, allowlist) a resource-targeting builtin scopes its
    /// first string-literal argument against.
    fn resource_target_of(&self, name: &str) -> Option<(&'static str, &BTreeSet<String>)> {
        resource_target_key(name).map(|key| (key, self.allowlist_for(key)))
    }

    /// The allowlist for a capability-class key.
    fn allowlist_for(&self, key: &str) -> &BTreeSet<String> {
        match key {
            "graph-write" => &self.graph_write,
            "graph-read" => &self.graph_read,
            "infer" => &self.infer,
            _ => unreachable!("unknown resource-target key {key}"),
        }
    }

    /// Check each `(fname <literal-cid> …)` call whose callee uses parameter
    /// `param_idx` as a resource target: the cid must be in that class's
    /// allowlist (the per-cid rule, one call layer deep).
    fn check_param_cid_calls(
        &self,
        v: &EdnValue,
        targets: &HashMap<String, Vec<(usize, &'static str)>>,
    ) -> Result<(), CljError> {
        if let EdnValue::List(items) = v {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                if crate::ast::is_inert_form(&head.name) {
                    return Ok(());
                }
                if let Some(positions) = targets.get(&head.name) {
                    let args = &items[1..];
                    for &(idx, key) in positions {
                        if let Some(EdnValue::String(cid)) = args.get(idx) {
                            let allow = self.allowlist_for(key);
                            if !(allow.contains("*") || allow.contains(cid)) {
                                return Err(CljError::Policy(format!(
                                    "`{cid}` is not in the policy's `:{key}` allowlist — it is \
                                     passed to `{}` which uses it as a {key} resource target \
                                     (T3 instance-level, through a call). Grant `:{key} \
                                     [\"{cid}\"]` (or `\"*\"`) to authorize it.",
                                    head.name
                                )));
                            }
                        }
                    }
                }
            }
            for it in items {
                self.check_param_cid_calls(it, targets)?;
            }
        }
        Ok(())
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
        let strs =
            |s: &BTreeSet<String>| EdnValue::vector(s.iter().map(|x| EdnValue::string(x.clone())));
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

fn resource_target_key(name: &str) -> Option<&'static str> {
    match name.rsplit('/').next().unwrap_or(name) {
        "kqe-assert!" | "kqe-retract!" => Some("graph-write"),
        "kqe-get-objects" => Some("graph-read"),
        "llm-infer" => Some("infer"),
        _ => None,
    }
}

fn collect_cid_param_targets(forms: &[EdnValue]) -> HashMap<String, Vec<(usize, &'static str)>> {
    let mut out = HashMap::new();
    for form in forms {
        collect_defn_cid_param_targets(form, &mut out);
    }
    out
}

fn collect_defn_cid_param_targets(
    form: &EdnValue,
    out: &mut HashMap<String, Vec<(usize, &'static str)>>,
) {
    let EdnValue::List(items) = form else {
        return;
    };
    if !matches!(
        items.first(),
        Some(EdnValue::Symbol(sym)) if sym.name == "defn"
    ) {
        return;
    }
    let Some(EdnValue::Symbol(name)) = items.get(1) else {
        return;
    };
    let mut params_idx = 2;
    if matches!(items.get(params_idx), Some(EdnValue::String(_))) {
        params_idx += 1;
    }
    if matches!(items.get(params_idx), Some(EdnValue::Map(_))) {
        params_idx += 1;
    }
    let Some(EdnValue::Vector(params)) = items.get(params_idx) else {
        return;
    };
    let mut params = params
        .iter()
        .enumerate()
        .filter_map(|(idx, value)| match value {
            EdnValue::Symbol(sym) => Some((sym.name.as_str(), idx)),
            _ => None,
        })
        .collect::<HashMap<_, _>>();
    if params.is_empty() {
        return;
    }

    let body_idx = if matches!(items.get(params_idx + 1), Some(EdnValue::Map(_))) {
        params_idx + 2
    } else {
        params_idx + 1
    };
    // Shadow-safe: a parameter rebound by a `let`/`loop`/`fn` in the body no
    // longer names the caller's argument where that binding is in scope, so it
    // must not be treated as flowing to a host-call target — else a caller
    // passing an unrelated cid would be mis-flagged (false positive). Dropping a
    // shadowed parameter just falls back to the class-level capability gate (the
    // pre-feature baseline), so it never weakens confinement below that.
    let mut shadowed = HashSet::new();
    for body in &items[body_idx..] {
        collect_bound_names_edn(body, &mut shadowed);
    }
    params.retain(|param, _| !shadowed.contains(*param));
    if params.is_empty() {
        return;
    }
    let mut seen = HashSet::new();
    for body in &items[body_idx..] {
        collect_value_cid_param_targets(body, &params, &mut seen);
    }
    if !seen.is_empty() {
        let mut seen = seen.into_iter().collect::<Vec<_>>();
        seen.sort();
        out.insert(name.name.clone(), seen);
    }
}

fn collect_value_cid_param_targets(
    value: &EdnValue,
    params: &HashMap<&str, usize>,
    out: &mut HashSet<(usize, &'static str)>,
) {
    match value {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                if crate::ast::is_inert_form(&head.name) {
                    return;
                }
                if let Some(key) = resource_target_key(&head.name) {
                    if let Some(EdnValue::Symbol(arg)) = items.get(1) {
                        if let Some(idx) = params.get(arg.name.as_str()) {
                            out.insert((*idx, key));
                        }
                    }
                }
            }
            for item in items {
                collect_value_cid_param_targets(item, params, out);
            }
        }
        EdnValue::Vector(items) => {
            for item in items {
                collect_value_cid_param_targets(item, params, out);
            }
        }
        EdnValue::Set(items) => {
            for item in items {
                collect_value_cid_param_targets(item, params, out);
            }
        }
        EdnValue::Map(map) => {
            for (key, value) in map {
                collect_value_cid_param_targets(key, params, out);
                collect_value_cid_param_targets(value, params, out);
            }
        }
        EdnValue::Tagged { value, .. } => collect_value_cid_param_targets(value, params, out),
        _ => {}
    }
}

/// Names introduced anywhere in `v` by a `let`/`loop`/`if-let`/`when-let`
/// binding vector or an `fn` parameter list — i.e. names that, where they are in
/// scope, shadow an enclosing parameter of the same spelling.
fn collect_bound_names_edn<'a>(v: &'a EdnValue, out: &mut HashSet<&'a str>) {
    if let EdnValue::List(items) = v {
        if let Some(EdnValue::Symbol(head)) = items.first() {
            match head.name.as_str() {
                "let" | "loop" | "if-let" | "when-let" => {
                    if let Some(EdnValue::Vector(binds)) = items.get(1) {
                        // Binding names are at even positions: [name val name val …].
                        let mut k = 0;
                        while k < binds.len() {
                            if let EdnValue::Symbol(sym) = &binds[k] {
                                out.insert(sym.name.as_str());
                            }
                            k += 2;
                        }
                    }
                }
                "fn" => {
                    for item in items.iter().skip(1) {
                        if let EdnValue::Vector(ps) = item {
                            for p in ps {
                                if let EdnValue::Symbol(sym) = p {
                                    out.insert(sym.name.as_str());
                                }
                            }
                            break;
                        }
                    }
                }
                _ => {}
            }
        }
    }
    match v {
        EdnValue::List(items) | EdnValue::Vector(items) => {
            for item in items {
                collect_bound_names_edn(item, out);
            }
        }
        EdnValue::Set(items) => {
            for item in items {
                collect_bound_names_edn(item, out);
            }
        }
        EdnValue::Map(map) => {
            for (k, val) in map {
                collect_bound_names_edn(k, out);
                collect_bound_names_edn(val, out);
            }
        }
        EdnValue::Tagged { value, .. } => collect_bound_names_edn(value, out),
        _ => {}
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
        diff_class(
            &mut out,
            "graph-write",
            &self.graph_write,
            &needed.graph_write,
        );
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
fn diff_class(
    out: &mut Vec<String>,
    key: &str,
    granted: &BTreeSet<String>,
    needed: &BTreeSet<String>,
) {
    if granted.is_empty() {
        return; // nothing granted → cannot over-grant
    }
    if needed.is_empty() {
        out.push(format!(
            "{key}: entire capability granted but the cell never uses it"
        ));
        return;
    }
    // Dynamic need (`"*"`) → any cid might be required at run time; don't flag.
    // A wildcard *grant* is deliberately broad → don't flag.
    if needed.contains("*") || granted.contains("*") {
        return;
    }
    for cid in granted {
        if !needed.contains(cid) {
            out.push(format!(
                "{key}: `{cid}` granted but never targeted by the cell"
            ));
        }
    }
}

/// Synthesize the **minimal** (least-privilege) policy that lets `forms`
/// compile under safe Kotoba: it grants exactly the resources the code targets and
/// nothing more.
///
/// - a literal resource id (`(kqe-assert! "graphA" …)`, `(llm-infer "modelA"
///   …)`) becomes a specific allowlist entry;
/// - a *dynamic* target for a class (`(kqe-assert! g …)`, or a graph-scope-free
///   call like `kqe-query`) widens that class to `"*"` — the least we can
///   statically prove sufficient;
/// - pure code yields [`Policy::deny_all`].
///
/// Invariant: `compile_safe_kotoba(src, &infer_minimal(parse(src)))` succeeds — the
/// synthesized policy is sufficient by construction — while removing any grant
/// makes it fail. This is least-privilege policy generation: point it at an
/// untrusted cell to see (and pin) exactly what it needs.
pub fn infer_minimal(forms: &[EdnValue]) -> Policy {
    let mut acc = MinAcc::default();
    let param_targets = collect_cid_param_targets(forms);
    let param_target_names = collect_cid_param_target_names(forms);
    for f in forms {
        collect_min(f, None, &param_target_names, &mut acc);
    }
    if !param_targets.is_empty() {
        collect_param_call_min(forms, &param_targets, &mut acc);
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

impl MinAcc {
    fn add_resource_target(&mut self, key: &str, literal: Option<&str>) {
        match (key, literal) {
            ("graph-write", Some(s)) => {
                self.write.insert(s.to_string());
            }
            ("graph-write", None) => self.write_dynamic = true,
            ("graph-read", Some(s)) => {
                self.read.insert(s.to_string());
            }
            ("graph-read", None) => self.read_dynamic = true,
            ("infer", Some(s)) => {
                self.infer.insert(s.to_string());
            }
            ("infer", None) => self.infer_dynamic = true,
            _ => {}
        }
    }
}

fn collect_min(
    v: &EdnValue,
    current_fn: Option<&str>,
    param_targets: &HashMap<String, Vec<(String, &'static str)>>,
    acc: &mut MinAcc,
) {
    match v {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                // Inert forms (quote/var/comment) are never executed → no
                // capability.
                if crate::ast::is_inert_form(&head.name) {
                    return;
                }
                let literal = match items.get(1) {
                    Some(EdnValue::String(s)) => Some(s.as_str()),
                    _ => None,
                };
                if head.name == "defn" {
                    if let Some(EdnValue::Symbol(name)) = items.get(1) {
                        for it in items.iter().skip(2) {
                            collect_min(it, Some(name.name.as_str()), param_targets, acc);
                        }
                        return;
                    }
                }
                match head.name.as_str() {
                    "kqe-assert!" | "kqe-retract!" => {
                        if !is_param_resource_target_use(
                            items,
                            current_fn,
                            param_targets,
                            "graph-write",
                        ) {
                            acc.add_resource_target("graph-write", literal);
                        }
                    }
                    "kqe-get-objects" => {
                        if !is_param_resource_target_use(
                            items,
                            current_fn,
                            param_targets,
                            "graph-read",
                        ) {
                            acc.add_resource_target("graph-read", literal);
                        }
                    }
                    // `kqe-query` reads but names no specific graph → needs the
                    // graph-read class with no pinnable cid.
                    "kqe-query" => acc.read_dynamic = true,
                    "llm-infer" => {
                        if !is_param_resource_target_use(items, current_fn, param_targets, "infer")
                        {
                            acc.add_resource_target("infer", literal);
                        }
                    }
                    "has-capability?" => acc.auth = true,
                    _ => {}
                }
            }
            for it in items {
                collect_min(it, current_fn, param_targets, acc);
            }
        }
        EdnValue::Vector(items) => {
            for it in items {
                collect_min(it, current_fn, param_targets, acc);
            }
        }
        EdnValue::Set(items) => {
            for it in items {
                collect_min(it, current_fn, param_targets, acc);
            }
        }
        EdnValue::Map(m) => {
            for (k, val) in m {
                collect_min(k, current_fn, param_targets, acc);
                collect_min(val, current_fn, param_targets, acc);
            }
        }
        EdnValue::Tagged { value, .. } => collect_min(value, current_fn, param_targets, acc),
        _ => {}
    }
}

fn is_param_resource_target_use(
    items: &[EdnValue],
    current_fn: Option<&str>,
    param_targets: &HashMap<String, Vec<(String, &'static str)>>,
    key: &'static str,
) -> bool {
    let Some(current_fn) = current_fn else {
        return false;
    };
    let Some(EdnValue::Symbol(arg)) = items.get(1) else {
        return false;
    };
    let Some(positions) = param_targets.get(current_fn) else {
        return false;
    };
    positions
        .iter()
        .any(|(name, target_key)| *target_key == key && name == &arg.name)
}

fn collect_param_call_min(
    forms: &[EdnValue],
    targets: &HashMap<String, Vec<(usize, &'static str)>>,
    acc: &mut MinAcc,
) {
    let mut seen_calls = HashSet::new();
    for f in forms {
        collect_param_call_min_value(f, targets, acc, &mut seen_calls);
    }
    for (callee, positions) in targets {
        for &(_, key) in positions {
            if !seen_calls.contains(&(callee.as_str(), key)) {
                acc.add_resource_target(key, None);
            }
        }
    }
}

fn collect_param_call_min_value<'a>(
    v: &'a EdnValue,
    targets: &'a HashMap<String, Vec<(usize, &'static str)>>,
    acc: &mut MinAcc,
    seen_calls: &mut HashSet<(&'a str, &'static str)>,
) {
    match v {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                if crate::ast::is_inert_form(&head.name) {
                    return;
                }
                if let Some(positions) = targets.get(&head.name) {
                    let args = &items[1..];
                    for &(idx, key) in positions {
                        seen_calls.insert((head.name.as_str(), key));
                        match args.get(idx) {
                            Some(EdnValue::String(cid)) => acc.add_resource_target(key, Some(cid)),
                            _ => acc.add_resource_target(key, None),
                        }
                    }
                }
            }
            for it in items {
                collect_param_call_min_value(it, targets, acc, seen_calls);
            }
        }
        EdnValue::Vector(items) => {
            for it in items {
                collect_param_call_min_value(it, targets, acc, seen_calls);
            }
        }
        EdnValue::Set(items) => {
            for it in items {
                collect_param_call_min_value(it, targets, acc, seen_calls);
            }
        }
        EdnValue::Map(m) => {
            for (k, val) in m {
                collect_param_call_min_value(k, targets, acc, seen_calls);
                collect_param_call_min_value(val, targets, acc, seen_calls);
            }
        }
        EdnValue::Tagged { value, .. } => {
            collect_param_call_min_value(value, targets, acc, seen_calls)
        }
        _ => {}
    }
}

fn collect_cid_param_target_names(
    forms: &[EdnValue],
) -> HashMap<String, Vec<(String, &'static str)>> {
    let mut out = HashMap::new();
    for form in forms {
        collect_defn_cid_param_target_names(form, &mut out);
    }
    out
}

fn collect_defn_cid_param_target_names(
    form: &EdnValue,
    out: &mut HashMap<String, Vec<(String, &'static str)>>,
) {
    let EdnValue::List(items) = form else {
        return;
    };
    if !matches!(
        items.first(),
        Some(EdnValue::Symbol(sym)) if sym.name == "defn"
    ) {
        return;
    }
    let Some(EdnValue::Symbol(name)) = items.get(1) else {
        return;
    };
    let mut params_idx = 2;
    if matches!(items.get(params_idx), Some(EdnValue::String(_))) {
        params_idx += 1;
    }
    if matches!(items.get(params_idx), Some(EdnValue::Map(_))) {
        params_idx += 1;
    }
    let Some(EdnValue::Vector(params)) = items.get(params_idx) else {
        return;
    };
    let params = params
        .iter()
        .filter_map(|value| match value {
            EdnValue::Symbol(sym) => Some(sym.name.as_str()),
            _ => None,
        })
        .collect::<HashSet<_>>();
    if params.is_empty() {
        return;
    }

    let body_idx = if matches!(items.get(params_idx + 1), Some(EdnValue::Map(_))) {
        params_idx + 2
    } else {
        params_idx + 1
    };
    let mut seen = HashSet::new();
    for body in &items[body_idx..] {
        collect_value_cid_param_target_names(body, &params, &mut seen);
    }
    if !seen.is_empty() {
        let mut seen = seen
            .into_iter()
            .map(|(param, key)| (param.to_string(), key))
            .collect::<Vec<_>>();
        seen.sort();
        out.insert(name.name.clone(), seen);
    }
}

fn collect_value_cid_param_target_names<'a>(
    value: &'a EdnValue,
    params: &HashSet<&'a str>,
    out: &mut HashSet<(&'a str, &'static str)>,
) {
    match value {
        EdnValue::List(items) => {
            if let Some(EdnValue::Symbol(head)) = items.first() {
                if crate::ast::is_inert_form(&head.name) {
                    return;
                }
                if let Some(key) = resource_target_key(&head.name) {
                    if let Some(EdnValue::Symbol(arg)) = items.get(1) {
                        if params.contains(arg.name.as_str()) {
                            out.insert((arg.name.as_str(), key));
                        }
                    }
                }
            }
            for item in items {
                collect_value_cid_param_target_names(item, params, out);
            }
        }
        EdnValue::Vector(items) => {
            for item in items {
                collect_value_cid_param_target_names(item, params, out);
            }
        }
        EdnValue::Set(items) => {
            for item in items {
                collect_value_cid_param_target_names(item, params, out);
            }
        }
        EdnValue::Map(map) => {
            for (key, value) in map {
                collect_value_cid_param_target_names(key, params, out);
                collect_value_cid_param_target_names(value, params, out);
            }
        }
        EdnValue::Tagged { value, .. } => collect_value_cid_param_target_names(value, params, out),
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

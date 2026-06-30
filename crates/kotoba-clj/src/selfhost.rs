//! Bridge APIs for Kotoba self-hosted compiler-admission seeds.
//!
//! The functions in this module compile and run `selfhost/safe_analyzer.kotoba`
//! as a Wasm Component, then decode its CBOR output into ordinary Rust types.
//! This keeps Rust as the bootstrap substrate while letting callers exercise the
//! analyzer semantics implemented in Kotoba itself.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use ciborium::value::Value;

use crate::ast::{self, Builtin, Expr};
use crate::compat::{self, ReaderTarget};
use crate::component::{compile_component_str_with_prelude, run_component};
use crate::{codegen, subset, ty, ty_infer};
use crate::{CljError, Policy};

/// The self-hosted safe Kotoba analyzer source bundled with the crate.
pub const SAFE_ANALYZER: &str = include_str!("../selfhost/safe_analyzer.kotoba");

/// CBOR contract version emitted by `safe_analyzer.kotoba`.
pub const SAFE_ANALYZER_ABI: &str = "kotoba.selfhost.safe-analyzer.v1";

/// EDN contract seed for shell evidence/profile projection ownership.
pub const SHELL_EVIDENCE_PROFILE_SPEC: &str =
    include_str!("../selfhost/shell_evidence_profile.edn");

/// Executable Kotoba oracle for the shell evidence/profile projection seed.
pub const SHELL_EVIDENCE_PROFILE_ORACLE: &str =
    include_str!("../selfhost/shell_evidence_profile.kotoba");

/// Executable Kotoba oracle for shell provider/surface policy projection.
pub const PROVIDER_SURFACE_POLICY_ORACLE: &str =
    include_str!("../selfhost/provider_surface_policy.kotoba");

/// EDN source of truth for aiueos shell provider/catalog projection.
pub const AIUEOS_PROVIDER_CATALOG_SPEC: &str =
    include_str!("../selfhost/aiueos_provider_catalog.edn");

/// Executable Kotoba oracle for shipped safe app component manifest contracts.
pub const APP_COMPONENTS_CONTRACT_ORACLE: &str =
    include_str!("../selfhost/app_components_contract.kotoba");

/// Executable Kotoba oracle for shell plugin registry/SDK/loader contracts.
pub const PLUGIN_CONTRACT_ORACLE: &str = include_str!("../selfhost/plugin_contract.kotoba");

/// Executable Kotoba oracle for shell compatibility policy contracts.
pub const COMPATIBILITY_CONTRACT_ORACLE: &str =
    include_str!("../selfhost/compatibility_contract.kotoba");

/// Executable Kotoba oracle for shell updater manifest contracts.
pub const UPDATER_CONTRACT_ORACLE: &str = include_str!("../selfhost/updater_contract.kotoba");

/// Executable Kotoba oracle for shell updater channel policy contracts.
pub const UPDATER_CHANNEL_CONTRACT_ORACLE: &str =
    include_str!("../selfhost/updater_channel_contract.kotoba");

/// Executable Kotoba oracle for shell updater UI contracts.
pub const UPDATER_UI_CONTRACT_ORACLE: &str = include_str!("../selfhost/updater_ui_contract.kotoba");

/// Executable Kotoba oracle for shell updater bundle/install/publication contracts.
pub const UPDATER_LIFECYCLE_CONTRACT_ORACLE: &str =
    include_str!("../selfhost/updater_lifecycle_contract.kotoba");

/// Executable Kotoba oracle for shell signing readiness contracts.
pub const SIGNING_CONTRACT_ORACLE: &str = include_str!("../selfhost/signing_contract.kotoba");

/// Executable Kotoba oracle for shell submission readiness contracts.
pub const SUBMISSION_CONTRACT_ORACLE: &str = include_str!("../selfhost/submission_contract.kotoba");

/// Executable Kotoba oracle for shell release metadata readiness contracts.
pub const RELEASE_CONTRACT_ORACLE: &str = include_str!("../selfhost/release_contract.kotoba");

/// Executable Kotoba oracle for target-specific shell release readiness contracts.
pub const RELEASE_TARGET_CONTRACT_ORACLE: &str =
    include_str!("../selfhost/release_target_contract.kotoba");

/// Executable Kotoba oracle for shell runtime release/matrix readiness contracts.
pub const RUNTIME_CONTRACT_ORACLE: &str = include_str!("../selfhost/runtime_contract.kotoba");

/// Executable Kotoba oracle for shell SDK/project verification contracts.
pub const SDK_CONTRACT_ORACLE: &str = include_str!("../selfhost/sdk_contract.kotoba");

/// Executable Kotoba oracle for generated native host bridge dispatch contracts.
pub const NATIVE_HOST_CONTRACT_ORACLE: &str =
    include_str!("../selfhost/native_host_contract.kotoba");

/// Contract version for `shell_evidence_profile.edn`.
pub const SHELL_EVIDENCE_PROFILE_ABI: &str = "kotoba.selfhost.shell-evidence-profile.v0";

/// Transitive facts inferred for one function by the self-hosted analyzer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FunctionSummary {
    pub effects: BTreeSet<String>,
    pub caps: BTreeSet<String>,
    pub targets: BTreeSet<String>,
}

/// One effect-declaration violation reported by the self-hosted analyzer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EffectViolation {
    pub name: String,
    pub used: BTreeSet<String>,
    pub declared: BTreeSet<String>,
    pub missing: BTreeSet<String>,
    pub unknown: BTreeSet<String>,
}

/// Result of checking `{:effects ...}` declarations with the self-hosted analyzer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EffectCheck {
    pub ok: bool,
    pub violations: Vec<EffectViolation>,
}

/// Result of checking a [`Policy`] with the self-hosted analyzer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PolicyCheck {
    pub ok: bool,
    pub used: BTreeSet<String>,
    pub granted: BTreeSet<String>,
    pub denials: BTreeSet<String>,
    pub target_denials: BTreeSet<String>,
}

/// Combined self-hosted compile-admission result.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdmissionCheck {
    pub effects: EffectCheck,
    pub policy: PolicyCheck,
}

/// Combined self-hosted subset/type/effect/policy gate used by compile paths.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompileGateCheck {
    pub subset: SubsetCheck,
    pub types: TypeCheck,
    pub effects: EffectCheck,
    pub policy: PolicyCheck,
}

/// Result of checking the executable-body safe subset with the self-hosted
/// analyzer. Top-level forms that are not represented in parser-owned function
/// bodies are still checked by Rust's subset gate.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SubsetCheck {
    pub ok: bool,
    pub denials: BTreeSet<String>,
}

/// Result of checking the first self-hosted literal type slice. Rust's full
/// type gates remain authoritative for typed-HIR and value-dependent checks.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TypeCheck {
    pub ok: bool,
    pub denials: BTreeSet<String>,
}

/// A compiled self-hosted analyzer component that can be reused across multiple
/// admission calls.
#[derive(Debug, Clone)]
pub struct Analyzer {
    component: Vec<u8>,
}

impl Analyzer {
    /// Compile the bundled `safe_analyzer.kotoba` once.
    pub fn new() -> Result<Self, CljError> {
        Ok(Self {
            component: analyzer_component()?,
        })
    }

    /// Reuse previously compiled analyzer component bytes.
    pub fn from_component(component: Vec<u8>) -> Self {
        Self { component }
    }

    /// The compiled Wasm Component bytes for auditing or external caching.
    pub fn component(&self) -> &[u8] {
        &self.component
    }

    /// Run a pre-lowered analyzer request and return the decoded CBOR value.
    pub fn run_request_value(&self, request: &AnalyzerRequest) -> Result<Value, CljError> {
        let input = request.to_cbor()?;
        self.run_value(&input)
    }

    pub fn analyze_program_all(
        &self,
        src: &str,
    ) -> Result<BTreeMap<String, FunctionSummary>, CljError> {
        self.analyze_program_all_with_reader_target(src, ReaderTarget::Kotoba)
    }

    pub fn analyze_program_all_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
    ) -> Result<BTreeMap<String, FunctionSummary>, CljError> {
        let input = program_all_input(src, target)?;
        let value = self.run_value(&input)?;
        function_summaries(&value)
    }

    pub fn infer_effects(&self, src: &str) -> Result<BTreeMap<String, BTreeSet<String>>, CljError> {
        self.infer_effects_with_reader_target(src, ReaderTarget::Kotoba)
    }

    pub fn infer_effects_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
    ) -> Result<BTreeMap<String, BTreeSet<String>>, CljError> {
        Ok(self
            .analyze_program_all_with_reader_target(src, target)?
            .into_iter()
            .map(|(name, summary)| (name, summary.effects))
            .collect())
    }

    pub fn minimal_policy(&self, src: &str) -> Result<Policy, CljError> {
        self.minimal_policy_with_reader_target(src, ReaderTarget::Kotoba)
    }

    pub fn minimal_policy_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
    ) -> Result<Policy, CljError> {
        let input = program_minimal_policy_input(src, target)?;
        let value = self.run_value(&input)?;
        policy_from_value(&value)
    }

    pub fn minimal_policy_file(&self, path: impl AsRef<Path>) -> Result<Policy, CljError> {
        self.minimal_policy_file_with_reader_target(path, ReaderTarget::Kotoba)
    }

    pub fn minimal_policy_file_with_reader_target(
        &self,
        path: impl AsRef<Path>,
        target: ReaderTarget,
    ) -> Result<Policy, CljError> {
        self.minimal_policy_file_with_reader_target_and_source_paths(path, target, &[])
    }

    pub fn minimal_policy_file_with_reader_target_and_source_paths(
        &self,
        path: impl AsRef<Path>,
        target: ReaderTarget,
        source_paths: &[PathBuf],
    ) -> Result<Policy, CljError> {
        let src = compat::load_file_graph_with_source_paths(path.as_ref(), target, source_paths)?;
        self.minimal_policy_with_reader_target(&src, target)
    }

    pub fn check_effect_declarations(&self, src: &str) -> Result<EffectCheck, CljError> {
        self.check_effect_declarations_with_reader_target(src, ReaderTarget::Kotoba)
    }

    pub fn check_effect_declarations_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
    ) -> Result<EffectCheck, CljError> {
        let input = program_effect_check_input(src, target)?;
        let value = self.run_value(&input)?;
        effect_check_from_value(&value)
    }

    pub fn check_policy(&self, src: &str, policy: &Policy) -> Result<PolicyCheck, CljError> {
        self.check_policy_with_reader_target(src, ReaderTarget::Kotoba, policy)
    }

    pub fn check_policy_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<PolicyCheck, CljError> {
        let input = program_policy_check_input(src, target, policy)?;
        let value = self.run_value(&input)?;
        policy_check_from_value(&value)
    }

    pub fn check_admission(&self, src: &str, policy: &Policy) -> Result<AdmissionCheck, CljError> {
        self.check_admission_with_reader_target(src, ReaderTarget::Kotoba, policy)
    }

    pub fn check_admission_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<AdmissionCheck, CljError> {
        let input = program_admission_check_input(src, target, policy)?;
        let value = self.run_value(&input)?;
        admission_check_from_value(&value)
    }

    pub fn check_compile_gate(
        &self,
        src: &str,
        policy: &Policy,
    ) -> Result<CompileGateCheck, CljError> {
        self.check_compile_gate_with_reader_target(src, ReaderTarget::Kotoba, policy)
    }

    pub fn check_compile_gate_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<CompileGateCheck, CljError> {
        let input = program_compile_gate_input(src, target, policy)?;
        let value = self.run_value(&input)?;
        compile_gate_check_from_value(&value)
    }

    pub fn check_subset(&self, src: &str) -> Result<SubsetCheck, CljError> {
        self.check_subset_with_reader_target(src, ReaderTarget::Kotoba)
    }

    pub fn check_subset_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
    ) -> Result<SubsetCheck, CljError> {
        let input = program_subset_check_input(src, target)?;
        let value = self.run_value(&input)?;
        subset_check_from_value(&value)
    }

    pub fn check_types(&self, src: &str) -> Result<TypeCheck, CljError> {
        self.check_types_with_reader_target(src, ReaderTarget::Kotoba)
    }

    pub fn check_types_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
    ) -> Result<TypeCheck, CljError> {
        let input = program_type_check_input(src, target)?;
        let value = self.run_value(&input)?;
        type_check_from_value(&value)
    }

    pub fn unused_grants(&self, src: &str, policy: &Policy) -> Result<Vec<String>, CljError> {
        self.unused_grants_with_reader_target(src, ReaderTarget::Kotoba, policy)
    }

    pub fn unused_grants_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<String>, CljError> {
        Ok(self
            .unused_grant_ids_with_reader_target(src, target, policy)?
            .into_iter()
            .map(|grant| humanize_unused_grant(&grant))
            .collect())
    }

    pub fn unused_grant_ids(&self, src: &str, policy: &Policy) -> Result<Vec<String>, CljError> {
        self.unused_grant_ids_with_reader_target(src, ReaderTarget::Kotoba, policy)
    }

    pub fn unused_grant_ids_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<String>, CljError> {
        let input = program_unused_grants_input(src, target, policy)?;
        let value = self.run_value(&input)?;
        text_array_vec(&value, "unused")
    }

    pub fn compile_safe_kotoba(&self, src: &str, policy: &Policy) -> Result<Vec<u8>, CljError> {
        self.compile_safe_kotoba_with_reader_target(src, ReaderTarget::Kotoba, policy)
    }

    pub fn compile_safe_clj(&self, src: &str, policy: &Policy) -> Result<Vec<u8>, CljError> {
        self.compile_safe_kotoba(src, policy)
    }

    pub fn compile_safe_kotoba_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        compile_safe_clj_inner(self, src, target, policy, false)
    }

    pub fn compile_safe_clj_with_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_kotoba_with_reader_target(src, target, policy)
    }

    pub fn compile_safe_kotoba_with_prelude(
        &self,
        src: &str,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_kotoba_with_prelude_and_reader_target(src, ReaderTarget::Kotoba, policy)
    }

    pub fn compile_safe_clj_with_prelude(
        &self,
        src: &str,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_kotoba_with_prelude(src, policy)
    }

    pub fn compile_safe_kotoba_with_prelude_and_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        compile_safe_clj_inner(self, src, target, policy, true)
    }

    pub fn compile_safe_clj_with_prelude_and_reader_target(
        &self,
        src: &str,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_kotoba_with_prelude_and_reader_target(src, target, policy)
    }

    pub fn compile_safe_file(
        &self,
        path: impl AsRef<Path>,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_file_with_reader_target(path, ReaderTarget::Kotoba, policy)
    }

    pub fn compile_safe_file_with_reader_target(
        &self,
        path: impl AsRef<Path>,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_file_with_reader_target_and_source_paths(path, target, policy, &[])
    }

    pub fn compile_safe_file_with_reader_target_and_source_paths(
        &self,
        path: impl AsRef<Path>,
        target: ReaderTarget,
        policy: &Policy,
        source_paths: &[PathBuf],
    ) -> Result<Vec<u8>, CljError> {
        let src = compat::load_file_graph_with_source_paths(path.as_ref(), target, source_paths)?;
        self.compile_safe_kotoba_with_reader_target(&src, target, policy)
    }

    pub fn compile_safe_file_with_prelude(
        &self,
        path: impl AsRef<Path>,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_file_with_prelude_and_reader_target(path, ReaderTarget::Kotoba, policy)
    }

    pub fn compile_safe_file_with_prelude_and_reader_target(
        &self,
        path: impl AsRef<Path>,
        target: ReaderTarget,
        policy: &Policy,
    ) -> Result<Vec<u8>, CljError> {
        self.compile_safe_file_with_prelude_reader_target_and_source_paths(
            path,
            target,
            policy,
            &[],
        )
    }

    pub fn compile_safe_file_with_prelude_reader_target_and_source_paths(
        &self,
        path: impl AsRef<Path>,
        target: ReaderTarget,
        policy: &Policy,
        source_paths: &[PathBuf],
    ) -> Result<Vec<u8>, CljError> {
        let src = compat::load_file_graph_with_source_paths(path.as_ref(), target, source_paths)?;
        self.compile_safe_kotoba_with_prelude_and_reader_target(&src, target, policy)
    }

    fn run_value(&self, input: &[u8]) -> Result<Value, CljError> {
        let out = run_component(&self.component, input)?;
        let value: Value = ciborium::from_reader(out.as_slice())
            .map_err(|e| CljError::Run(format!("selfhost analyzer output CBOR: {e}")))?;
        require_abi(&value)?;
        require_no_analyzer_error(&value)?;
        Ok(value)
    }
}

/// Compile the bundled self-hosted analyzer to a `run(list<u8>) -> list<u8>`
/// Wasm Component.
pub fn analyzer_component() -> Result<Vec<u8>, CljError> {
    compile_component_str_with_prelude(SAFE_ANALYZER)
}

/// Compile the bundled shell evidence/profile oracle as a safe Kotoba Wasm module.
pub fn shell_evidence_profile_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(SHELL_EVIDENCE_PROFILE_ORACLE, &Policy::deny_all())
}

/// Compile the bundled provider/surface policy oracle as a safe Kotoba Wasm module.
pub fn provider_surface_policy_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(PROVIDER_SURFACE_POLICY_ORACLE, &Policy::deny_all())
}

/// Compile the bundled app-components contract oracle as a safe Kotoba Wasm module.
pub fn app_components_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(APP_COMPONENTS_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled plugin contract oracle as a safe Kotoba Wasm module.
pub fn plugin_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(PLUGIN_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled compatibility contract oracle as a safe Kotoba Wasm module.
pub fn compatibility_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(COMPATIBILITY_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled updater contract oracle as a safe Kotoba Wasm module.
pub fn updater_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(UPDATER_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled updater channel contract oracle as a safe Kotoba Wasm module.
pub fn updater_channel_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(UPDATER_CHANNEL_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled updater UI contract oracle as a safe Kotoba Wasm module.
pub fn updater_ui_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(UPDATER_UI_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled updater lifecycle contract oracle as a safe Kotoba Wasm module.
pub fn updater_lifecycle_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(UPDATER_LIFECYCLE_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled signing contract oracle as a safe Kotoba Wasm module.
pub fn signing_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(SIGNING_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled submission contract oracle as a safe Kotoba Wasm module.
pub fn submission_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(SUBMISSION_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled release contract oracle as a safe Kotoba Wasm module.
pub fn release_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(RELEASE_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled release target contract oracle as a safe Kotoba Wasm module.
pub fn release_target_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(RELEASE_TARGET_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled runtime contract oracle as a safe Kotoba Wasm module.
pub fn runtime_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(RUNTIME_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled SDK/project verification contract oracle as a safe Kotoba Wasm module.
pub fn sdk_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(SDK_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile the bundled native host bridge contract oracle as a safe Kotoba Wasm module.
pub fn native_host_contract_oracle_wasm() -> Result<Vec<u8>, CljError> {
    crate::compile_safe_kotoba_with_prelude(NATIVE_HOST_CONTRACT_ORACLE, &Policy::deny_all())
}

/// Compile safe Kotoba source using the self-hosted Kotoba analyzer.
///
/// Rust still owns reader normalization, subset/type checks, and Wasm emission;
/// the covered T2/T3 admission decisions come from the bundled self-hosted
/// analyzer component.
pub fn compile_safe_kotoba(src: &str, policy: &Policy) -> Result<Vec<u8>, CljError> {
    Analyzer::new()?.compile_safe_kotoba(src, policy)
}

/// Compatibility alias for [`compile_safe_kotoba`].
pub fn compile_safe_clj(src: &str, policy: &Policy) -> Result<Vec<u8>, CljError> {
    compile_safe_kotoba(src, policy)
}

/// Compile safe Kotoba source for a specific reader target using the analyzer.
pub fn compile_safe_kotoba_with_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    Analyzer::new()?.compile_safe_kotoba_with_reader_target(src, target, policy)
}

/// Compatibility alias for [`compile_safe_kotoba_with_reader_target`].
pub fn compile_safe_clj_with_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    compile_safe_kotoba_with_reader_target(src, target, policy)
}

/// Same as [`compile_safe_kotoba`], with the policy-aware safe prelude included.
pub fn compile_safe_kotoba_with_prelude(src: &str, policy: &Policy) -> Result<Vec<u8>, CljError> {
    Analyzer::new()?.compile_safe_kotoba_with_prelude(src, policy)
}

/// Compatibility alias for [`compile_safe_kotoba_with_prelude`].
pub fn compile_safe_clj_with_prelude(src: &str, policy: &Policy) -> Result<Vec<u8>, CljError> {
    compile_safe_kotoba_with_prelude(src, policy)
}

/// Same as [`compile_safe_kotoba_with_reader_target`], with the safe prelude.
pub fn compile_safe_kotoba_with_prelude_and_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    Analyzer::new()?.compile_safe_kotoba_with_prelude_and_reader_target(src, target, policy)
}

/// Compatibility alias for [`compile_safe_kotoba_with_prelude_and_reader_target`].
pub fn compile_safe_clj_with_prelude_and_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    compile_safe_kotoba_with_prelude_and_reader_target(src, target, policy)
}

/// Compile a `.kotoba` / `.clj` / `.cljc` / `.cljs` file using the self-hosted
/// analyzer for covered effect/capability admission.
pub fn compile_safe_file(path: impl AsRef<Path>, policy: &Policy) -> Result<Vec<u8>, CljError> {
    compile_safe_file_with_reader_target(path, ReaderTarget::Kotoba, policy)
}

/// Compile a source file with a specific reader conditional target.
pub fn compile_safe_file_with_reader_target(
    path: impl AsRef<Path>,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    compile_safe_file_with_reader_target_and_source_paths(path, target, policy, &[])
}

/// Compile a source file with reader target and source paths.
pub fn compile_safe_file_with_reader_target_and_source_paths(
    path: impl AsRef<Path>,
    target: ReaderTarget,
    policy: &Policy,
    source_paths: &[PathBuf],
) -> Result<Vec<u8>, CljError> {
    Analyzer::new()?.compile_safe_file_with_reader_target_and_source_paths(
        path,
        target,
        policy,
        source_paths,
    )
}

/// Compile a source file with the policy-aware prelude.
pub fn compile_safe_file_with_prelude(
    path: impl AsRef<Path>,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    compile_safe_file_with_prelude_and_reader_target(path, ReaderTarget::Kotoba, policy)
}

/// Compile a source file with prelude and reader target.
pub fn compile_safe_file_with_prelude_and_reader_target(
    path: impl AsRef<Path>,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    compile_safe_file_with_prelude_reader_target_and_source_paths(path, target, policy, &[])
}

/// Compile a source file with prelude, reader target, and source paths.
pub fn compile_safe_file_with_prelude_reader_target_and_source_paths(
    path: impl AsRef<Path>,
    target: ReaderTarget,
    policy: &Policy,
    source_paths: &[PathBuf],
) -> Result<Vec<u8>, CljError> {
    Analyzer::new()?.compile_safe_file_with_prelude_reader_target_and_source_paths(
        path,
        target,
        policy,
        source_paths,
    )
}

/// Infer transitive per-function summaries by running the Kotoba analyzer.
pub fn analyze_program_all(src: &str) -> Result<BTreeMap<String, FunctionSummary>, CljError> {
    Analyzer::new()?.analyze_program_all(src)
}

/// Infer transitive per-function summaries for a specific reader target.
pub fn analyze_program_all_with_reader_target(
    src: &str,
    target: ReaderTarget,
) -> Result<BTreeMap<String, FunctionSummary>, CljError> {
    Analyzer::new()?.analyze_program_all_with_reader_target(src, target)
}

/// Source-level effect inference backed by the Kotoba analyzer.
pub fn infer_effects(src: &str) -> Result<BTreeMap<String, BTreeSet<String>>, CljError> {
    Ok(analyze_program_all(src)?
        .into_iter()
        .map(|(name, summary)| (name, summary.effects))
        .collect())
}

/// Source-level effect inference for a specific reader target.
pub fn infer_effects_with_reader_target(
    src: &str,
    target: ReaderTarget,
) -> Result<BTreeMap<String, BTreeSet<String>>, CljError> {
    Ok(analyze_program_all_with_reader_target(src, target)?
        .into_iter()
        .map(|(name, summary)| (name, summary.effects))
        .collect())
}

/// Minimal policy synthesis backed by the Kotoba analyzer.
pub fn minimal_policy(src: &str) -> Result<Policy, CljError> {
    Analyzer::new()?.minimal_policy(src)
}

/// Minimal policy synthesis for a specific reader target.
pub fn minimal_policy_with_reader_target(
    src: &str,
    target: ReaderTarget,
) -> Result<Policy, CljError> {
    Analyzer::new()?.minimal_policy_with_reader_target(src, target)
}

/// Synthesize a minimal policy for a source file using the self-hosted analyzer.
pub fn minimal_policy_file(path: impl AsRef<Path>) -> Result<Policy, CljError> {
    minimal_policy_file_with_reader_target(path, ReaderTarget::Kotoba)
}

/// Synthesize a minimal policy for a source file with a reader target.
pub fn minimal_policy_file_with_reader_target(
    path: impl AsRef<Path>,
    target: ReaderTarget,
) -> Result<Policy, CljError> {
    minimal_policy_file_with_reader_target_and_source_paths(path, target, &[])
}

/// Synthesize a minimal policy for a source file with reader target and source
/// paths.
pub fn minimal_policy_file_with_reader_target_and_source_paths(
    path: impl AsRef<Path>,
    target: ReaderTarget,
    source_paths: &[PathBuf],
) -> Result<Policy, CljError> {
    Analyzer::new()?.minimal_policy_file_with_reader_target_and_source_paths(
        path,
        target,
        source_paths,
    )
}

/// Check declared `{:effects ...}` rows by running the Kotoba analyzer.
pub fn check_effect_declarations(src: &str) -> Result<EffectCheck, CljError> {
    Analyzer::new()?.check_effect_declarations(src)
}

/// Check declared `{:effects ...}` rows for a specific reader target.
pub fn check_effect_declarations_with_reader_target(
    src: &str,
    target: ReaderTarget,
) -> Result<EffectCheck, CljError> {
    Analyzer::new()?.check_effect_declarations_with_reader_target(src, target)
}

/// Check class-level and per-resource policy grants with the Kotoba analyzer.
pub fn check_policy(src: &str, policy: &Policy) -> Result<PolicyCheck, CljError> {
    Analyzer::new()?.check_policy(src, policy)
}

/// Check class-level and per-resource policy grants for a specific reader target.
pub fn check_policy_with_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<PolicyCheck, CljError> {
    Analyzer::new()?.check_policy_with_reader_target(src, target, policy)
}

/// Check effect declarations and policy grants with one Kotoba analyzer run.
pub fn check_admission(src: &str, policy: &Policy) -> Result<AdmissionCheck, CljError> {
    Analyzer::new()?.check_admission(src, policy)
}

/// Check effect declarations and policy grants for a specific reader target.
pub fn check_admission_with_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<AdmissionCheck, CljError> {
    Analyzer::new()?.check_admission_with_reader_target(src, target, policy)
}

/// Check subset, types, effects, and policy with one Kotoba analyzer run.
pub fn check_compile_gate(src: &str, policy: &Policy) -> Result<CompileGateCheck, CljError> {
    Analyzer::new()?.check_compile_gate(src, policy)
}

/// Check subset, types, effects, and policy for a specific reader target with
/// one Kotoba analyzer run.
pub fn check_compile_gate_with_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<CompileGateCheck, CljError> {
    Analyzer::new()?.check_compile_gate_with_reader_target(src, target, policy)
}

/// Check executable-body safe-subset denials with the Kotoba analyzer.
pub fn check_subset(src: &str) -> Result<SubsetCheck, CljError> {
    Analyzer::new()?.check_subset(src)
}

/// Check executable-body safe-subset denials for a specific reader target.
pub fn check_subset_with_reader_target(
    src: &str,
    target: ReaderTarget,
) -> Result<SubsetCheck, CljError> {
    Analyzer::new()?.check_subset_with_reader_target(src, target)
}

/// Check the covered literal type slice with the Kotoba analyzer.
pub fn check_types(src: &str) -> Result<TypeCheck, CljError> {
    Analyzer::new()?.check_types(src)
}

/// Check the covered literal type slice for a specific reader target.
pub fn check_types_with_reader_target(
    src: &str,
    target: ReaderTarget,
) -> Result<TypeCheck, CljError> {
    Analyzer::new()?.check_types_with_reader_target(src, target)
}

/// Report policy over-grants using the Kotoba analyzer.
pub fn unused_grants(src: &str, policy: &Policy) -> Result<Vec<String>, CljError> {
    Analyzer::new()?.unused_grants(src, policy)
}

/// Report policy over-grants for a specific reader target.
pub fn unused_grants_with_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<String>, CljError> {
    Analyzer::new()?.unused_grants_with_reader_target(src, target, policy)
}

/// Report policy over-grants as compact machine-readable ids emitted by the
/// Kotoba analyzer, e.g. `graph-write:graphB`, `infer:*`, or `auth`.
pub fn unused_grant_ids(src: &str, policy: &Policy) -> Result<Vec<String>, CljError> {
    Analyzer::new()?.unused_grant_ids(src, policy)
}

/// Report policy over-grants for a specific reader target.
pub fn unused_grant_ids_with_reader_target(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<String>, CljError> {
    Analyzer::new()?.unused_grant_ids_with_reader_target(src, target, policy)
}

fn humanize_unused_grant(grant: &str) -> String {
    if grant == "auth" {
        return "auth: granted but `has-capability?` is never used".to_string();
    }
    if let Some((class, target)) = grant.split_once(':') {
        if target == "*" {
            return format!("{class}: entire capability granted but the cell never uses it");
        }
        return format!("{class}: `{target}` granted but never targeted by the cell");
    }
    grant.to_string()
}

fn compile_safe_clj_inner(
    analyzer: &Analyzer,
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
    with_prelude: bool,
) -> Result<Vec<u8>, CljError> {
    policy.validate_limits()?;

    let normalized = compat::normalize_source(src, target)?;
    let user_forms =
        kotoba_edn::parse_all(&normalized).map_err(|e| CljError::Read(e.to_string()))?;
    let selfhost_gate =
        match analyzer.check_compile_gate_with_reader_target(&normalized, target, policy) {
            Ok(gate) => Some(gate),
            // If full AST lowering fails, still let source-level subset facts
            // reject forbidden constructs before falling back to Rust's full
            // gates and eventual lowering error for non-forbidden unsupported
            // syntax.
            Err(CljError::Lower(_)) => {
                let subset = analyzer.check_subset_with_reader_target(&normalized, target)?;
                if !subset.ok {
                    return Err(CljError::Subset(format_subset_check_error(&subset)));
                }
                let types = analyzer.check_types_with_reader_target(&normalized, target)?;
                if !types.ok {
                    return Err(CljError::Type(format_type_check_error(&types)));
                }
                None
            }
            Err(err) => return Err(err),
        };
    if let Some(gate) = &selfhost_gate {
        if !gate.subset.ok {
            return Err(CljError::Subset(format_subset_check_error(&gate.subset)));
        }
    }
    subset::check_forms(&user_forms)?;
    if let Some(gate) = &selfhost_gate {
        if !gate.types.ok {
            return Err(CljError::Type(format_type_check_error(&gate.types)));
        }
    }
    ty::check_forms(&user_forms)?;

    if let Some(gate) = &selfhost_gate {
        if !gate.effects.ok {
            return Err(CljError::Effect(format_effect_check_error(&gate.effects)));
        }
    }

    let full = if with_prelude {
        format!("{}\n{normalized}", crate::safe_prelude(policy))
    } else {
        normalized.clone()
    };
    let program = ast::parse_program(&full)?;
    ty_infer::check(&program)?;

    let policy_check = if let Some(gate) = &selfhost_gate {
        gate.policy.clone()
    } else {
        let admission = analyzer.check_admission_with_reader_target(&normalized, target, policy)?;
        if !admission.effects.ok {
            return Err(CljError::Effect(format_effect_check_error(
                &admission.effects,
            )));
        }
        admission.policy
    };

    if !policy_check.ok {
        return Err(CljError::Policy(format_policy_check_error(&policy_check)));
    }

    codegen::compile_with_memory_max(&program, Some(policy.limits.memory_pages))
}

fn format_effect_check_error(check: &EffectCheck) -> String {
    let details = check
        .violations
        .iter()
        .map(|violation| {
            let missing = violation
                .missing
                .iter()
                .cloned()
                .collect::<Vec<_>>()
                .join(", ");
            let unknown = violation
                .unknown
                .iter()
                .cloned()
                .collect::<Vec<_>>()
                .join(", ");
            format!(
                "{}: missing {{{}}}; unknown {{{}}}",
                violation.name, missing, unknown
            )
        })
        .collect::<Vec<_>>()
        .join("\n  - ");
    format!(
        "self-hosted effect soundness rejected {} function(s):\n  - {}",
        check.violations.len(),
        details
    )
}

fn format_subset_check_error(check: &SubsetCheck) -> String {
    let denials = check.denials.iter().cloned().collect::<Vec<_>>();
    format!(
        "self-hosted safe subset rejected {} forbidden form(s):\n  - {}",
        denials.len(),
        denials.join("\n  - ")
    )
}

fn format_type_check_error(check: &TypeCheck) -> String {
    let denials = check.denials.iter().cloned().collect::<Vec<_>>();
    format!(
        "self-hosted literal type gate rejected {} builtin(s):\n  - {}",
        denials.len(),
        denials.join("\n  - ")
    )
}

fn format_policy_check_error(check: &PolicyCheck) -> String {
    let mut denials = check.denials.iter().cloned().collect::<Vec<_>>();
    denials.extend(check.target_denials.iter().cloned());
    format!(
        "self-hosted capability confinement rejected {} denial(s):\n  - {}",
        denials.len(),
        denials.join("\n  - ")
    )
}

fn program_all_input(src: &str, target: ReaderTarget) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?.to_cbor()
}

fn program_minimal_policy_input(src: &str, target: ReaderTarget) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?
        .with_check("minimal-policy")
        .to_cbor()
}

fn program_effect_check_input(src: &str, target: ReaderTarget) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_with_reader_target(src, target)?
        .with_check("effects")
        .to_cbor()
}

fn program_subset_check_input(src: &str, target: ReaderTarget) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?
        .with_check("subset")
        .to_cbor()
}

fn program_type_check_input(src: &str, target: ReaderTarget) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?
        .with_check("types")
        .to_cbor()
}

fn program_policy_check_input(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?
        .with_check("policy")
        .with_policy(policy)
        .to_cbor()
}

fn program_admission_check_input(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?
        .with_check("admission")
        .with_policy(policy)
        .to_cbor()
}

fn program_compile_gate_input(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?
        .with_check("compile-gate")
        .with_policy(policy)
        .to_cbor()
}

fn program_unused_grants_input(
    src: &str,
    target: ReaderTarget,
    policy: &Policy,
) -> Result<Vec<u8>, CljError> {
    AnalyzerRequest::from_source_or_source_only_with_reader_target(src, target)?
        .with_check("unused-grants")
        .with_policy(policy)
        .to_cbor()
}

/// Versioned request sent from Rust/tooling into the self-hosted analyzer.
#[derive(Debug, Clone)]
pub struct AnalyzerRequest {
    functions: Vec<AnalyzerFunction>,
    source_subset: Vec<SourceSubsetFact>,
    source_types: Vec<SourceTypeFact>,
    source_effects: Vec<SourceEffectFact>,
    check: Option<String>,
    policy: Option<Policy>,
    declared: BTreeMap<String, BTreeSet<String>>,
}

#[derive(Debug, Clone)]
struct SourceSubsetFact {
    kind: String,
    op: String,
    form: String,
}

#[derive(Debug, Clone)]
struct SourceTypeFact {
    op: String,
    args: Vec<i128>,
}

#[derive(Debug, Clone)]
struct SourceEffectFact {
    op: String,
    target: String,
}

#[derive(Debug, Clone)]
struct AnalyzerFunction {
    name: String,
    params: Vec<String>,
    body: Vec<Expr>,
    source_effects: Vec<SourceEffectFact>,
}

impl AnalyzerRequest {
    pub fn from_source(src: &str) -> Result<Self, CljError> {
        Self::from_source_with_reader_target(src, ReaderTarget::Kotoba)
    }

    pub fn from_source_with_reader_target(
        src: &str,
        target: ReaderTarget,
    ) -> Result<Self, CljError> {
        let normalized = compat::normalize_source(src, target)?;
        let source_forms =
            kotoba_edn::parse_all(&normalized).map_err(|e| CljError::Read(e.to_string()))?;
        let source_subset = source_subset_facts(&source_forms);
        let source_types = source_type_facts(&source_forms);
        let mut source_effects = source_effect_facts_by_function(&source_forms);
        let program = ast::parse_program(&normalized)?;
        let mut declared = BTreeMap::new();
        Ok(Self {
            functions: program
                .functions
                .into_iter()
                .map(|function| {
                    let function_source_effects =
                        source_effects.remove(&function.name).unwrap_or_default();
                    if let Some(effects) = &function.declared_effects {
                        declared.insert(function.name.clone(), effects.clone());
                    }
                    AnalyzerFunction {
                        name: function.name,
                        params: function.params,
                        body: function.body,
                        source_effects: function_source_effects,
                    }
                })
                .collect(),
            source_subset,
            source_types,
            source_effects: Vec::new(),
            check: None,
            policy: None,
            declared,
        })
    }

    fn from_source_or_source_only_with_reader_target(
        src: &str,
        target: ReaderTarget,
    ) -> Result<Self, CljError> {
        Self::from_source_with_reader_target(src, target).or_else(|err| match err {
            CljError::Lower(_) => Self::from_source_subset_only_with_reader_target(src, target),
            other => Err(other),
        })
    }

    fn from_source_subset_only_with_reader_target(
        src: &str,
        target: ReaderTarget,
    ) -> Result<Self, CljError> {
        let normalized = compat::normalize_source(src, target)?;
        let source_forms =
            kotoba_edn::parse_all(&normalized).map_err(|e| CljError::Read(e.to_string()))?;
        Ok(Self {
            functions: Vec::new(),
            source_subset: source_subset_facts(&source_forms),
            source_types: source_type_facts(&source_forms),
            source_effects: source_effect_facts(&source_forms),
            check: None,
            policy: None,
            declared: BTreeMap::new(),
        })
    }

    pub fn abi(&self) -> &'static str {
        SAFE_ANALYZER_ABI
    }

    pub fn check(&self) -> Option<&str> {
        self.check.as_deref()
    }

    pub fn function_count(&self) -> usize {
        self.functions.len()
    }

    pub fn with_check(mut self, check: &str) -> Self {
        self.check = Some(check.to_string());
        self
    }

    pub fn with_policy(mut self, policy: &Policy) -> Self {
        self.policy = Some(policy.clone());
        self
    }

    pub fn with_declared_effects(mut self, declared: BTreeMap<String, BTreeSet<String>>) -> Self {
        self.declared = declared;
        self
    }

    pub fn to_cbor(&self) -> Result<Vec<u8>, CljError> {
        let functions = Value::Array(
            self.functions
                .iter()
                .map(|function| {
                    let mut entries = vec![
                        (
                            Value::Text("name".to_string()),
                            Value::Text(function.name.clone()),
                        ),
                        (
                            Value::Text("params".to_string()),
                            Value::Array(function.params.iter().map(|param| text(param)).collect()),
                        ),
                        (
                            Value::Text("body".to_string()),
                            Value::Array(function.body.iter().map(ast_expr_value).collect()),
                        ),
                        (
                            Value::Text("type-body".to_string()),
                            Value::Array(function.body.iter().map(ast_expr_value).collect()),
                        ),
                    ];
                    if let Some(ret) = function.body.last() {
                        entries.push((Value::Text("ret".to_string()), ast_expr_value(ret)));
                        entries
                            .push((Value::Text("ret-call-ast".to_string()), ast_expr_value(ret)));
                    }
                    if let Some(declared) = self.declared.get(&function.name) {
                        entries.push((
                            Value::Text("declared".to_string()),
                            Value::Array(declared.iter().map(|effect| text(effect)).collect()),
                        ));
                    }
                    if !function.source_effects.is_empty() {
                        entries.push((
                            Value::Text("source-effects".to_string()),
                            Value::Array(
                                function
                                    .source_effects
                                    .iter()
                                    .map(|fact| {
                                        map(vec![
                                            ("op", text(&fact.op)),
                                            ("target", text(&fact.target)),
                                        ])
                                    })
                                    .collect(),
                            ),
                        ));
                    }
                    Value::Map(entries)
                })
                .collect(),
        );

        let mut entries = vec![(
            Value::Text("abi".to_string()),
            Value::Text(SAFE_ANALYZER_ABI.to_string()),
        )];
        if let Some(check) = &self.check {
            entries.push((
                Value::Text("check".to_string()),
                Value::Text(check.to_string()),
            ));
        }
        if let Some(policy) = &self.policy {
            entries.push((Value::Text("policy".to_string()), policy_value(policy)));
        }
        entries.push((Value::Text("program".to_string()), functions));
        if !self.source_subset.is_empty() {
            entries.push((
                Value::Text("source-subset".to_string()),
                Value::Array(
                    self.source_subset
                        .iter()
                        .map(|fact| {
                            map(vec![
                                ("kind", text(&fact.kind)),
                                ("op", text(&fact.op)),
                                ("form", text(&fact.form)),
                            ])
                        })
                        .collect(),
                ),
            ));
        }
        if !self.source_types.is_empty() {
            entries.push((
                Value::Text("source-types".to_string()),
                Value::Array(
                    self.source_types
                        .iter()
                        .map(|fact| {
                            map(vec![
                                ("op", text(&fact.op)),
                                (
                                    "args",
                                    Value::Array(
                                        fact.args
                                            .iter()
                                            .map(|arg| {
                                                Value::Integer(
                                                    i64::try_from(*arg)
                                                        .expect("source type fact fits i64")
                                                        .into(),
                                                )
                                            })
                                            .collect(),
                                    ),
                                ),
                            ])
                        })
                        .collect(),
                ),
            ));
        }
        if !self.source_effects.is_empty() {
            entries.push((
                Value::Text("source-effects".to_string()),
                Value::Array(
                    self.source_effects
                        .iter()
                        .map(|fact| {
                            map(vec![("op", text(&fact.op)), ("target", text(&fact.target))])
                        })
                        .collect(),
                ),
            ));
        }
        encode_value(&Value::Map(entries))
    }
}

fn source_subset_facts(forms: &[kotoba_edn::EdnValue]) -> Vec<SourceSubsetFact> {
    let mut facts = Vec::new();
    for form in forms {
        collect_source_subset_facts(form, &mut facts);
    }
    facts
}

fn collect_source_subset_facts(value: &kotoba_edn::EdnValue, out: &mut Vec<SourceSubsetFact>) {
    match value {
        kotoba_edn::EdnValue::List(items) => {
            if let Some(kotoba_edn::EdnValue::Symbol(head)) = items.first() {
                out.push(SourceSubsetFact {
                    kind: "head".to_string(),
                    op: head.name.clone(),
                    form: head.to_qualified(),
                });
                if head.name == "ns" {
                    collect_ns_clause_facts(items, out);
                    return;
                }
                if crate::ast::is_inert_form(&head.name) || source_non_executable_form(&head.name) {
                    return;
                }
            }
            for item in items {
                collect_source_subset_facts(item, out);
            }
        }
        kotoba_edn::EdnValue::Vector(items) => {
            for item in items {
                collect_source_subset_facts(item, out);
            }
        }
        kotoba_edn::EdnValue::Set(items) => {
            for item in items {
                collect_source_subset_facts(item, out);
            }
        }
        kotoba_edn::EdnValue::Map(entries) => {
            for (key, value) in entries {
                collect_source_subset_facts(key, out);
                collect_source_subset_facts(value, out);
            }
        }
        kotoba_edn::EdnValue::Tagged { value, .. } => collect_source_subset_facts(value, out),
        _ => {}
    }
}

fn collect_ns_clause_facts(items: &[kotoba_edn::EdnValue], out: &mut Vec<SourceSubsetFact>) {
    for clause in items.iter().skip(1) {
        let head_kw = match clause {
            kotoba_edn::EdnValue::List(xs) | kotoba_edn::EdnValue::Vector(xs) => {
                xs.first().and_then(kotoba_edn::EdnValue::as_keyword)
            }
            _ => None,
        };
        if let Some(kw) = head_kw {
            out.push(SourceSubsetFact {
                kind: "ns-clause".to_string(),
                op: kw.0.name.clone(),
                form: kw.to_qualified(),
            });
        }
    }
}

fn source_type_facts(forms: &[kotoba_edn::EdnValue]) -> Vec<SourceTypeFact> {
    let mut facts = Vec::new();
    for form in forms {
        collect_source_type_facts(form, &mut facts);
    }
    facts
}

fn collect_source_type_facts(value: &kotoba_edn::EdnValue, out: &mut Vec<SourceTypeFact>) {
    match value {
        kotoba_edn::EdnValue::List(items) => {
            if let Some(kotoba_edn::EdnValue::Symbol(head)) = items.first() {
                if crate::ast::is_inert_form(&head.name) || source_non_executable_form(&head.name) {
                    return;
                }
                out.push(SourceTypeFact {
                    op: source_type_op_name(head),
                    args: items.iter().skip(1).map(source_literal_fact).collect(),
                });
            }
            for item in items {
                collect_source_type_facts(item, out);
            }
        }
        kotoba_edn::EdnValue::Vector(items) => {
            for item in items {
                collect_source_type_facts(item, out);
            }
        }
        kotoba_edn::EdnValue::Set(items) => {
            for item in items {
                collect_source_type_facts(item, out);
            }
        }
        kotoba_edn::EdnValue::Map(entries) => {
            for (key, value) in entries {
                collect_source_type_facts(key, out);
                collect_source_type_facts(value, out);
            }
        }
        kotoba_edn::EdnValue::Tagged { value, .. } => collect_source_type_facts(value, out),
        _ => {}
    }
}

fn source_non_executable_form(name: &str) -> bool {
    matches!(
        name,
        "ns" | "require"
            | "require-macros"
            | "use"
            | "use-macros"
            | "refer-clojure"
            | "in-ns"
            | "alias"
            | "create-ns"
            | "remove-ns"
            | "import"
            | "gen-class"
            | "set!"
            | "defrecord"
            | "deftype"
            | "defprotocol"
            | "extend-type"
            | "extend-protocol"
            | "defmulti"
            | "defmethod"
            | "defmacro"
            | "definline"
            | "defstruct"
            | "create-struct"
            | "declare"
    )
}

fn source_type_op_name(symbol: &kotoba_edn::Symbol) -> String {
    match symbol.namespace.as_deref() {
        Some("Math") => symbol.to_qualified(),
        _ => symbol.name.clone(),
    }
}

fn source_literal_fact(value: &kotoba_edn::EdnValue) -> i128 {
    match value {
        kotoba_edn::EdnValue::Integer(_)
        | kotoba_edn::EdnValue::Float(_)
        | kotoba_edn::EdnValue::BigInt(_)
        | kotoba_edn::EdnValue::BigDec(_) => 2,
        kotoba_edn::EdnValue::String(_)
        | kotoba_edn::EdnValue::Keyword(_)
        | kotoba_edn::EdnValue::Char(_)
        | kotoba_edn::EdnValue::Vector(_)
        | kotoba_edn::EdnValue::Map(_)
        | kotoba_edn::EdnValue::Set(_) => 5,
        _ => 0,
    }
}

fn source_effect_facts(forms: &[kotoba_edn::EdnValue]) -> Vec<SourceEffectFact> {
    let mut facts = Vec::new();
    for form in forms {
        collect_top_level_source_effects(form, &mut facts);
    }
    facts
}

fn source_effect_facts_by_function(
    forms: &[kotoba_edn::EdnValue],
) -> BTreeMap<String, Vec<SourceEffectFact>> {
    let mut facts = BTreeMap::new();
    for form in forms {
        collect_top_level_source_effects_by_function(form, &mut facts);
    }
    facts
}

fn collect_top_level_source_effects_by_function(
    value: &kotoba_edn::EdnValue,
    out: &mut BTreeMap<String, Vec<SourceEffectFact>>,
) {
    let kotoba_edn::EdnValue::List(items) = value else {
        return;
    };
    let Some(kotoba_edn::EdnValue::Symbol(head)) = items.first() else {
        return;
    };
    match head.name.as_str() {
        "do" => {
            for item in items.iter().skip(1) {
                collect_top_level_source_effects_by_function(item, out);
            }
        }
        "defn" | "defn-" => {
            if let Some(name) = defn_source_name(items) {
                let mut effects = Vec::new();
                collect_defn_source_effects(items, &mut effects);
                if !effects.is_empty() {
                    out.entry(name).or_default().extend(effects);
                }
            }
        }
        _ => {}
    }
}

fn defn_source_name(items: &[kotoba_edn::EdnValue]) -> Option<String> {
    match items.get(1) {
        Some(kotoba_edn::EdnValue::Symbol(symbol)) => Some(symbol.name.clone()),
        _ => None,
    }
}

fn collect_top_level_source_effects(value: &kotoba_edn::EdnValue, out: &mut Vec<SourceEffectFact>) {
    let kotoba_edn::EdnValue::List(items) = value else {
        return;
    };
    let Some(kotoba_edn::EdnValue::Symbol(head)) = items.first() else {
        return;
    };
    match head.name.as_str() {
        "do" => {
            for item in items.iter().skip(1) {
                collect_top_level_source_effects(item, out);
            }
        }
        "defn" | "defn-" => collect_defn_source_effects(items, out),
        _ => {}
    }
}

fn collect_defn_source_effects(items: &[kotoba_edn::EdnValue], out: &mut Vec<SourceEffectFact>) {
    if items.len() < 3 {
        return;
    }
    let mut idx = 2;
    if matches!(items.get(idx), Some(kotoba_edn::EdnValue::String(_))) {
        idx += 1;
    }
    if matches!(items.get(idx), Some(kotoba_edn::EdnValue::Map(_))) {
        idx += 1;
    }
    match items.get(idx) {
        Some(kotoba_edn::EdnValue::Vector(_)) => {
            for body in defn_body_after_params(&items[(idx + 1)..]) {
                collect_source_effect_expr(body, out);
            }
        }
        Some(kotoba_edn::EdnValue::List(_)) => {
            for arity in &items[idx..] {
                collect_defn_arity_source_effects(arity, out);
            }
        }
        _ => {}
    }
}

fn collect_defn_arity_source_effects(
    value: &kotoba_edn::EdnValue,
    out: &mut Vec<SourceEffectFact>,
) {
    let kotoba_edn::EdnValue::List(items) = value else {
        return;
    };
    let Some(kotoba_edn::EdnValue::Vector(_)) = items.first() else {
        return;
    };
    for body in defn_body_after_params(&items[1..]) {
        collect_source_effect_expr(body, out);
    }
}

fn defn_body_after_params(items: &[kotoba_edn::EdnValue]) -> &[kotoba_edn::EdnValue] {
    if matches!(items.first(), Some(kotoba_edn::EdnValue::Map(_))) {
        &items[1..]
    } else {
        items
    }
}

fn collect_source_effect_expr(value: &kotoba_edn::EdnValue, out: &mut Vec<SourceEffectFact>) {
    match value {
        kotoba_edn::EdnValue::List(items) => {
            let Some(kotoba_edn::EdnValue::Symbol(head)) = items.first() else {
                for item in items {
                    collect_source_effect_expr(item, out);
                }
                return;
            };
            if crate::ast::is_inert_form(&head.name) || source_non_executable_form(&head.name) {
                return;
            }
            if source_effect_op(&head.name) {
                out.push(SourceEffectFact {
                    op: source_effect_op_name(head),
                    target: source_effect_target(&head.name, items),
                });
            }
            for item in items.iter().skip(1) {
                collect_source_effect_expr(item, out);
            }
        }
        kotoba_edn::EdnValue::Vector(items) => {
            for item in items {
                collect_source_effect_expr(item, out);
            }
        }
        kotoba_edn::EdnValue::Set(items) => {
            for item in items {
                collect_source_effect_expr(item, out);
            }
        }
        kotoba_edn::EdnValue::Map(entries) => {
            for (key, value) in entries {
                collect_source_effect_expr(key, out);
                collect_source_effect_expr(value, out);
            }
        }
        kotoba_edn::EdnValue::Tagged { value, .. } => collect_source_effect_expr(value, out),
        _ => {}
    }
}

fn source_effect_op(name: &str) -> bool {
    matches!(
        name,
        "kqe-assert!"
            | "kqe-retract!"
            | "kqe-get-objects"
            | "kqe-query"
            | "llm-infer"
            | "has-capability?"
    )
}

fn source_effect_op_name(symbol: &kotoba_edn::Symbol) -> String {
    match symbol.namespace.as_deref() {
        Some("Math") => symbol.to_qualified(),
        _ => symbol.name.clone(),
    }
}

fn source_effect_target(op: &str, items: &[kotoba_edn::EdnValue]) -> String {
    match op {
        "kqe-assert!" | "kqe-retract!" | "kqe-get-objects" | "llm-infer" => match items.get(1) {
            Some(kotoba_edn::EdnValue::String(target)) => target.clone(),
            _ => String::new(),
        },
        _ => String::new(),
    }
}

fn policy_value(policy: &Policy) -> Value {
    Value::Map(vec![
        (
            Value::Text("graph-read".to_string()),
            Value::Array(policy.graph_read.iter().map(|cid| text(cid)).collect()),
        ),
        (
            Value::Text("graph-write".to_string()),
            Value::Array(policy.graph_write.iter().map(|cid| text(cid)).collect()),
        ),
        (
            Value::Text("infer".to_string()),
            Value::Array(policy.infer.iter().map(|cid| text(cid)).collect()),
        ),
        (
            Value::Text("auth".to_string()),
            Value::Text(if policy.auth { "true" } else { "false" }.to_string()),
        ),
    ])
}

fn encode_value(value: &Value) -> Result<Vec<u8>, CljError> {
    let mut out = Vec::new();
    ciborium::into_writer(value, &mut out)
        .map_err(|e| CljError::Run(format!("selfhost analyzer input CBOR: {e}")))?;
    Ok(out)
}

fn text(s: &str) -> Value {
    Value::Text(s.to_string())
}

fn map(entries: Vec<(&str, Value)>) -> Value {
    Value::Map(
        entries
            .into_iter()
            .map(|(key, value)| (Value::Text(key.to_string()), value))
            .collect(),
    )
}

fn builtin_name(op: Builtin) -> &'static str {
    match op {
        Builtin::Add => "+",
        Builtin::Sub => "-",
        Builtin::Mul => "*",
        Builtin::Div => "/",
        Builtin::Mod => "mod",
        Builtin::Rem => "rem",
        Builtin::Inc => "inc",
        Builtin::Dec => "dec",
        Builtin::Abs => "abs",
        Builtin::Min => "min",
        Builtin::Max => "max",
        Builtin::Lt => "<",
        Builtin::Gt => ">",
        Builtin::Le => "<=",
        Builtin::Ge => ">=",
        Builtin::Zero => "zero?",
        Builtin::Pos => "pos?",
        Builtin::Neg => "neg?",
        Builtin::Even => "even?",
        Builtin::Odd => "odd?",
        Builtin::StrLen => "str-len",
        Builtin::ByteAt => "byte-at",
        Builtin::BytesAlloc => "bytes-alloc",
        Builtin::ByteAppend => "byte-append!",
        Builtin::BytesLen => "bytes-len",
        Builtin::BytesFinish => "bytes-finish",
        Builtin::BitAnd => "bit-and",
        Builtin::BitOr => "bit-or",
        Builtin::BitXor => "bit-xor",
        Builtin::BitShiftLeft => "bit-shift-left",
        Builtin::BitShiftRight => "bit-shift-right",
        Builtin::Double => "double",
        Builtin::Int => "int",
        Builtin::MathRound => "Math/round",
        Builtin::MathFloor => "Math/floor",
        Builtin::MathCeil => "Math/ceil",
        Builtin::MathAbs => "Math/abs",
        Builtin::MathSqrt => "Math/sqrt",
        Builtin::HasCapability => "has-capability?",
        Builtin::LlmInfer => "llm-infer",
        Builtin::KqeAssert => "kqe-assert!",
        Builtin::KqeRetract => "kqe-retract!",
        Builtin::KqeGetObjects => "kqe-get-objects",
        Builtin::KqeQuery => "kqe-query",
        Builtin::Alloc => "alloc",
        Builtin::Load64 => "load64",
        Builtin::Store64 => "store64!",
        Builtin::Load32 => "load32",
        Builtin::Store32 => "store32!",
        _ => "pure-builtin",
    }
}

fn ast_expr_value(expr: &Expr) -> Value {
    match expr {
        Expr::Int(n) => map(vec![
            ("tag", text("int")),
            ("value", Value::Integer((*n).into())),
        ]),
        Expr::Float(f) => map(vec![("tag", text("float")), ("value", Value::Float(*f))]),
        Expr::Str(bytes) => map(vec![
            ("tag", text("str")),
            // Lossy rather than `.expect()`: serializing a program for analysis
            // must not panic the host on a non-UTF-8 string literal (string
            // literals are normally UTF-8, but a reader/escape edge must degrade
            // gracefully, not abort).
            ("value", text(&String::from_utf8_lossy(bytes))),
        ]),
        Expr::Var(name) => map(vec![("tag", text("var")), ("name", text(name))]),
        Expr::If { cond, then, els } => map(vec![
            ("tag", text("if")),
            ("cond", ast_expr_value(cond)),
            ("then", ast_expr_value(then)),
            ("else", ast_expr_value(els)),
        ]),
        Expr::Let { bindings, body } => map(vec![
            ("tag", text("let")),
            ("bindings", ast_bindings_value(bindings)),
            (
                "body",
                Value::Array(body.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::Do(body) => map(vec![
            ("tag", text("do")),
            (
                "body",
                Value::Array(body.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::Loop { bindings, body } => map(vec![
            ("tag", text("loop")),
            ("bindings", ast_bindings_value(bindings)),
            (
                "body",
                Value::Array(body.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::Recur(args) => map(vec![
            ("tag", text("recur")),
            (
                "args",
                Value::Array(args.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::Builtin { op, args } => map(vec![
            ("tag", text("builtin")),
            ("op", text(builtin_name(*op))),
            (
                "args",
                Value::Array(args.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::Call { name, args } => map(vec![
            ("tag", text("call")),
            ("name", text(name)),
            (
                "args",
                Value::Array(args.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::Fn { params, body } => map(vec![
            ("tag", text("fn")),
            (
                "params",
                Value::Array(params.iter().map(|param| text(param)).collect()),
            ),
            (
                "body",
                Value::Array(body.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::MakeClosure {
            table_slot,
            captures,
        } => map(vec![
            ("tag", text("make-closure")),
            ("table-slot", Value::Integer((*table_slot).into())),
            (
                "captures",
                Value::Array(captures.iter().map(ast_expr_value).collect()),
            ),
        ]),
        Expr::ClosureRef(slot) => map(vec![
            ("tag", text("closure-ref")),
            ("slot", Value::Integer((*slot).into())),
        ]),
        Expr::CallValue { f, args } => map(vec![
            ("tag", text("call-value")),
            ("f", ast_expr_value(f)),
            (
                "args",
                Value::Array(args.iter().map(ast_expr_value).collect()),
            ),
        ]),
    }
}

fn ast_bindings_value(bindings: &[(String, Expr)]) -> Value {
    Value::Array(
        bindings
            .iter()
            .map(|(name, value)| map(vec![("name", text(name)), ("value", ast_expr_value(value))]))
            .collect(),
    )
}

fn function_summaries(value: &Value) -> Result<BTreeMap<String, FunctionSummary>, CljError> {
    let functions = map_field(value, "functions")?.as_array().ok_or_else(|| {
        CljError::Run("selfhost analyzer `functions` is not an array".to_string())
    })?;
    let mut out = BTreeMap::new();
    for function in functions {
        let name = text_field(function, "name")?.to_string();
        out.insert(
            name,
            FunctionSummary {
                effects: text_array_set(function, "effects")?,
                caps: text_array_set(function, "caps")?,
                targets: text_array_set(function, "targets")?,
            },
        );
    }
    Ok(out)
}

fn policy_from_value(value: &Value) -> Result<Policy, CljError> {
    let mut policy = Policy::deny_all()
        .grant_graph_read(text_array_set(value, "graph-read")?)
        .grant_graph_write(text_array_set(value, "graph-write")?)
        .grant_infer(text_array_set(value, "infer")?);
    if text_field(value, "auth")? == "true" {
        policy = policy.grant_auth();
    }
    Ok(policy)
}

fn effect_check_from_value(value: &Value) -> Result<EffectCheck, CljError> {
    let violations = map_field(value, "violations")?
        .as_array()
        .ok_or_else(|| CljError::Run("selfhost analyzer `violations` is not an array".to_string()))?
        .iter()
        .map(|violation| {
            Ok(EffectViolation {
                name: text_field(violation, "name")?.to_string(),
                used: text_array_set(violation, "used")?,
                declared: text_array_set(violation, "declared")?,
                missing: text_array_set(violation, "missing")?,
                unknown: text_array_set(violation, "unknown")?,
            })
        })
        .collect::<Result<Vec<_>, CljError>>()?;
    Ok(EffectCheck {
        ok: bool_field(value, "ok")?,
        violations,
    })
}

fn policy_check_from_value(value: &Value) -> Result<PolicyCheck, CljError> {
    Ok(PolicyCheck {
        ok: bool_field(value, "ok")?,
        used: text_array_set(value, "used")?,
        granted: text_array_set(value, "granted")?,
        denials: text_array_set(value, "denials")?,
        target_denials: text_array_set(value, "target-denials")?,
    })
}

fn subset_check_from_value(value: &Value) -> Result<SubsetCheck, CljError> {
    Ok(SubsetCheck {
        ok: bool_field(value, "ok")?,
        denials: text_array_set(value, "denials")?,
    })
}

fn type_check_from_value(value: &Value) -> Result<TypeCheck, CljError> {
    Ok(TypeCheck {
        ok: bool_field(value, "ok")?,
        denials: text_array_set(value, "denials")?,
    })
}

fn admission_check_from_value(value: &Value) -> Result<AdmissionCheck, CljError> {
    Ok(AdmissionCheck {
        effects: effect_check_from_value(map_field(value, "effects")?)?,
        policy: policy_check_from_value(map_field(value, "policy")?)?,
    })
}

fn compile_gate_check_from_value(value: &Value) -> Result<CompileGateCheck, CljError> {
    Ok(CompileGateCheck {
        subset: subset_check_from_value(map_field(value, "subset")?)?,
        types: type_check_from_value(map_field(value, "types")?)?,
        effects: effect_check_from_value(map_field(value, "effects")?)?,
        policy: policy_check_from_value(map_field(value, "policy")?)?,
    })
}

fn require_abi(value: &Value) -> Result<(), CljError> {
    let abi = text_field(value, "abi")?;
    if abi == SAFE_ANALYZER_ABI {
        Ok(())
    } else {
        Err(CljError::Run(format!(
            "selfhost analyzer ABI mismatch: expected {SAFE_ANALYZER_ABI}, got {abi}"
        )))
    }
}

fn require_no_analyzer_error(value: &Value) -> Result<(), CljError> {
    if let Some(error) = optional_text_field(value, "error")? {
        let expected = optional_text_field(value, "expected")?.unwrap_or("");
        let got = optional_text_field(value, "got")?.unwrap_or("");
        return Err(CljError::Run(format!(
            "selfhost analyzer error: {error}; expected {expected}; got {got}"
        )));
    }
    Ok(())
}

fn map_field<'a>(value: &'a Value, field: &str) -> Result<&'a Value, CljError> {
    value
        .as_map()
        .ok_or_else(|| CljError::Run("selfhost analyzer output is not a map".to_string()))?
        .iter()
        .find_map(|(k, v)| (k.as_text() == Some(field)).then_some(v))
        .ok_or_else(|| CljError::Run(format!("selfhost analyzer output missing `{field}`")))
}

fn text_field<'a>(value: &'a Value, field: &str) -> Result<&'a str, CljError> {
    map_field(value, field)?
        .as_text()
        .ok_or_else(|| CljError::Run(format!("selfhost analyzer `{field}` is not text")))
}

fn optional_text_field<'a>(value: &'a Value, field: &str) -> Result<Option<&'a str>, CljError> {
    let Some(field_value) = value
        .as_map()
        .ok_or_else(|| CljError::Run("selfhost analyzer output is not a map".to_string()))?
        .iter()
        .find_map(|(k, v)| (k.as_text() == Some(field)).then_some(v))
    else {
        return Ok(None);
    };
    field_value
        .as_text()
        .map(Some)
        .ok_or_else(|| CljError::Run(format!("selfhost analyzer `{field}` is not text")))
}

fn bool_field(value: &Value, field: &str) -> Result<bool, CljError> {
    match text_field(value, field)? {
        "true" => Ok(true),
        "false" => Ok(false),
        other => Err(CljError::Run(format!(
            "selfhost analyzer `{field}` is not boolean text: {other}"
        ))),
    }
}

fn text_array_vec(value: &Value, field: &str) -> Result<Vec<String>, CljError> {
    let array = map_field(value, field)?
        .as_array()
        .ok_or_else(|| CljError::Run(format!("selfhost analyzer `{field}` is not an array")))?;
    array
        .iter()
        .map(|v| {
            v.as_text().map(str::to_string).ok_or_else(|| {
                CljError::Run(format!(
                    "selfhost analyzer `{field}` contains non-text item"
                ))
            })
        })
        .collect()
}

fn text_array_set(value: &Value, field: &str) -> Result<BTreeSet<String>, CljError> {
    let array = map_field(value, field)?
        .as_array()
        .ok_or_else(|| CljError::Run(format!("selfhost analyzer `{field}` is not an array")))?;
    array
        .iter()
        .map(|v| {
            v.as_text().map(str::to_string).ok_or_else(|| {
                CljError::Run(format!(
                    "selfhost analyzer `{field}` contains non-text item"
                ))
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bridge_program_inputs_include_versioned_abi_marker() {
        let src = r#"
            (defn helper []
              (kqe-assert! "graphA" "s" "p" "v"))

            (defn run {:effects #{:graph-write}} []
              (helper))
        "#;
        let input = program_admission_check_input(
            src,
            ReaderTarget::Kotoba,
            &Policy::deny_all().grant_graph_write(["graphA"]),
        )
        .expect("build analyzer input");
        let value: Value =
            ciborium::from_reader(input.as_slice()).expect("decode analyzer input cbor");

        assert_eq!(text_field(&value, "abi").unwrap(), SAFE_ANALYZER_ABI);
        assert_eq!(text_field(&value, "check").unwrap(), "admission");
        assert!(map_field(&value, "program").is_ok());
        assert!(map_field(&value, "policy").is_ok());

        let functions = map_field(&value, "program")
            .unwrap()
            .as_array()
            .expect("program array");
        let run = functions
            .iter()
            .find(|function| text_field(function, "name").unwrap() == "run")
            .expect("run function");
        assert!(map_field(run, "body").is_ok());
        assert!(map_field(run, "forms").is_err());
        assert_eq!(
            text_array_set(run, "declared").unwrap(),
            BTreeSet::from(["graph-write".to_string()])
        );
    }

    #[test]
    fn bridge_program_inputs_include_source_subset_facts() {
        let src = r#"
            (ns demo.core
              (:require [evil.ns]))

            (defn run [] (+ "x" 1))
        "#;
        let input = program_subset_check_input(src, ReaderTarget::Kotoba)
            .expect("build analyzer subset input");
        let value: Value =
            ciborium::from_reader(input.as_slice()).expect("decode analyzer input cbor");

        let facts = map_field(&value, "source-subset")
            .expect("source-subset facts")
            .as_array()
            .expect("source-subset array");
        assert!(facts.iter().any(|fact| {
            text_field(fact, "kind").ok() == Some("ns-clause")
                && text_field(fact, "op").ok() == Some("require")
        }));

        let type_input =
            program_type_check_input(src, ReaderTarget::Kotoba).expect("build analyzer type input");
        let type_value: Value =
            ciborium::from_reader(type_input.as_slice()).expect("decode analyzer input cbor");
        let type_facts = map_field(&type_value, "source-types")
            .expect("source-types facts")
            .as_array()
            .expect("source-types array");
        assert!(type_facts
            .iter()
            .any(|fact| text_field(fact, "op").ok() == Some("+")));

        let source_only_src = r#"
            (defn run [] (kqe-assert! "graphB" "s" "p" "v"))
            (unsupported-top-level)
        "#;
        let compile_gate_input =
            program_compile_gate_input(source_only_src, ReaderTarget::Kotoba, &Policy::deny_all())
                .expect("build source-only compile gate input");
        let compile_gate_value: Value = ciborium::from_reader(compile_gate_input.as_slice())
            .expect("decode source-only compile gate cbor");
        let effect_facts = map_field(&compile_gate_value, "source-effects")
            .expect("source-effects facts")
            .as_array()
            .expect("source-effects array");
        assert!(effect_facts.iter().any(|fact| {
            text_field(fact, "op").ok() == Some("kqe-assert!")
                && text_field(fact, "target").ok() == Some("graphB")
        }));
    }
}

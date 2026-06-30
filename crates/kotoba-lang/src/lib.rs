//! Language profile constants for canonical Kotoba source.
//!
//! This crate is intentionally small and dependency-free. It defines the source
//! compatibility contract shared by tools that accept Kotoba language source;
//! compiler implementation details stay in `kotoba-clj`.

use std::path::Path;

pub const PROFILE_EDN: &str = include_str!("../resources/kotoba/lang/profile.edn");
pub const CONFORMANCE_MANIFEST_EDN: &str =
    include_str!("../resources/kotoba/lang/conformance/manifest.edn");
pub const COVERAGE_EDN: &str = include_str!("../../../docs/lang/coverage.edn");
pub const GATES_MD: &str = include_str!("../../../docs/lang/gates.md");

/// Reader conditional target used when normalizing `.cljc` source.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum ReaderTarget {
    /// Kotoba's authoring target. Selects `:kotoba`, then `:clj`, then `:default`.
    Kotoba,
    /// JVM Clojure compatibility target. Selects `:clj`, then `:default`.
    Clj,
    /// ClojureScript compatibility target. Selects `:cljs`, then `:default`.
    Cljs,
}

impl ReaderTarget {
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "kotoba" => Some(Self::Kotoba),
            "clj" => Some(Self::Clj),
            "cljs" => Some(Self::Cljs),
            _ => None,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Kotoba => "kotoba",
            Self::Clj => "clj",
            Self::Cljs => "cljs",
        }
    }

    /// Reader conditional branches checked, in order.
    pub fn reader_branches(self) -> &'static [&'static str] {
        match self {
            Self::Kotoba => &["kotoba", "clj", "default"],
            Self::Clj => &["clj", "default"],
            Self::Cljs => &["cljs", "default"],
        }
    }

    /// Source file extension priority for namespace resolution.
    pub fn namespace_extension_priority(self) -> &'static [&'static str] {
        match self {
            Self::Kotoba => &["kotoba", "cljc", "clj", "cljs"],
            Self::Clj => &["cljc", "clj", "kotoba", "cljs"],
            Self::Cljs => &["cljc", "cljs", "clj", "kotoba"],
        }
    }
}

pub const SUPPORTED_SOURCE_EXTENSIONS: &[&str] = &["kotoba", "clj", "cljc", "cljs"];

pub fn is_supported_source_extension(ext: &str) -> bool {
    SUPPORTED_SOURCE_EXTENSIONS.contains(&ext)
}

pub fn is_supported_source_path(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(is_supported_source_extension)
}

pub const DEFAULT_READER_TARGET: ReaderTarget = ReaderTarget::Kotoba;

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_edn::EdnValue;

    #[test]
    fn kotoba_reader_target_falls_back_to_clj_then_default() {
        assert_eq!(
            ReaderTarget::Kotoba.reader_branches(),
            &["kotoba", "clj", "default"]
        );
    }

    #[test]
    fn extension_priorities_are_stable() {
        assert_eq!(
            ReaderTarget::Kotoba.namespace_extension_priority(),
            &["kotoba", "cljc", "clj", "cljs"]
        );
        assert_eq!(
            ReaderTarget::Clj.namespace_extension_priority(),
            &["cljc", "clj", "kotoba", "cljs"]
        );
        assert_eq!(
            ReaderTarget::Cljs.namespace_extension_priority(),
            &["cljc", "cljs", "clj", "kotoba"]
        );
    }

    #[test]
    fn kotoba_extension_is_canonical_and_supported() {
        assert_eq!(SUPPORTED_SOURCE_EXTENSIONS.first().copied(), Some("kotoba"));
        assert!(is_supported_source_extension("kotoba"));
        assert!(is_supported_source_path(Path::new("cell.kotoba")));
        assert!(is_supported_source_path(Path::new("cell.clj")));
        assert!(!is_supported_source_path(Path::new("cell.edn")));
    }

    #[test]
    fn profile_manifest_matches_the_rust_contract() {
        let profile = parse_single_map(PROFILE_EDN);
        assert_eq!(
            profile
                .get(&EdnValue::kw("kotoba.lang", "profile-version"))
                .and_then(EdnValue::as_integer),
            Some(1)
        );
        assert_eq!(
            profile
                .get(&EdnValue::kw("kotoba.lang", "default-reader-target"))
                .and_then(keyword_name),
            Some(DEFAULT_READER_TARGET.as_str())
        );
        assert_eq!(
            profile
                .get(&EdnValue::kw("kotoba.lang", "source-extensions"))
                .and_then(EdnValue::as_vector)
                .map(string_vec)
                .unwrap(),
            SUPPORTED_SOURCE_EXTENSIONS
        );

        let targets = profile
            .get(&EdnValue::kw("kotoba.lang", "reader-targets"))
            .and_then(EdnValue::as_map)
            .unwrap();
        for target in [ReaderTarget::Kotoba, ReaderTarget::Clj, ReaderTarget::Cljs] {
            let target_spec = targets
                .get(&EdnValue::kw_bare(target.as_str()))
                .and_then(EdnValue::as_map)
                .unwrap();
            assert_eq!(
                target_spec
                    .get(&EdnValue::kw_bare("reader-branches"))
                    .and_then(EdnValue::as_vector)
                    .map(string_vec)
                    .unwrap(),
                target.reader_branches()
            );
            assert_eq!(
                target_spec
                    .get(&EdnValue::kw_bare("namespace-extension-priority"))
                    .and_then(EdnValue::as_vector)
                    .map(string_vec)
                    .unwrap(),
                target.namespace_extension_priority()
            );
        }

        let authoring = profile
            .get(&EdnValue::kw("kotoba.lang", "authoring-surface"))
            .and_then(EdnValue::as_map)
            .unwrap();
        assert_eq!(
            authoring
                .get(&EdnValue::kw_bare("canonical-extension"))
                .and_then(EdnValue::as_string),
            Some("kotoba")
        );
        assert_eq!(
            authoring
                .get(&EdnValue::kw_bare("portable-extension"))
                .and_then(EdnValue::as_string),
            Some("cljc")
        );
        assert_eq!(
            authoring
                .get(&EdnValue::kw_bare("kotoba-branch"))
                .and_then(EdnValue::as_string),
            Some("kotoba")
        );
    }

    #[test]
    fn coverage_declares_m6_and_all_stage_evidence() {
        let coverage = parse_single_map(COVERAGE_EDN);
        assert_eq!(
            coverage
                .get(&EdnValue::kw("kotoba.lang.coverage", "version"))
                .and_then(EdnValue::as_integer),
            Some(1)
        );
        assert_eq!(
            coverage
                .get(&EdnValue::kw_bare("maturity"))
                .and_then(keyword_name),
            Some("m6")
        );
        let stages = coverage
            .get(&EdnValue::kw_bare("stages"))
            .and_then(EdnValue::as_vector)
            .unwrap();
        let declared = stages
            .iter()
            .map(|stage| {
                stage
                    .as_map()
                    .unwrap()
                    .get(&EdnValue::kw_bare("stage"))
                    .and_then(keyword_name)
                    .unwrap()
            })
            .collect::<Vec<_>>();
        assert_eq!(declared, ["m0", "m1", "m2", "m3", "m4", "m5", "m6"]);

        let m6 = stages
            .iter()
            .map(|stage| stage.as_map().unwrap())
            .find(|stage| {
                stage
                    .get(&EdnValue::kw_bare("stage"))
                    .and_then(keyword_name)
                    == Some("m6")
            })
            .unwrap();
        let evidence = m6
            .get(&EdnValue::kw_bare("evidence"))
            .and_then(EdnValue::as_vector)
            .map(string_vec)
            .unwrap();
        assert!(evidence.contains(&"crates/kotoba-cli/tests/public_cli.rs"));
        assert!(evidence.contains(&"crates/kotoba-cli/src/mesh.rs"));
        assert!(evidence.contains(&"crates/kotoba-cli/src/extension.rs"));
        assert!(evidence.contains(&"crates/kotoba-lattice/src/manifest.rs"));

        let features = coverage
            .get(&EdnValue::kw_bare("features"))
            .and_then(EdnValue::as_vector)
            .unwrap();
        let public_cli = features
            .iter()
            .map(|feature| feature.as_map().unwrap())
            .find(|feature| {
                feature
                    .get(&EdnValue::kw_bare("feature"))
                    .and_then(keyword_name)
                    == Some("public-kotoba-cli-surface")
            })
            .unwrap();
        let positives = public_cli
            .get(&EdnValue::kw_bare("positive"))
            .and_then(EdnValue::as_vector)
            .map(keyword_vec)
            .unwrap();
        for required in [
            "kotoba-eval",
            "kotoba-wasm-build",
            "kotoba-wasm-safe-policy",
            "kotoba-wasm-selfhost-inspect",
            "kotoba-wasm-safe-build",
            "kotoba-wasm-kotoba-namespace-priority",
            "kotoba-wasm-argument-surface",
        ] {
            assert!(positives.contains(&required), "missing {required}");
        }
        let negatives = public_cli
            .get(&EdnValue::kw_bare("negative"))
            .and_then(EdnValue::as_vector)
            .map(keyword_vec)
            .unwrap();
        assert!(negatives.contains(&"legacy-admission-gate-not-public"));

        let component_defaults = features
            .iter()
            .map(|feature| feature.as_map().unwrap())
            .find(|feature| {
                feature
                    .get(&EdnValue::kw_bare("feature"))
                    .and_then(keyword_name)
                    == Some("kotoba-component-and-extension-defaults")
            })
            .unwrap();
        let positives = component_defaults
            .get(&EdnValue::kw_bare("positive"))
            .and_then(EdnValue::as_vector)
            .map(keyword_vec)
            .unwrap();
        for required in [
            "kotoba-component-build-canonical-extension",
            "kotoba-component-clj-family-compatibility",
            "kotoba-app-manifest-kotoba-default",
            "kotoba-extension-artifact-kind",
        ] {
            assert!(positives.contains(&required), "missing {required}");
        }
        let negatives = component_defaults
            .get(&EdnValue::kw_bare("negative"))
            .and_then(EdnValue::as_vector)
            .map(keyword_vec)
            .unwrap();
        assert!(negatives.contains(&"legacy-clojure-default-not-public"));
    }

    #[test]
    fn gates_include_public_cli_component_and_extension_defaults() {
        for command in [
            "cargo test -p kotoba-cli --test public_cli",
            "cargo test -p kotoba-cli wasm_cli_tests",
            "cargo test -p kotoba-cli mesh::tests",
            "cargo test -p kotoba-cli manifest_defaults_to_kotoba_extension_kind_with_clj_compat_host",
            "cargo test -p kotoba-lattice manifest::tests",
            "cargo run -p kotoba-cli -- wasm safe-policy examples/kotoba-shell-hello/src/policy.kotoba",
        ] {
            assert!(
                GATES_MD.contains(command),
                "missing gate command: {command}"
            );
        }
    }

    fn parse_single_map(src: &str) -> std::collections::BTreeMap<EdnValue, EdnValue> {
        let forms = kotoba_edn::parse_all(src).unwrap();
        assert_eq!(forms.len(), 1);
        forms.into_iter().next().unwrap().as_map().unwrap().clone()
    }

    fn keyword_name(v: &EdnValue) -> Option<&str> {
        let kw = v.as_keyword()?;
        if kw.namespace().is_none() {
            Some(kw.name())
        } else {
            None
        }
    }

    fn string_vec(values: &[EdnValue]) -> Vec<&str> {
        values
            .iter()
            .map(|v| v.as_string().unwrap())
            .collect::<Vec<_>>()
    }

    fn keyword_vec(values: &[EdnValue]) -> Vec<&str> {
        values.iter().map(|v| keyword_name(v).unwrap()).collect()
    }
}

//! KOTOBA Mesh app manifest (ADR §7 / §14).
//!
//! The manifest is **EDN** (`kotoba.app.edn`) — the same language family as the
//! components (Clojure via `kotoba-clj`) and the data (Datomic/Datalog). The
//! default component language is **Clojure**: `:lang` omitted ⇒ [`Lang::Clojure`].

use std::collections::BTreeMap;
use std::path::Path;

use kotoba_edn::{EdnValue, Keyword};
use serde::{Deserialize, Serialize};

use crate::error::LatticeError;

/// Component source language. Clojure (`kotoba-clj`) is the default (§14).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Lang {
    /// `.clj` → `kotoba-clj::compile_kais_component_str` (DEFAULT).
    Clojure,
    /// `.rs`  → `cargo component build`.
    Rust,
    /// `.py`  → `componentize-py`.
    Python,
    /// `.js`/`.ts` → `jco componentize`.
    Js,
}

impl Default for Lang {
    fn default() -> Self {
        Lang::Clojure
    }
}

impl Lang {
    /// Parse a `:lang` keyword/string. Empty/unknown handled by caller.
    pub fn from_token(s: &str) -> Result<Lang, LatticeError> {
        match s.trim_start_matches(':') {
            "clojure" | "clj" | "edn" => Ok(Lang::Clojure),
            "rust" | "rs" => Ok(Lang::Rust),
            "python" | "py" => Ok(Lang::Python),
            "js" | "javascript" | "ts" | "typescript" => Ok(Lang::Js),
            other => Err(LatticeError::UnknownLang(other.to_string())),
        }
    }

    /// Infer the language from a source filename extension. Anything that is not
    /// a recognised opt-in extension defaults to Clojure (§14.1).
    pub fn from_ext(path: &str) -> Lang {
        match Path::new(path)
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
        {
            "rs" => Lang::Rust,
            "py" => Lang::Python,
            "js" | "ts" | "mjs" => Lang::Js,
            // ".clj" and everything else → Clojure default
            _ => Lang::Clojure,
        }
    }
}

/// A trigger binding (ADR §8): what causes the host to invoke the component.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TriggerSpec {
    /// "http" | "kse" | "cron" | "datom-delta" | "room".
    pub kind: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub route: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schedule: Option<String>,
}

/// A capability link (ADR §5): CACAO-rooted binding to a capability/provider.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LinkSpec {
    pub target: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub config: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cacao: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ability: Option<String>,
}

/// One component within an app.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentSpec {
    pub name: String,
    #[serde(default)]
    pub lang: Lang,
    /// Source path (e.g. "reply.clj"). Compiled at deploy time → `cid`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub src: Option<String>,
    /// Pre-built artifact CID (set directly, or filled in after compiling src).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cid: Option<String>,
    /// Desired instance count.
    #[serde(default = "default_scale")]
    pub scale: u32,
    #[serde(default)]
    pub triggers: Vec<TriggerSpec>,
    /// Required host-import capabilities (e.g. ["cap/kqe","cap/llm"]).
    #[serde(default)]
    pub requires: Vec<String>,
    #[serde(default)]
    pub links: Vec<LinkSpec>,
}

fn default_scale() -> u32 {
    1
}

/// Placement policy for the whole app.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct Placement {
    /// Label key to spread instances across (e.g. "zone").
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub spread: Option<String>,
    /// Labels every hosting node must match.
    #[serde(default)]
    pub require: BTreeMap<String, String>,
}

/// A KOTOBA Mesh application.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AppManifest {
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(default)]
    pub components: Vec<ComponentSpec>,
    #[serde(default)]
    pub placement: Placement,
}

impl AppManifest {
    /// Parse an EDN manifest (the canonical format, §14).
    pub fn from_edn(src: &str) -> Result<AppManifest, LatticeError> {
        let v = kotoba_edn::parse(src).map_err(|e| LatticeError::Edn(format!("{e:?}")))?;
        let m = map_of(&v).ok_or_else(|| LatticeError::Schema("top-level must be a map".into()))?;

        let name = get_str(m, "kotoba.app/name")
            .ok_or_else(|| LatticeError::Schema("missing :kotoba.app/name".into()))?;
        let version = get_str(m, "kotoba.app/version");

        let components = match get(m, "kotoba.app/components") {
            Some(cs) => items(cs)
                .ok_or_else(|| LatticeError::Schema(":kotoba.app/components must be a seq".into()))?
                .into_iter()
                .map(component_from_edn)
                .collect::<Result<Vec<_>, _>>()?,
            None => Vec::new(),
        };

        let placement = match get(m, "kotoba.app/placement") {
            Some(p) => placement_from_edn(p)?,
            None => Placement::default(),
        };

        Ok(AppManifest {
            name,
            version,
            components,
            placement,
        })
    }

    /// Convenience: parse from a JSON manifest (interop / tests).
    pub fn from_json(src: &str) -> Result<AppManifest, LatticeError> {
        serde_json::from_str(src).map_err(|e| LatticeError::Schema(e.to_string()))
    }

    /// Desired state for the reconciler: component key → desired instance count.
    /// Keyed by artifact CID when known, else a stable `clj:<name>` placeholder
    /// (the CID is filled in once `src` is compiled at deploy time).
    pub fn desired_by_cid(&self) -> BTreeMap<String, u32> {
        let mut out = BTreeMap::new();
        for c in &self.components {
            let key = c
                .cid
                .clone()
                .unwrap_or_else(|| format!("clj:{}", c.name));
            out.insert(key, c.scale);
        }
        out
    }
}

// ── EDN helpers ─────────────────────────────────────────────────────────────

fn map_of(v: &EdnValue) -> Option<&BTreeMap<EdnValue, EdnValue>> {
    match v {
        EdnValue::Map(m) => Some(m),
        _ => None,
    }
}

fn get<'a>(m: &'a BTreeMap<EdnValue, EdnValue>, key: &str) -> Option<&'a EdnValue> {
    m.get(&EdnValue::Keyword(Keyword::parse(key)))
}

/// String view of a scalar EDN node: String / Keyword / Symbol.
fn as_str(v: &EdnValue) -> Option<String> {
    match v {
        EdnValue::String(s) => Some(s.clone()),
        EdnValue::Keyword(k) => Some(k.to_qualified()),
        EdnValue::Symbol(s) => Some(s.to_qualified()),
        _ => None,
    }
}

fn get_str(m: &BTreeMap<EdnValue, EdnValue>, key: &str) -> Option<String> {
    get(m, key).and_then(as_str)
}

/// Iterate Vector / List / Set uniformly.
fn items(v: &EdnValue) -> Option<Vec<&EdnValue>> {
    match v {
        EdnValue::Vector(xs) | EdnValue::List(xs) => Some(xs.iter().collect()),
        EdnValue::Set(xs) => Some(xs.iter().collect()),
        _ => None,
    }
}

fn str_seq(v: &EdnValue) -> Vec<String> {
    items(v)
        .map(|xs| xs.into_iter().filter_map(as_str).collect())
        .unwrap_or_default()
}

fn component_from_edn(v: &EdnValue) -> Result<ComponentSpec, LatticeError> {
    let m = map_of(v).ok_or_else(|| LatticeError::Schema("component must be a map".into()))?;
    let name = get_str(m, "name")
        .ok_or_else(|| LatticeError::Schema("component missing :name".into()))?;

    // :lang omitted ⇒ infer from :src extension ⇒ Clojure default (§14.1).
    let lang = match get_str(m, "lang") {
        Some(tok) => Lang::from_token(&tok)?,
        None => get_str(m, "src").map(|s| Lang::from_ext(&s)).unwrap_or_default(),
    };

    let scale = get(m, "scale")
        .and_then(|x| x.as_integer())
        .map(|i| i.max(0) as u32)
        .unwrap_or(1);

    let triggers = match get(m, "triggers") {
        Some(t) => items(t)
            .unwrap_or_default()
            .into_iter()
            .map(trigger_from_edn)
            .collect::<Result<Vec<_>, _>>()?,
        None => Vec::new(),
    };

    let requires = get(m, "requires").map(str_seq).unwrap_or_default();

    let links = match get(m, "links") {
        Some(l) => items(l)
            .unwrap_or_default()
            .into_iter()
            .map(link_from_edn)
            .collect::<Result<Vec<_>, _>>()?,
        None => Vec::new(),
    };

    Ok(ComponentSpec {
        name,
        lang,
        src: get_str(m, "src"),
        cid: get_str(m, "cid"),
        scale,
        triggers,
        requires,
        links,
    })
}

fn trigger_from_edn(v: &EdnValue) -> Result<TriggerSpec, LatticeError> {
    let m = map_of(v).ok_or_else(|| LatticeError::Schema("trigger must be a map".into()))?;
    let kind = get_str(m, "type")
        .ok_or_else(|| LatticeError::Schema("trigger missing :type".into()))?;
    Ok(TriggerSpec {
        kind,
        route: get_str(m, "route"),
        topic: get_str(m, "topic"),
        schedule: get_str(m, "schedule"),
    })
}

fn link_from_edn(v: &EdnValue) -> Result<LinkSpec, LatticeError> {
    let m = map_of(v).ok_or_else(|| LatticeError::Schema("link must be a map".into()))?;
    let target = get_str(m, "target")
        .ok_or_else(|| LatticeError::Schema("link missing :target".into()))?;
    Ok(LinkSpec {
        target,
        config: get_str(m, "config"),
        cacao: get_str(m, "cacao"),
        ability: get_str(m, "ability"),
    })
}

fn placement_from_edn(v: &EdnValue) -> Result<Placement, LatticeError> {
    let m = map_of(v).ok_or_else(|| LatticeError::Schema("placement must be a map".into()))?;
    let require = match get(m, "require") {
        Some(r) => {
            let rm = map_of(r)
                .ok_or_else(|| LatticeError::Schema(":require must be a map".into()))?;
            rm.iter()
                .filter_map(|(k, val)| Some((as_str(k)?, as_str(val)?)))
                .collect()
        }
        None => BTreeMap::new(),
    };
    Ok(Placement {
        spread: get_str(m, "spread"),
        require,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const APP: &str = r#"
    {:kotoba.app/name    "kotodama-bot"
     :kotoba.app/version "0.3.0"
     :kotoba.app/components
     [{:name "ingest"  :cid "bafyIngest"
       :scale 2 :triggers [{:type :kse :topic "kotoba/mail/in"}]
       :requires #{:cap/kqe :cap/egress}}
      {:name "reply"   :src "reply.clj"
       :scale 1 :triggers [{:type :http :route "/reply"}]
       :requires [:cap/kqe :cap/llm]
       :links [{:target :cap/llm :config "bafyGemma" :cacao "bafyGrant" :ability "infer"}]}]
     :kotoba.app/placement {:spread :zone :require {:tier "edge"}}}
    "#;

    #[test]
    fn parses_edn_manifest() {
        let app = AppManifest::from_edn(APP).unwrap();
        assert_eq!(app.name, "kotodama-bot");
        assert_eq!(app.version.as_deref(), Some("0.3.0"));
        assert_eq!(app.components.len(), 2);
        assert_eq!(app.placement.spread.as_deref(), Some("zone"));
        assert_eq!(app.placement.require.get("tier").map(|s| s.as_str()), Some("edge"));
    }

    #[test]
    fn clojure_is_default_language() {
        let app = AppManifest::from_edn(APP).unwrap();
        // "reply" has :src "reply.clj" and no :lang → Clojure by extension
        let reply = app.components.iter().find(|c| c.name == "reply").unwrap();
        assert_eq!(reply.lang, Lang::Clojure);
        // "ingest" has neither :lang nor :src → Clojure by Default
        let ingest = app.components.iter().find(|c| c.name == "ingest").unwrap();
        assert_eq!(ingest.lang, Lang::Clojure);
    }

    #[test]
    fn requires_set_and_vector_both_parse() {
        let app = AppManifest::from_edn(APP).unwrap();
        let ingest = app.components.iter().find(|c| c.name == "ingest").unwrap();
        assert!(ingest.requires.contains(&"cap/kqe".to_string()));
        assert!(ingest.requires.contains(&"cap/egress".to_string()));
        let reply = app.components.iter().find(|c| c.name == "reply").unwrap();
        assert!(reply.requires.contains(&"cap/llm".to_string()));
    }

    #[test]
    fn triggers_and_links_parse() {
        let app = AppManifest::from_edn(APP).unwrap();
        let reply = app.components.iter().find(|c| c.name == "reply").unwrap();
        assert_eq!(reply.triggers[0].kind, "http");
        assert_eq!(reply.triggers[0].route.as_deref(), Some("/reply"));
        assert_eq!(reply.links[0].target, "cap/llm");
        assert_eq!(reply.links[0].cacao.as_deref(), Some("bafyGrant"));
    }

    #[test]
    fn explicit_lang_overrides_extension() {
        let src = r#"{:kotoba.app/name "x"
                      :kotoba.app/components [{:name "n" :src "a.clj" :lang :rust}]}"#;
        let app = AppManifest::from_edn(src).unwrap();
        assert_eq!(app.components[0].lang, Lang::Rust);
    }

    #[test]
    fn desired_by_cid_uses_cid_then_name_placeholder() {
        let app = AppManifest::from_edn(APP).unwrap();
        let d = app.desired_by_cid();
        assert_eq!(d.get("bafyIngest"), Some(&2)); // ingest had a cid
        assert_eq!(d.get("clj:reply"), Some(&1)); // reply only had src
    }

    #[test]
    fn from_ext_defaults_to_clojure() {
        assert_eq!(Lang::from_ext("foo.clj"), Lang::Clojure);
        assert_eq!(Lang::from_ext("foo"), Lang::Clojure);
        assert_eq!(Lang::from_ext("foo.rs"), Lang::Rust);
        assert_eq!(Lang::from_ext("foo.py"), Lang::Python);
        assert_eq!(Lang::from_ext("foo.ts"), Lang::Js);
    }

    #[test]
    fn lang_from_token_all_aliases_and_unknown() {
        for t in ["clojure", "clj", "edn", ":clojure"] {
            assert_eq!(Lang::from_token(t).unwrap(), Lang::Clojure);
        }
        assert_eq!(Lang::from_token("rs").unwrap(), Lang::Rust);
        assert_eq!(Lang::from_token("python").unwrap(), Lang::Python);
        assert_eq!(Lang::from_token("typescript").unwrap(), Lang::Js);
        assert!(matches!(Lang::from_token("cobol"), Err(LatticeError::UnknownLang(_))));
    }

    #[test]
    fn from_json_parses_and_matches_edn() {
        let json = r#"{
            "name": "j",
            "version": "1.0",
            "components": [
                {"name": "c", "lang": "rust", "cid": "bafyC", "scale": 4,
                 "triggers": [{"kind": "http", "route": "/x"}],
                 "requires": ["cap/kqe"], "links": []}
            ],
            "placement": {"require": {"tier": "edge"}}
        }"#;
        let app = AppManifest::from_json(json).unwrap();
        assert_eq!(app.name, "j");
        assert_eq!(app.components[0].lang, Lang::Rust);
        assert_eq!(app.components[0].scale, 4);
        assert_eq!(app.desired_by_cid().get("bafyC"), Some(&4));
    }

    #[test]
    fn from_json_rejects_garbage() {
        assert!(matches!(
            AppManifest::from_json("not json"),
            Err(LatticeError::Schema(_))
        ));
    }

    #[test]
    fn from_edn_errors_are_descriptive() {
        // top-level not a map
        assert!(matches!(AppManifest::from_edn("[1 2 3]"), Err(LatticeError::Schema(_))));
        // missing :kotoba.app/name
        assert!(matches!(AppManifest::from_edn("{:x 1}"), Err(LatticeError::Schema(_))));
        // components not a seq
        assert!(matches!(
            AppManifest::from_edn(r#"{:kotoba.app/name "a" :kotoba.app/components 5}"#),
            Err(LatticeError::Schema(_))
        ));
        // component missing :name
        assert!(matches!(
            AppManifest::from_edn(r#"{:kotoba.app/name "a" :kotoba.app/components [{:cid "x"}]}"#),
            Err(LatticeError::Schema(_))
        ));
        // trigger missing :type
        assert!(matches!(
            AppManifest::from_edn(
                r#"{:kotoba.app/name "a" :kotoba.app/components [{:name "c" :triggers [{:route "/x"}]}]}"#
            ),
            Err(LatticeError::Schema(_))
        ));
        // link missing :target
        assert!(matches!(
            AppManifest::from_edn(
                r#"{:kotoba.app/name "a" :kotoba.app/components [{:name "c" :links [{:cacao "x"}]}]}"#
            ),
            Err(LatticeError::Schema(_))
        ));
        // unknown :lang
        assert!(matches!(
            AppManifest::from_edn(
                r#"{:kotoba.app/name "a" :kotoba.app/components [{:name "c" :lang :cobol}]}"#
            ),
            Err(LatticeError::UnknownLang(_))
        ));
        // placement :require not a map
        assert!(matches!(
            AppManifest::from_edn(r#"{:kotoba.app/name "a" :kotoba.app/placement {:require 5}}"#),
            Err(LatticeError::Schema(_))
        ));
    }

    #[test]
    fn from_json_uses_serde_defaults() {
        // scale + lang omitted → default_scale() and Lang::default()
        let json = r#"{"name":"j","components":[{"name":"c","cid":"bafyC"}]}"#;
        let app = AppManifest::from_json(json).unwrap();
        assert_eq!(app.components[0].scale, 1);
        assert_eq!(app.components[0].lang, Lang::Clojure);
    }

    #[test]
    fn requires_accepts_bare_symbols() {
        // a `:requires` element written as a bare EDN symbol (not keyword/string)
        let src = r#"{:kotoba.app/name "a"
            :kotoba.app/components [{:name "c" :cid "x" :requires [cap-kqe]}]}"#;
        let app = AppManifest::from_edn(src).unwrap();
        assert!(app.components[0].requires.contains(&"cap-kqe".to_string()));
    }

    #[test]
    fn scale_zero_and_negative_clamp_to_unsigned() {
        let src = r#"{:kotoba.app/name "a" :kotoba.app/components
            [{:name "z" :cid "c0" :scale 0}
             {:name "n" :cid "cn" :scale -5}]}"#;
        let app = AppManifest::from_edn(src).unwrap();
        let d = app.desired_by_cid();
        assert_eq!(d.get("c0"), Some(&0));
        assert_eq!(d.get("cn"), Some(&0)); // negative clamped, never wraps to huge u32
    }

    #[test]
    fn unicode_names_and_cids_roundtrip() {
        let src = r#"{:kotoba.app/name "言葉ボット"
            :kotoba.app/components [{:name "返信器" :cid "bafy言" :scale 2 :requires [:cap/言語]}]}"#;
        let app = AppManifest::from_edn(src).unwrap();
        assert_eq!(app.name, "言葉ボット");
        assert_eq!(app.components[0].name, "返信器");
        assert!(app.components[0].requires.contains(&"cap/言語".to_string()));
        assert_eq!(app.desired_by_cid().get("bafy言"), Some(&2));
    }

    #[test]
    fn wrong_typed_name_is_treated_as_missing() {
        // :kotoba.app/name as a non-stringy value (integer) → as_str None → error
        assert!(matches!(
            AppManifest::from_edn("{:kotoba.app/name 5}"),
            Err(LatticeError::Schema(_))
        ));
    }

    #[test]
    fn placement_without_require_defaults_to_empty() {
        let app = AppManifest::from_edn(
            r#"{:kotoba.app/name "a" :kotoba.app/placement {:spread :zone}}"#,
        )
        .unwrap();
        assert_eq!(app.placement.spread.as_deref(), Some("zone"));
        assert!(app.placement.require.is_empty());
    }

    #[test]
    fn empty_components_default_and_scale_default() {
        let app = AppManifest::from_edn(r#"{:kotoba.app/name "a"}"#).unwrap();
        assert!(app.components.is_empty());
        assert!(app.desired_by_cid().is_empty());
        // scale defaults to 1 when omitted
        let app2 = AppManifest::from_edn(
            r#"{:kotoba.app/name "a" :kotoba.app/components [{:name "c" :cid "x"}]}"#,
        )
        .unwrap();
        assert_eq!(app2.components[0].scale, 1);
    }
}

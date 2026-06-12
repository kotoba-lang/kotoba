//! Manifest — the interchange form of the SSOT (lockfile pattern).
//!
//! Extracted from code (`Root::manifest()`), committed to the repo, and
//! diffed in CI: any diff is a public-API change; removed or changed words
//! are breaking (semver major), added words are additive (minor).

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::word::{ExecutorMeta, WordMode};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Manifest {
    pub version: u32,
    pub root: String,
    pub words: Vec<WordManifest>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct WordManifest {
    pub nsid: String,
    pub description: String,
    pub mode: WordMode,
    pub caps: Vec<String>,
    pub input: Value,
    pub output: Value,
    pub executor: ExecutorMeta,
}

impl Manifest {
    /// Deterministic serialization: words are NSID-sorted by construction
    /// (BTreeMap iteration) and serde_json maps are BTreeMap-backed, so equal
    /// manifests produce byte-equal output.
    pub fn to_canonical_json(&self) -> String {
        serde_json::to_string_pretty(self).expect("manifest serializes")
    }

    pub fn from_json(s: &str) -> anyhow::Result<Manifest> {
        Ok(serde_json::from_str(s)?)
    }

    pub fn diff(&self, new: &Manifest) -> ManifestDiff {
        let old_nsids: Vec<&str> = self.words.iter().map(|w| w.nsid.as_str()).collect();
        let new_nsids: Vec<&str> = new.words.iter().map(|w| w.nsid.as_str()).collect();

        let added = new_nsids
            .iter()
            .filter(|n| !old_nsids.contains(n))
            .map(|n| n.to_string())
            .collect();
        let removed = old_nsids
            .iter()
            .filter(|n| !new_nsids.contains(n))
            .map(|n| n.to_string())
            .collect();
        let changed = self
            .words
            .iter()
            .filter_map(|ow| {
                new.words
                    .iter()
                    .find(|nw| nw.nsid == ow.nsid)
                    .filter(|nw| *nw != ow)
                    .map(|_| ow.nsid.clone())
            })
            .collect();

        ManifestDiff {
            added,
            removed,
            changed,
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct ManifestDiff {
    pub added: Vec<String>,
    pub removed: Vec<String>,
    pub changed: Vec<String>,
}

impl ManifestDiff {
    pub fn is_empty(&self) -> bool {
        self.added.is_empty() && self.removed.is_empty() && self.changed.is_empty()
    }

    /// Removed or changed words break callers; additions don't.
    pub fn is_breaking(&self) -> bool {
        !self.removed.is_empty() || !self.changed.is_empty()
    }

    pub fn summary(&self) -> String {
        let mut lines = Vec::new();
        for n in &self.added {
            lines.push(format!("+ {n}"));
        }
        for n in &self.removed {
            lines.push(format!("- {n} (BREAKING)"));
        }
        for n in &self.changed {
            lines.push(format!("~ {n} (BREAKING: schema/caps/executor changed)"));
        }
        lines.join("\n")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cap::Cap;
    use crate::root::Root;
    use crate::word::{Word, WordMode};
    use schemars::JsonSchema;
    use serde::{Deserialize, Serialize};

    #[derive(Deserialize, Serialize, JsonSchema)]
    struct In {
        x: i64,
    }

    fn root_with(names: &[&str]) -> Root {
        let mut root = Root::new("com.example.word", vec![Cap::Proc("git".into())]).unwrap();
        for n in names {
            let w = Word::closure(
                &format!("com.example.word.{n}"),
                "t",
                WordMode::Query,
                vec![],
                |i: In, _ctx| async move { Ok(i) },
            )
            .unwrap();
            root.register(w).unwrap();
        }
        root
    }

    #[test]
    fn canonical_json_roundtrip_and_stability() {
        let m = root_with(&["b", "a"]).manifest();
        // NSID-sorted regardless of registration order
        assert_eq!(m.words[0].nsid, "com.example.word.a");
        let s1 = m.to_canonical_json();
        let m2 = Manifest::from_json(&s1).unwrap();
        assert_eq!(m, m2);
        assert_eq!(s1, m2.to_canonical_json());
    }

    #[test]
    fn diff_classifies_breaking() {
        let old = root_with(&["a", "b"]).manifest();
        let same = root_with(&["a", "b"]).manifest();
        assert!(old.diff(&same).is_empty());

        let added = root_with(&["a", "b", "c"]).manifest();
        let d = old.diff(&added);
        assert_eq!(d.added, vec!["com.example.word.c"]);
        assert!(!d.is_breaking());

        let removed = root_with(&["a"]).manifest();
        assert!(old.diff(&removed).is_breaking());

        // change a's description → changed → breaking
        let mut changed = root_with(&["a", "b"]).manifest();
        changed.words[0].description = "different".into();
        let d = old.diff(&changed);
        assert_eq!(d.changed, vec!["com.example.word.a"]);
        assert!(d.is_breaking());
    }
}

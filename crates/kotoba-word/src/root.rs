//! Root — where words are planted.
//!
//! Owns a namespace (every word NSID must live under `nsid_root`), holds the
//! capability grants (a word may not request more than the root grants), and
//! runs invocations by handing each word a [`Ctx`] carrying only its own caps.

use std::collections::BTreeMap;
use std::sync::Arc;

use serde_json::Value;

use crate::cap::Cap;
use crate::ctx::Ctx;
use crate::error::WordError;
use crate::manifest::{Manifest, WordManifest};
use crate::word::{validate_nsid, Word};

pub struct Root {
    nsid_root: String,
    grants: Vec<Cap>,
    words: BTreeMap<String, Arc<Word>>,
}

impl Root {
    pub fn new(nsid_root: &str, grants: Vec<Cap>) -> Result<Self, WordError> {
        validate_nsid(nsid_root)?;
        Ok(Self {
            nsid_root: nsid_root.to_string(),
            grants,
            words: BTreeMap::new(),
        })
    }

    pub fn nsid_root(&self) -> &str {
        &self.nsid_root
    }

    pub fn register(&mut self, word: Word) -> Result<(), WordError> {
        if !word.nsid.starts_with(&format!("{}.", self.nsid_root)) {
            return Err(WordError::OutsideRoot {
                nsid: word.nsid.clone(),
                root: self.nsid_root.clone(),
            });
        }
        if self.words.contains_key(&word.nsid) {
            return Err(WordError::Duplicate(word.nsid.clone()));
        }
        for cap in &word.caps {
            if !self.grants.iter().any(|g| g.permits(cap)) {
                return Err(WordError::CapExceedsGrant {
                    nsid: word.nsid.clone(),
                    cap: cap.to_string(),
                });
            }
        }
        self.words.insert(word.nsid.clone(), Arc::new(word));
        Ok(())
    }

    pub fn get(&self, nsid: &str) -> Option<&Arc<Word>> {
        self.words.get(nsid)
    }

    /// Sorted by NSID (BTreeMap order) — keeps every projection deterministic.
    pub fn words(&self) -> impl Iterator<Item = &Arc<Word>> {
        self.words.values()
    }

    pub async fn invoke(&self, nsid: &str, input: Value) -> Result<Value, WordError> {
        let word = self
            .words
            .get(nsid)
            .ok_or_else(|| WordError::NotFound(nsid.to_string()))?;
        let ctx = Ctx::new(word.caps.clone());
        word.invoke(input, ctx).await
    }

    /// Extract the interchange SSOT — commit this, CI-diff it.
    pub fn manifest(&self) -> Manifest {
        Manifest {
            version: 1,
            root: self.nsid_root.clone(),
            words: self
                .words
                .values()
                .map(|w| WordManifest {
                    nsid: w.nsid.clone(),
                    description: w.description.clone(),
                    mode: w.mode,
                    caps: w.caps.iter().map(|c| c.to_string()).collect(),
                    input: w.input_schema.clone(),
                    output: w.output_schema.clone(),
                    executor: w.executor.clone(),
                })
                .collect(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::word::WordMode;
    use schemars::JsonSchema;
    use serde::{Deserialize, Serialize};

    #[derive(Deserialize, Serialize, JsonSchema)]
    struct EchoIn {
        text: String,
    }

    fn echo(nsid: &str, caps: Vec<Cap>) -> Word {
        Word::closure(
            nsid,
            "echo",
            WordMode::Query,
            caps,
            |i: EchoIn, _ctx| async move { Ok(i) },
        )
        .unwrap()
    }

    #[tokio::test]
    async fn register_and_invoke() {
        let mut root = Root::new("com.example.word", vec![]).unwrap();
        root.register(echo("com.example.word.echo", vec![]))
            .unwrap();
        let out = root
            .invoke("com.example.word.echo", serde_json::json!({"text": "hi"}))
            .await
            .unwrap();
        assert_eq!(out["text"], "hi");
        assert!(matches!(
            root.invoke("com.example.word.nope", serde_json::json!({}))
                .await,
            Err(WordError::NotFound(_))
        ));
    }

    #[test]
    fn rejects_outside_namespace_and_dup() {
        let mut root = Root::new("com.example.word", vec![]).unwrap();
        assert!(matches!(
            root.register(echo("org.other.word.echo", vec![])),
            Err(WordError::OutsideRoot { .. })
        ));
        root.register(echo("com.example.word.echo", vec![]))
            .unwrap();
        assert!(matches!(
            root.register(echo("com.example.word.echo", vec![])),
            Err(WordError::Duplicate(_))
        ));
    }

    #[test]
    fn rejects_cap_exceeding_grant() {
        let mut root = Root::new("com.example.word", vec![Cap::Proc("git".into())]).unwrap();
        assert!(root
            .register(echo(
                "com.example.word.gitty",
                vec![Cap::Proc("git".into())]
            ))
            .is_ok());
        assert!(matches!(
            root.register(echo("com.example.word.rmrf", vec![Cap::Proc("rm".into())])),
            Err(WordError::CapExceedsGrant { .. })
        ));
    }
}

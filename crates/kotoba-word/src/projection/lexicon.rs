//! ATProto Lexicon projection — one lexicon doc per word, matching the layout
//! already used under `lexicons/com/etzhayyim/apps/kotoba/`.
//!
//! Mapping:
//! - `WordMode::Procedure` → `type: "procedure"` with JSON-encoded input/output
//! - `WordMode::Query` → `type: "query"` with flat `parameters` when every
//!   top-level input property is a lexicon-legal primitive; otherwise it falls
//!   back to `procedure` (XRPC query params cannot carry nested objects).
//!
//! Caps and executor provenance ride along in the `description` so a reader
//! of the published lexicon can see the word's blast radius without access to
//! the source.

use std::path::{Path, PathBuf};

use serde_json::{json, Map, Value};

use crate::manifest::{Manifest, WordManifest};
use crate::word::WordMode;

/// Can this input schema be expressed as XRPC query `parameters`?
/// (top-level object whose properties are all string/integer/boolean)
fn query_params_compatible(input: &Value) -> bool {
    let Some(props) = input.get("properties").and_then(|p| p.as_object()) else {
        // an empty object schema is trivially compatible
        return input.get("type").and_then(|t| t.as_str()) == Some("object");
    };
    props.values().all(|p| {
        matches!(
            p.get("type").and_then(|t| t.as_str()),
            Some("string") | Some("integer") | Some("boolean")
        )
    })
}

fn described(w: &WordManifest) -> String {
    let caps = if w.caps.is_empty() {
        "none".to_string()
    } else {
        w.caps.join(", ")
    };
    format!(
        "{} [caps: {}] [executor: {:?}:{}]",
        w.description, caps, w.executor.kind, w.executor.reference
    )
}

/// Build the lexicon document for one word.
pub fn lexicon_doc(w: &WordManifest) -> Value {
    let as_query = w.mode == WordMode::Query && query_params_compatible(&w.input);

    let main = if as_query {
        let props = w
            .input
            .get("properties")
            .cloned()
            .unwrap_or(Value::Object(Map::new()));
        let required = w.input.get("required").cloned().unwrap_or(json!([]));
        json!({
            "type": "query",
            "description": described(w),
            "parameters": {
                "type": "params",
                "required": required,
                "properties": props,
            },
            "output": {
                "encoding": "application/json",
                "schema": w.output,
            },
        })
    } else {
        json!({
            "type": "procedure",
            "description": described(w),
            "input": {
                "encoding": "application/json",
                "schema": w.input,
            },
            "output": {
                "encoding": "application/json",
                "schema": w.output,
            },
        })
    };

    json!({
        "lexicon": 1,
        "id": w.nsid,
        "defs": { "main": main },
    })
}

/// `com.etzhayyim.apps.kotoba.word.git.status` →
/// `<out_dir>/com/etzhayyim/apps/kotoba/word/git/status.json`
pub fn lexicon_path(out_dir: &Path, nsid: &str) -> PathBuf {
    let mut p = out_dir.to_path_buf();
    let segs: Vec<&str> = nsid.split('.').collect();
    for seg in &segs[..segs.len() - 1] {
        p.push(seg);
    }
    p.push(format!("{}.json", segs[segs.len() - 1]));
    p
}

/// Write one lexicon file per word. Returns the written paths.
pub fn write_lexicons(manifest: &Manifest, out_dir: &Path) -> anyhow::Result<Vec<PathBuf>> {
    let mut written = Vec::new();
    for w in &manifest.words {
        let path = lexicon_path(out_dir, &w.nsid);
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let doc = lexicon_doc(w);
        std::fs::write(&path, format!("{}\n", serde_json::to_string_pretty(&doc)?))?;
        written.push(path);
    }
    Ok(written)
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
    struct FlatIn {
        name: String,
        count: i64,
    }
    #[derive(Deserialize, Serialize, JsonSchema)]
    struct Nested {
        inner: FlatIn,
    }
    #[derive(Deserialize, Serialize, JsonSchema)]
    struct Out {
        ok: bool,
    }

    fn manifest() -> Manifest {
        let mut root = Root::new("com.example.word", vec![Cap::Proc("git".into())]).unwrap();
        root.register(
            Word::closure(
                "com.example.word.flat.get",
                "flat query",
                WordMode::Query,
                vec![],
                |i: FlatIn, _ctx| async move {
                    Ok(Out {
                        ok: i.count > 0 && !i.name.is_empty(),
                    })
                },
            )
            .unwrap(),
        )
        .unwrap();
        root.register(
            Word::closure(
                "com.example.word.nested.run",
                "nested query falls back to procedure",
                WordMode::Query,
                vec![Cap::Proc("git".into())],
                |_i: Nested, _ctx| async move { Ok(Out { ok: true }) },
            )
            .unwrap(),
        )
        .unwrap();
        root.manifest()
    }

    #[test]
    fn flat_query_projects_as_query() {
        let m = manifest();
        let doc = lexicon_doc(&m.words[0]);
        assert_eq!(doc["id"], "com.example.word.flat.get");
        assert_eq!(doc["defs"]["main"]["type"], "query");
        assert_eq!(
            doc["defs"]["main"]["parameters"]["properties"]["name"]["type"],
            "string"
        );
        assert_eq!(doc["defs"]["main"]["output"]["encoding"], "application/json");
    }

    #[test]
    fn nested_query_falls_back_to_procedure() {
        let m = manifest();
        let doc = lexicon_doc(&m.words[1]);
        assert_eq!(doc["defs"]["main"]["type"], "procedure");
        assert!(doc["defs"]["main"]["description"]
            .as_str()
            .unwrap()
            .contains("proc:git"));
    }

    #[test]
    fn path_layout_matches_repo_convention() {
        let p = lexicon_path(Path::new("lexicons"), "com.etzhayyim.apps.kotoba.word.git.status");
        assert_eq!(
            p,
            Path::new("lexicons/com/etzhayyim/apps/kotoba/word/git/status.json")
        );
    }

    #[test]
    fn write_lexicons_creates_files() {
        let dir = tempfile::tempdir().unwrap();
        let written = write_lexicons(&manifest(), dir.path()).unwrap();
        assert_eq!(written.len(), 2);
        for p in &written {
            let doc: Value =
                serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap();
            assert_eq!(doc["lexicon"], 1);
        }
    }
}

//! Example root — the words the `kotoba word` CLI subcommands serve, and the
//! living demo of all wrapper styles: pure closure, local-app wrap (CLI-
//! Anything principle: call the real software), and web-service wrap.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::cap::Cap;
use crate::error::WordError;
use crate::root::Root;
use crate::word::{ExecutorKind, Word, WordMode};

pub const EXAMPLE_NSID_ROOT: &str = "com.etzhayyim.apps.kotoba.word";

// ── math.add ─────────────────────────────────────────────────────────────────

#[derive(Deserialize, Serialize, JsonSchema)]
pub struct AddInput {
    pub a: f64,
    pub b: f64,
}

#[derive(Deserialize, Serialize, JsonSchema)]
pub struct AddOutput {
    pub sum: f64,
}

// ── text.echo ────────────────────────────────────────────────────────────────

#[derive(Deserialize, Serialize, JsonSchema)]
pub struct EchoInput {
    pub text: String,
}

// ── git.status — local-app wrap ──────────────────────────────────────────────

#[derive(Deserialize, Serialize, JsonSchema)]
pub struct GitStatusInput {
    /// Path to the repository working tree.
    pub dir: String,
}

#[derive(Deserialize, Serialize, JsonSchema)]
pub struct GitStatusOutput {
    pub branch: Option<String>,
    pub clean: bool,
    pub files: Vec<GitFile>,
}

#[derive(Deserialize, Serialize, JsonSchema)]
pub struct GitFile {
    /// Two-letter porcelain status code (e.g. " M", "??").
    pub status: String,
    pub path: String,
}

// ── web.head — web-service wrap ──────────────────────────────────────────────

#[cfg(feature = "http")]
#[derive(Deserialize, Serialize, JsonSchema)]
pub struct WebHeadInput {
    /// URL to fetch. The host must be covered by the word's `net:` cap.
    pub url: String,
}

#[cfg(feature = "http")]
#[derive(Deserialize, Serialize, JsonSchema)]
pub struct WebHeadOutput {
    pub status: u16,
    pub content_type: String,
    pub body_bytes: usize,
}

/// Build the example root. Grants are the union of what its words request.
pub fn example_root() -> Result<Root, WordError> {
    let mut root = Root::new(
        EXAMPLE_NSID_ROOT,
        vec![
            Cap::Proc("git".to_string()),
            Cap::Net("example.com".to_string()),
        ],
    )?;

    root.register(Word::closure(
        &format!("{EXAMPLE_NSID_ROOT}.math.add"),
        "Add two numbers.",
        WordMode::Query,
        vec![],
        |i: AddInput, _ctx| async move { Ok(AddOutput { sum: i.a + i.b }) },
    )?)?;

    root.register(Word::closure(
        &format!("{EXAMPLE_NSID_ROOT}.text.echo"),
        "Echo the input text back.",
        WordMode::Query,
        vec![],
        |i: EchoInput, _ctx| async move { Ok(i) },
    )?)?;

    root.register(
        Word::closure(
            &format!("{EXAMPLE_NSID_ROOT}.git.status"),
            "Structured `git status` of a local repository (wraps the real git binary).",
            WordMode::Query,
            vec![Cap::Proc("git".to_string())],
            |i: GitStatusInput, ctx| async move {
                let out = ctx
                    .exec("git", ["-C", &i.dir, "status", "--porcelain=v1", "-b"])
                    .await?;
                if out.code != 0 {
                    return Err(WordError::Executor(format!(
                        "git exited {}: {}",
                        out.code,
                        out.stderr.trim()
                    )));
                }
                let mut branch = None;
                let mut files = Vec::new();
                for line in out.stdout.lines() {
                    if let Some(rest) = line.strip_prefix("## ") {
                        branch = Some(rest.split("...").next().unwrap_or(rest).to_string());
                    } else if line.len() > 3 {
                        files.push(GitFile {
                            status: line[..2].to_string(),
                            path: line[3..].to_string(),
                        });
                    }
                }
                Ok(GitStatusOutput {
                    branch,
                    clean: files.is_empty(),
                    files,
                })
            },
        )?
        // provenance: this closure delegates to a local process
        .with_executor_meta(ExecutorKind::Process, "git"),
    )?;

    #[cfg(feature = "http")]
    root.register(
        Word::closure(
            &format!("{EXAMPLE_NSID_ROOT}.web.head"),
            "Fetch a URL and report status / content type (host restricted by net cap).",
            WordMode::Query,
            vec![Cap::Net("example.com".to_string())],
            |i: WebHeadInput, ctx| async move {
                let resp = ctx.http_get(&i.url).await?;
                Ok(WebHeadOutput {
                    status: resp.status,
                    content_type: resp.content_type,
                    body_bytes: resp.body.len(),
                })
            },
        )?
        .with_executor_meta(ExecutorKind::Http, "https://example.com"),
    )?;

    Ok(root)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn example_root_builds_and_adds() {
        let root = example_root().unwrap();
        let out = root
            .invoke(
                &format!("{EXAMPLE_NSID_ROOT}.math.add"),
                serde_json::json!({"a": 40.0, "b": 2.0}),
            )
            .await
            .unwrap();
        assert_eq!(out["sum"], 42.0);
    }

    #[tokio::test]
    async fn git_status_word_on_temp_repo() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().to_str().unwrap().to_string();
        let run = |args: &[&str]| {
            std::process::Command::new("git")
                .args(args)
                .output()
                .expect("git available")
        };
        run(&["-C", &path, "init", "-q"]);
        std::fs::write(dir.path().join("hello.txt"), "konnichiwa").unwrap();

        let root = example_root().unwrap();
        let out = root
            .invoke(
                &format!("{EXAMPLE_NSID_ROOT}.git.status"),
                serde_json::json!({"dir": path}),
            )
            .await
            .unwrap();
        assert_eq!(out["clean"], false);
        assert_eq!(out["files"][0]["status"], "??");
        assert_eq!(out["files"][0]["path"], "hello.txt");
    }

    #[cfg(feature = "http")]
    #[tokio::test]
    async fn web_head_denies_uncapped_host() {
        let root = example_root().unwrap();
        let err = root
            .invoke(
                &format!("{EXAMPLE_NSID_ROOT}.web.head"),
                serde_json::json!({"url": "https://attacker.invalid/x"}),
            )
            .await
            .unwrap_err();
        assert!(matches!(err, WordError::CapDenied(_)), "got: {err}");
    }

    #[test]
    fn manifest_covers_all_words() {
        let m = example_root().unwrap().manifest();
        let nsids: Vec<&str> = m.words.iter().map(|w| w.nsid.as_str()).collect();
        assert!(nsids.contains(&"com.etzhayyim.apps.kotoba.word.math.add"));
        assert!(nsids.contains(&"com.etzhayyim.apps.kotoba.word.git.status"));
        // executor provenance recorded for the wrapped local app
        let git = m
            .words
            .iter()
            .find(|w| w.nsid.ends_with("git.status"))
            .unwrap();
        assert_eq!(git.executor.reference, "git");
    }
}

//! Invocation context — the *closure capability model*.
//!
//! A word's body never reaches the OS directly; it receives a [`Ctx`] carrying
//! only the capabilities the word declared (and the root granted). Wrapping a
//! local app means calling [`Ctx::exec`]; wrapping a web service means calling
//! [`Ctx::http_get`]. Both are denied unless covered by a matching [`Cap`].

use serde::{Deserialize, Serialize};

use crate::cap::Cap;
use crate::error::WordError;

#[derive(Clone, Debug, Default)]
pub struct Ctx {
    caps: Vec<Cap>,
}

#[derive(Clone, Debug, Serialize, Deserialize, schemars::JsonSchema)]
pub struct ExecOutput {
    pub stdout: String,
    pub stderr: String,
    pub code: i32,
}

impl Ctx {
    pub fn new(caps: Vec<Cap>) -> Self {
        Self { caps }
    }

    pub fn caps(&self) -> &[Cap] {
        &self.caps
    }

    fn require(&self, want: Cap) -> Result<(), WordError> {
        if self.caps.iter().any(|g| g.permits(&want)) {
            Ok(())
        } else {
            Err(WordError::CapDenied(want.to_string()))
        }
    }

    /// Spawn a local executable (no shell). Requires `proc:<basename>`.
    pub async fn exec<S: AsRef<std::ffi::OsStr>>(
        &self,
        program: &str,
        args: impl IntoIterator<Item = S>,
    ) -> Result<ExecOutput, WordError> {
        let basename = std::path::Path::new(program)
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or(program)
            .to_string();
        self.require(Cap::Proc(basename))?;

        let out = tokio::process::Command::new(program)
            .args(args)
            .kill_on_drop(true)
            .output()
            .await
            .map_err(|e| WordError::Executor(format!("spawn `{program}`: {e}")))?;

        Ok(ExecOutput {
            stdout: String::from_utf8_lossy(&out.stdout).into_owned(),
            stderr: String::from_utf8_lossy(&out.stderr).into_owned(),
            code: out.status.code().unwrap_or(-1),
        })
    }

    /// HTTP GET. Requires `net:<host>` covering the URL's host.
    #[cfg(feature = "http")]
    pub async fn http_get(&self, url: &str) -> Result<HttpOutput, WordError> {
        let parsed: reqwest::Url = url
            .parse()
            .map_err(|e| WordError::Executor(format!("invalid url `{url}`: {e}")))?;
        let host = parsed
            .host_str()
            .ok_or_else(|| WordError::Executor(format!("url `{url}` has no host")))?
            .to_string();
        self.require(Cap::Net(host))?;

        let resp = reqwest::Client::new()
            .get(parsed)
            .send()
            .await
            .map_err(|e| WordError::Executor(format!("http get: {e}")))?;
        let status = resp.status().as_u16();
        let content_type = resp
            .headers()
            .get(reqwest::header::CONTENT_TYPE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or_default()
            .to_string();
        let body = resp
            .text()
            .await
            .map_err(|e| WordError::Executor(format!("http body: {e}")))?;
        Ok(HttpOutput {
            status,
            content_type,
            body,
        })
    }
}

#[cfg(feature = "http")]
#[derive(Clone, Debug, Serialize, Deserialize, schemars::JsonSchema)]
pub struct HttpOutput {
    pub status: u16,
    pub content_type: String,
    pub body: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn exec_denied_without_cap() {
        let ctx = Ctx::new(vec![]);
        let err = ctx.exec("echo", ["hi"]).await.unwrap_err();
        assert!(matches!(err, WordError::CapDenied(_)));
    }

    #[tokio::test]
    async fn exec_allowed_with_cap() {
        let ctx = Ctx::new(vec![Cap::Proc("echo".into())]);
        let out = ctx.exec("echo", ["hello", "kotoba"]).await.unwrap();
        assert_eq!(out.code, 0);
        assert_eq!(out.stdout.trim(), "hello kotoba");
    }

    #[tokio::test]
    async fn exec_cap_checks_basename() {
        // grant is on the basename, so an absolute path to the same binary passes
        let ctx = Ctx::new(vec![Cap::Proc("echo".into())]);
        let out = ctx.exec("/bin/echo", ["x"]).await.unwrap();
        assert_eq!(out.stdout.trim(), "x");
        // ...but a different binary is denied
        assert!(ctx.exec("/bin/cat", ["/etc/hosts"]).await.is_err());
    }
}

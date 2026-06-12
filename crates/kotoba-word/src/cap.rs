//! Capability model — what a word is allowed to reach outside its own input.
//!
//! Grammar (string form, used in manifests and lexicon docs):
//!   proc:<bin>        spawn local executable whose basename is <bin> ("*" = any)
//!   net:<host>        HTTP to exact <host>, or "*.<suffix>" subdomain wildcard
//!   fs:ro:<path>      read under <path> prefix
//!   fs:rw:<path>      read/write under <path> prefix

use std::fmt;
use std::str::FromStr;

use serde::{Deserialize, Serialize};

use crate::error::WordError;

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub enum Cap {
    Proc(String),
    Net(String),
    FsRead(String),
    FsWrite(String),
}

impl Cap {
    /// Does `self` (a grant) permit `want` (a request)?
    pub fn permits(&self, want: &Cap) -> bool {
        match (self, want) {
            (Cap::Proc(g), Cap::Proc(w)) => g == "*" || g == w,
            (Cap::Net(g), Cap::Net(w)) => {
                if g == "*" || g == w {
                    return true;
                }
                // "*.example.com" permits "api.example.com" (and bare "example.com")
                if let Some(suffix) = g.strip_prefix("*.") {
                    return w == suffix || w.ends_with(&format!(".{suffix}"));
                }
                false
            }
            (Cap::FsRead(g), Cap::FsRead(w)) => path_prefix(g, w),
            // an rw grant satisfies both ro and rw requests under its prefix
            (Cap::FsWrite(g), Cap::FsWrite(w)) | (Cap::FsWrite(g), Cap::FsRead(w)) => {
                path_prefix(g, w)
            }
            _ => false,
        }
    }
}

fn path_prefix(grant: &str, want: &str) -> bool {
    let g = grant.trim_end_matches('/');
    want == g || want.starts_with(&format!("{g}/"))
}

impl fmt::Display for Cap {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Cap::Proc(b) => write!(f, "proc:{b}"),
            Cap::Net(h) => write!(f, "net:{h}"),
            Cap::FsRead(p) => write!(f, "fs:ro:{p}"),
            Cap::FsWrite(p) => write!(f, "fs:rw:{p}"),
        }
    }
}

impl FromStr for Cap {
    type Err = WordError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let invalid = || WordError::InvalidCap(s.to_string());
        if let Some(rest) = s.strip_prefix("proc:") {
            if rest.is_empty() {
                return Err(invalid());
            }
            return Ok(Cap::Proc(rest.to_string()));
        }
        if let Some(rest) = s.strip_prefix("net:") {
            if rest.is_empty() {
                return Err(invalid());
            }
            return Ok(Cap::Net(rest.to_string()));
        }
        if let Some(rest) = s.strip_prefix("fs:ro:") {
            if rest.is_empty() {
                return Err(invalid());
            }
            return Ok(Cap::FsRead(rest.to_string()));
        }
        if let Some(rest) = s.strip_prefix("fs:rw:") {
            if rest.is_empty() {
                return Err(invalid());
            }
            return Ok(Cap::FsWrite(rest.to_string()));
        }
        Err(invalid())
    }
}

impl TryFrom<String> for Cap {
    type Error = WordError;
    fn try_from(s: String) -> Result<Self, Self::Error> {
        s.parse()
    }
}

impl From<Cap> for String {
    fn from(c: Cap) -> String {
        c.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_roundtrip() {
        for s in [
            "proc:git",
            "net:example.com",
            "fs:ro:/tmp",
            "fs:rw:/var/data",
        ] {
            let c: Cap = s.parse().unwrap();
            assert_eq!(c.to_string(), s);
        }
        assert!("bogus:x".parse::<Cap>().is_err());
        assert!("proc:".parse::<Cap>().is_err());
    }

    #[test]
    fn proc_permits() {
        let any: Cap = "proc:*".parse().unwrap();
        let git: Cap = "proc:git".parse().unwrap();
        assert!(any.permits(&git));
        assert!(git.permits(&git));
        assert!(!git.permits(&"proc:rm".parse().unwrap()));
    }

    #[test]
    fn net_wildcard_permits() {
        let g: Cap = "net:*.example.com".parse().unwrap();
        assert!(g.permits(&"net:api.example.com".parse().unwrap()));
        assert!(g.permits(&"net:example.com".parse().unwrap()));
        assert!(!g.permits(&"net:evilexample.com".parse().unwrap()));
    }

    #[test]
    fn fs_rw_covers_ro() {
        let g: Cap = "fs:rw:/tmp".parse().unwrap();
        assert!(g.permits(&"fs:ro:/tmp/x".parse().unwrap()));
        assert!(!g.permits(&"fs:ro:/tmpx".parse().unwrap()));
        let ro: Cap = "fs:ro:/tmp".parse().unwrap();
        assert!(!ro.permits(&"fs:rw:/tmp".parse().unwrap()));
    }
}

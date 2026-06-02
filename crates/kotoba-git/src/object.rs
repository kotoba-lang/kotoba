//! Byte-exact git object codec.
//!
//! A git object is `<type> <size>\0<body>` (the *framed* form). Its oid is the
//! SHA-1 of that framing. We model an object as `(kind, body)` where `body` is
//! the uncompressed content **without** the header; framing is then a pure
//! function of `(kind, body)`, so [`GitObject::framed`] is byte-exact by
//! construction and `parse_framed(framed(x)) == x` holds for any object.
//!
//! This module is the fidelity core of the round-trip guarantee and is proven
//! against real `git hash-object` / `git cat-file` vectors in the tests.

use crate::error::GitError;
use crate::oid::GitOid;

/// The four git object kinds.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GitObjectKind {
    Blob,
    Tree,
    Commit,
    Tag,
}

impl GitObjectKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            GitObjectKind::Blob => "blob",
            GitObjectKind::Tree => "tree",
            GitObjectKind::Commit => "commit",
            GitObjectKind::Tag => "tag",
        }
    }

    pub fn from_bytes(s: &[u8]) -> Result<Self, GitError> {
        match s {
            b"blob" => Ok(GitObjectKind::Blob),
            b"tree" => Ok(GitObjectKind::Tree),
            b"commit" => Ok(GitObjectKind::Commit),
            b"tag" => Ok(GitObjectKind::Tag),
            other => Err(GitError::UnknownObjectKind(
                String::from_utf8_lossy(other).into_owned(),
            )),
        }
    }
}

/// A parsed git object: kind + raw uncompressed body (no `<type> <size>\0`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GitObject {
    pub kind: GitObjectKind,
    pub body: Vec<u8>,
}

/// One entry of a tree object: `<mode> <name>\0<20-byte oid>`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TreeEntry {
    /// ASCII octal mode, e.g. `100644`, `40000` (no leading zero for dirs).
    pub mode: Vec<u8>,
    /// File/dir name — raw bytes (git names are not guaranteed UTF-8).
    pub name: Vec<u8>,
    pub oid: GitOid,
}

impl GitObject {
    pub fn new(kind: GitObjectKind, body: Vec<u8>) -> Self {
        Self { kind, body }
    }

    pub fn blob(body: Vec<u8>) -> Self {
        Self::new(GitObjectKind::Blob, body)
    }

    /// Build a tree object from entries (entries are serialized in the order
    /// given — callers wanting git's canonical layout must pre-sort).
    pub fn tree(entries: &[TreeEntry]) -> Self {
        let mut body = Vec::new();
        for e in entries {
            body.extend_from_slice(&e.mode);
            body.push(b' ');
            body.extend_from_slice(&e.name);
            body.push(0);
            body.extend_from_slice(e.oid.raw());
        }
        Self::new(GitObjectKind::Tree, body)
    }

    /// The framed object bytes: `<type> <size>\0<body>`.
    pub fn framed(&self) -> Vec<u8> {
        let header = format!("{} {}\0", self.kind.as_str(), self.body.len());
        let mut out = Vec::with_capacity(header.len() + self.body.len());
        out.extend_from_slice(header.as_bytes());
        out.extend_from_slice(&self.body);
        out
    }

    /// The git oid (SHA-1 of the framed bytes).
    pub fn oid(&self) -> GitOid {
        GitOid::of_framed(&self.framed())
    }

    /// Parse framed object bytes (`<type> <size>\0<body>`).
    pub fn parse_framed(framed: &[u8]) -> Result<Self, GitError> {
        let space = framed
            .iter()
            .position(|&b| b == b' ')
            .ok_or(GitError::MalformedHeader)?;
        let nul = framed
            .iter()
            .position(|&b| b == 0)
            .ok_or(GitError::MalformedHeader)?;
        if nul < space {
            return Err(GitError::MalformedHeader);
        }
        let kind = GitObjectKind::from_bytes(&framed[..space])?;
        let size_str =
            std::str::from_utf8(&framed[space + 1..nul]).map_err(|_| GitError::MalformedHeader)?;
        let size: usize = size_str.parse().map_err(|_| GitError::MalformedHeader)?;
        let body = framed[nul + 1..].to_vec();
        if body.len() != size {
            return Err(GitError::SizeMismatch {
                declared: size,
                actual: body.len(),
            });
        }
        Ok(Self { kind, body })
    }

    /// Parse the body of a tree object into entries.
    pub fn tree_entries(&self) -> Result<Vec<TreeEntry>, GitError> {
        if self.kind != GitObjectKind::Tree {
            return Err(GitError::WrongKind {
                expected: "tree",
                actual: self.kind.as_str(),
            });
        }
        let b = &self.body;
        let mut entries = Vec::new();
        let mut i = 0;
        while i < b.len() {
            let space = b[i..]
                .iter()
                .position(|&x| x == b' ')
                .map(|p| p + i)
                .ok_or(GitError::MalformedTree)?;
            let mode = b[i..space].to_vec();
            let nul = b[space + 1..]
                .iter()
                .position(|&x| x == 0)
                .map(|p| p + space + 1)
                .ok_or(GitError::MalformedTree)?;
            let name = b[space + 1..nul].to_vec();
            let oid_start = nul + 1;
            let oid_end = oid_start + 20;
            if oid_end > b.len() {
                return Err(GitError::MalformedTree);
            }
            let oid = GitOid::from_raw(&b[oid_start..oid_end])?;
            entries.push(TreeEntry { mode, name, oid });
            i = oid_end;
        }
        Ok(entries)
    }

    /// Split a commit/tag body into `(header_bytes, message_bytes)` at the first
    /// blank line (`\n\n`). The header excludes the separating blank line; the
    /// message is everything after it. If there is no blank line, the whole body
    /// is the header and the message is empty.
    pub fn split_header_message(&self) -> (&[u8], &[u8]) {
        match find_subslice(&self.body, b"\n\n") {
            Some(idx) => (&self.body[..idx], &self.body[idx + 2..]),
            None => (&self.body[..], &[]),
        }
    }

    /// Parse the leading simple `key value` headers of a commit/tag body.
    ///
    /// Continuation lines (starting with a space, e.g. multi-line `gpgsig`) are
    /// appended to the previous header's value with a newline. This is a
    /// *queryable projection*; the lossless form is always the framed block.
    pub fn header_fields(&self) -> Vec<(String, String)> {
        let (header, _msg) = self.split_header_message();
        let text = String::from_utf8_lossy(header);
        let mut out: Vec<(String, String)> = Vec::new();
        for line in text.split('\n') {
            if let Some(rest) = line.strip_prefix(' ') {
                // continuation of previous header
                if let Some(last) = out.last_mut() {
                    last.1.push('\n');
                    last.1.push_str(rest);
                }
                continue;
            }
            if let Some((k, v)) = line.split_once(' ') {
                out.push((k.to_string(), v.to_string()));
            } else if !line.is_empty() {
                out.push((line.to_string(), String::new()));
            }
        }
        out
    }

    /// First header value matching `key` (e.g. `tree`, `author`, `object`).
    pub fn header_value(&self, key: &str) -> Option<String> {
        self.header_fields()
            .into_iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v)
    }

    /// All header values matching `key` (e.g. multiple `parent` lines).
    pub fn header_values(&self, key: &str) -> Vec<String> {
        self.header_fields()
            .into_iter()
            .filter(|(k, _)| k == key)
            .map(|(_, v)| v)
            .collect()
    }
}

fn find_subslice(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || haystack.len() < needle.len() {
        return None;
    }
    haystack
        .windows(needle.len())
        .position(|w| w == needle)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blob_framed_and_oid() {
        let obj = GitObject::blob(b"hello\n".to_vec());
        assert_eq!(obj.framed(), b"blob 6\0hello\n");
        assert_eq!(
            obj.oid().to_hex(),
            "ce013625030ba8dba906f756967f9e9ca394464a"
        );
    }

    #[test]
    fn parse_framed_roundtrips() {
        for body in [
            b"hello\n".to_vec(),
            Vec::new(),
            vec![0u8, 1, 2, 255, 254],
        ] {
            let obj = GitObject::blob(body);
            let framed = obj.framed();
            let parsed = GitObject::parse_framed(&framed).unwrap();
            assert_eq!(obj, parsed);
            assert_eq!(parsed.framed(), framed);
        }
    }

    #[test]
    fn tree_oid_matches_git() {
        // Authoritative tree from a repo with a single `f.txt` -> hello blob.
        // `git ls-tree` -> 100644 blob ce0136...  f.txt
        // expected tree oid: b4ed918248039b78f24383523fa4e51f80994fac
        let blob_oid = GitOid::from_hex("ce013625030ba8dba906f756967f9e9ca394464a").unwrap();
        let tree = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob_oid,
        }]);
        assert_eq!(
            tree.oid().to_hex(),
            "b4ed918248039b78f24383523fa4e51f80994fac"
        );
    }

    #[test]
    fn tree_entries_roundtrip() {
        let blob_oid = GitOid::from_hex("ce013625030ba8dba906f756967f9e9ca394464a").unwrap();
        let entries = vec![TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob_oid,
        }];
        let tree = GitObject::tree(&entries);
        assert_eq!(tree.tree_entries().unwrap(), entries);
        // re-serialize from parsed entries must reproduce identical body
        assert_eq!(GitObject::tree(&tree.tree_entries().unwrap()), tree);
    }

    #[test]
    fn commit_oid_matches_git() {
        // Authoritative commit (size 120) from the fixture repo.
        let body = b"tree b4ed918248039b78f24383523fa4e51f80994fac\n\
author t <t@t> 1700000000 +0000\n\
committer t <t@t> 1700000000 +0000\n\
\n\
first\n"
            .to_vec();
        let commit = GitObject::new(GitObjectKind::Commit, body);
        assert_eq!(commit.body.len(), 120);
        assert_eq!(
            commit.oid().to_hex(),
            "ef01bd2630efea35165770fd32ee509f62459ce3"
        );
    }

    #[test]
    fn commit_header_parsing() {
        let body = b"tree b4ed918248039b78f24383523fa4e51f80994fac\n\
parent 1111111111111111111111111111111111111111\n\
parent 2222222222222222222222222222222222222222\n\
author t <t@t> 1700000000 +0000\n\
committer t <t@t> 1700000000 +0000\n\
\n\
first\n"
            .to_vec();
        let commit = GitObject::new(GitObjectKind::Commit, body);
        assert_eq!(
            commit.header_value("tree").as_deref(),
            Some("b4ed918248039b78f24383523fa4e51f80994fac")
        );
        assert_eq!(commit.header_values("parent").len(), 2);
        let (_, msg) = commit.split_header_message();
        assert_eq!(msg, b"first\n");
    }

    #[test]
    fn split_header_message_no_blank_line() {
        let obj = GitObject::new(GitObjectKind::Commit, b"tree abc".to_vec());
        let (h, m) = obj.split_header_message();
        assert_eq!(h, b"tree abc");
        assert_eq!(m, b"");
    }
}

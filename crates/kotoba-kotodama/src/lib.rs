pub const CANONICAL_REPOSITORIES: &[(&str, &str)] = &[
    ("inference", "https://github.com/kotoba-lang/inference"),
    ("host", "https://github.com/kotoba-lang/kotodama-host"),
    ("mcp", "https://github.com/kotoba-lang/kotodama-mcp"),
    ("cells", "https://github.com/kotoba-lang/kotodama-cells"),
    ("py", "https://github.com/kotoba-lang/kotodama-py"),
    (
        "holochain",
        "https://github.com/kotoba-lang/kotodama-holochain",
    ),
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn includes_host_redirect() {
        assert!(CANONICAL_REPOSITORIES
            .iter()
            .any(|(name, url)| *name == "host" && url.ends_with("/kotodama-host")));
    }
}

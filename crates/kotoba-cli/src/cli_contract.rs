use anyhow::{Context, Result};
use kotoba_edn::{EdnValue, Keyword};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

pub const CLI_CONTRACT_EDN: &str = include_str!("../resources/kotoba/lang/cli.edn");
pub const CLI_CONTRACT_SOURCE: &str = "kotoba-lang/kotoba-lang:lang/cli.edn";

const REQUIRED_COMMANDS: &[&str] = &["run", "check", "db", "git", "rad", "deploy"];

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ContractSummary {
    pub source: &'static str,
    pub version: i64,
    pub commands: Vec<String>,
    pub command_count: usize,
    pub option_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ContractCheck {
    pub ok: bool,
    pub summary: ContractSummary,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ContractConformance {
    pub ok: bool,
    pub source: &'static str,
    pub contract_commands: Vec<String>,
    pub host_commands: Vec<String>,
    pub implemented_contract_commands: Vec<String>,
    pub missing_contract_commands: Vec<String>,
    pub extra_host_commands: Vec<String>,
}

#[derive(clap::Subcommand)]
pub enum ContractCmd {
    /// Validate the bundled kotoba-lang CLI command contract.
    Check {
        /// Emit JSON instead of a human-readable line.
        #[arg(long)]
        json: bool,
    },
    /// Print the bundled EDN contract snapshot.
    Print,
    /// Compare the bundled contract with this host CLI's top-level commands.
    Conformance {
        /// Emit JSON instead of a human-readable line.
        #[arg(long)]
        json: bool,
        /// Exit non-zero when the host CLI does not implement every contract command.
        #[arg(long)]
        strict: bool,
    },
}

pub fn run(cmd: ContractCmd, host_commands: &[String]) -> Result<()> {
    match cmd {
        ContractCmd::Check { json } => {
            let check = check()?;
            if json {
                println!("{}", serde_json::to_string_pretty(&check)?);
            } else {
                println!(
                    "ok {} version {} commands {} options {}",
                    check.summary.source,
                    check.summary.version,
                    check.summary.command_count,
                    check.summary.option_count
                );
            }
            Ok(())
        }
        ContractCmd::Print => {
            print!("{CLI_CONTRACT_EDN}");
            Ok(())
        }
        ContractCmd::Conformance { json, strict } => {
            let report = conformance(host_commands)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&report)?);
            } else {
                println!(
                    "{} {} contract_commands={} implemented={} missing={} extra_host={}",
                    if report.ok { "ok" } else { "pending" },
                    report.source,
                    report.contract_commands.len(),
                    report.implemented_contract_commands.len(),
                    report.missing_contract_commands.len(),
                    report.extra_host_commands.len()
                );
                if !report.missing_contract_commands.is_empty() {
                    println!("missing: {}", report.missing_contract_commands.join(", "));
                }
            }
            if strict && !report.ok {
                anyhow::bail!(
                    "host CLI is missing contract commands: {}",
                    report.missing_contract_commands.join(", ")
                );
            }
            Ok(())
        }
    }
}

pub fn check() -> Result<ContractCheck> {
    let value = kotoba_edn::parse(CLI_CONTRACT_EDN).context("parse bundled CLI contract EDN")?;
    let root = value.as_map().context("CLI contract root must be a map")?;
    let version = required_int(root, "kotoba.cli.contract/version")?;
    if version <= 0 {
        anyhow::bail!("CLI contract version must be positive, got {version}");
    }

    let tier_labels = required_map(root, "kotoba.cli.contract/tier-labels")?;
    let option_types = required_map(root, "kotoba.cli.contract/option-types")?;
    let commands = required_vector(root, "kotoba.cli.contract/commands")?;
    let mut command_ids = BTreeSet::new();
    let mut command_names = Vec::with_capacity(commands.len());
    let mut option_count = 0usize;

    for command in commands {
        let command = command
            .as_map()
            .context("each CLI contract command must be a map")?;
        let id = required_keyword_name(command, "id")?;
        let tier = required_keyword_name(command, "tier")?;
        if !tier_labels.contains_key(&kw_bare(&tier)) {
            anyhow::bail!("command :{id} uses unknown tier :{tier}");
        }
        required_string(command, "summary")?;
        if !command_ids.insert(id.clone()) {
            anyhow::bail!("duplicate command id :{id}");
        }
        command_names.push(id.clone());

        if let Some(subcommands) = optional_vector(command, "subcommands")? {
            if subcommands.is_empty() {
                anyhow::bail!("command :{id} has empty :subcommands");
            }
            for subcommand in subcommands {
                subcommand
                    .as_keyword()
                    .with_context(|| format!("command :{id} subcommand must be keyword"))?;
            }
        }

        if let Some(positionals) = optional_vector(command, "positionals")? {
            for positional in positionals {
                let positional = positional
                    .as_map()
                    .with_context(|| format!("command :{id} positional must be map"))?;
                required_keyword_name(positional, "id")?;
                let ty = required_keyword_name(positional, "type")?;
                if !option_types.contains_key(&kw_bare(&ty)) {
                    anyhow::bail!("command :{id} positional uses unknown type :{ty}");
                }
            }
        }

        let options = required_vector(command, "options")?;
        option_count += options.len();
        let mut option_ids = BTreeSet::new();
        let mut option_flags = BTreeSet::new();
        for option in options {
            let option = option
                .as_map()
                .with_context(|| format!("command :{id} option must be map"))?;
            let option_id = required_keyword_name(option, "id")?;
            if !option_ids.insert(option_id.clone()) {
                anyhow::bail!("command :{id} has duplicate option :{option_id}");
            }
            let ty = required_keyword_name(option, "type")?;
            if !option_types.contains_key(&kw_bare(&ty)) {
                anyhow::bail!("command :{id} option :{option_id} uses unknown type :{ty}");
            }
            let flags = required_vector(option, "flags")?;
            if flags.is_empty() {
                anyhow::bail!("command :{id} option :{option_id} has empty :flags");
            }
            for flag in flags {
                let flag = flag.as_string().with_context(|| {
                    format!("command :{id} option :{option_id} flag must be string")
                })?;
                if !flag.starts_with('-') {
                    anyhow::bail!("command :{id} option :{option_id} invalid flag {flag:?}");
                }
                if !option_flags.insert(flag.to_string()) {
                    anyhow::bail!("command :{id} has duplicate option flag {flag}");
                }
            }
            if ty == "enum" {
                let values = required_vector(option, "values")?;
                if values.is_empty() {
                    anyhow::bail!("command :{id} option :{option_id} enum has empty :values");
                }
                for value in values {
                    value.as_keyword().with_context(|| {
                        format!("command :{id} option :{option_id} enum value must be keyword")
                    })?;
                }
            }
        }
    }

    let expected: BTreeSet<String> = REQUIRED_COMMANDS.iter().map(|s| s.to_string()).collect();
    if command_ids != expected {
        anyhow::bail!(
            "CLI contract command set mismatch: expected {:?}, got {:?}",
            expected,
            command_ids
        );
    }

    Ok(ContractCheck {
        ok: true,
        summary: ContractSummary {
            source: CLI_CONTRACT_SOURCE,
            version,
            commands: command_names,
            command_count: commands.len(),
            option_count,
        },
    })
}

pub fn conformance(host_commands: &[String]) -> Result<ContractConformance> {
    let contract = check()?;
    let contract_commands: BTreeSet<String> = contract.summary.commands.iter().cloned().collect();
    let host_commands_set: BTreeSet<String> = host_commands.iter().cloned().collect();
    let implemented_contract_commands = contract_commands
        .intersection(&host_commands_set)
        .cloned()
        .collect::<Vec<_>>();
    let missing_contract_commands = contract_commands
        .difference(&host_commands_set)
        .cloned()
        .collect::<Vec<_>>();
    let extra_host_commands = host_commands_set
        .difference(&contract_commands)
        .filter(|command| command.as_str() != "contract")
        .cloned()
        .collect::<Vec<_>>();

    Ok(ContractConformance {
        ok: missing_contract_commands.is_empty(),
        source: CLI_CONTRACT_SOURCE,
        contract_commands: contract.summary.commands,
        host_commands: host_commands_set.into_iter().collect(),
        implemented_contract_commands,
        missing_contract_commands,
        extra_host_commands,
    })
}

fn kw_bare(name: &str) -> EdnValue {
    EdnValue::Keyword(Keyword::bare(name))
}

fn kw(path: &str) -> EdnValue {
    EdnValue::Keyword(Keyword::parse(path))
}

fn required<'a>(map: &'a BTreeMap<EdnValue, EdnValue>, key: &str) -> Result<&'a EdnValue> {
    map.get(&kw(key))
        .with_context(|| format!("missing required key :{key}"))
}

fn required_map<'a>(
    map: &'a BTreeMap<EdnValue, EdnValue>,
    key: &str,
) -> Result<&'a BTreeMap<EdnValue, EdnValue>> {
    required(map, key)?
        .as_map()
        .with_context(|| format!(":{key} must be a map"))
}

fn required_vector<'a>(map: &'a BTreeMap<EdnValue, EdnValue>, key: &str) -> Result<&'a [EdnValue]> {
    required(map, key)?
        .as_vector()
        .with_context(|| format!(":{key} must be a vector"))
}

fn optional_vector<'a>(
    map: &'a BTreeMap<EdnValue, EdnValue>,
    key: &str,
) -> Result<Option<&'a [EdnValue]>> {
    map.get(&kw(key))
        .map(|v| {
            v.as_vector()
                .with_context(|| format!(":{key} must be a vector"))
        })
        .transpose()
}

fn required_int(map: &BTreeMap<EdnValue, EdnValue>, key: &str) -> Result<i64> {
    required(map, key)?
        .as_integer()
        .with_context(|| format!(":{key} must be an integer"))
}

fn required_string<'a>(map: &'a BTreeMap<EdnValue, EdnValue>, key: &str) -> Result<&'a str> {
    required(map, key)?
        .as_string()
        .with_context(|| format!(":{key} must be a string"))
}

fn required_keyword_name(map: &BTreeMap<EdnValue, EdnValue>, key: &str) -> Result<String> {
    let keyword = required(map, key)?
        .as_keyword()
        .with_context(|| format!(":{key} must be a keyword"))?;
    Ok(keyword.to_qualified())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_contract_validates() {
        let check = check().expect("bundled CLI contract validates");
        assert!(check.ok);
        assert_eq!(check.summary.version, 1);
        assert_eq!(check.summary.command_count, 6);
        assert_eq!(check.summary.option_count, 33);
        assert_eq!(
            check.summary.commands,
            ["run", "check", "db", "git", "rad", "deploy"]
        );
    }

    #[test]
    fn conformance_reports_missing_host_commands() {
        let host_commands = vec![
            "contract".to_string(),
            "run".to_string(),
            "check".to_string(),
        ];
        let report = conformance(&host_commands).expect("conformance report");
        assert!(!report.ok);
        assert_eq!(report.implemented_contract_commands, ["check", "run"]);
        assert_eq!(
            report.missing_contract_commands,
            ["db", "deploy", "git", "rad"]
        );
        assert!(report.extra_host_commands.is_empty());
    }
}

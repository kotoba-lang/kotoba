//! Clojure source compatibility helpers that run before the EDN reader.
//!
//! This is deliberately a loader layer, not a second Clojure compiler. It
//! normalizes source features that decide which forms the existing kotoba-clj
//! compiler should see.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::{Path, PathBuf};

use kotoba_edn::{parse_all, to_string, EdnValue, Symbol};

use crate::CljError;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReaderTarget {
    Kotoba,
    Clj,
    Cljs,
}

impl ReaderTarget {
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "kotoba" => Some(Self::Kotoba),
            "clj" => Some(Self::Clj),
            "cljs" => Some(Self::Cljs),
            _ => None,
        }
    }

    fn branch_names(self) -> &'static [&'static str] {
        match self {
            Self::Kotoba => &["kotoba", "clj", "default"],
            Self::Clj => &["clj", "default"],
            Self::Cljs => &["cljs", "default"],
        }
    }
}

pub fn normalize_source(src: &str, target: ReaderTarget) -> Result<String, CljError> {
    let src = expand_discard_syntax(src)?;
    let src = expand_metadata_syntax(&src)?;
    let src = expand_var_quote_syntax(&src)?;
    let src = expand_quote_syntax(&src)?;
    let src = expand_reader_conditionals(&src, target)?;
    qualify_source(&src)
}

pub fn load_file_graph(path: &Path, target: ReaderTarget) -> Result<String, CljError> {
    load_file_graph_with_source_paths(path, target, &[])
}

pub fn load_file_graph_with_source_paths(
    path: &Path,
    target: ReaderTarget,
    source_paths: &[PathBuf],
) -> Result<String, CljError> {
    let roots = source_roots(path, source_paths)?;
    let mut seen = HashSet::new();
    let mut exports = HashMap::new();
    let mut out = Vec::new();
    load_file_graph_inner(
        path,
        &roots,
        target,
        false,
        &mut seen,
        &mut exports,
        &mut out,
    )?;
    Ok(out.join("\n"))
}

fn load_file_graph_inner(
    path: &Path,
    roots: &[PathBuf],
    target: ReaderTarget,
    qualify_defs: bool,
    seen: &mut HashSet<PathBuf>,
    exports: &mut HashMap<String, HashSet<String>>,
    out: &mut Vec<String>,
) -> Result<(), CljError> {
    let key = path.canonicalize().unwrap_or_else(|_| path.to_path_buf());
    if !seen.insert(key) {
        return Ok(());
    }

    let raw = std::fs::read_to_string(path)
        .map_err(|e| CljError::Read(format!("read {}: {e}", path.display())))?;
    let stripped = strip_shebang(&raw);
    let without_discards = expand_discard_syntax(stripped)?;
    let without_metadata = expand_metadata_syntax(&without_discards)?;
    let var_quoted = expand_var_quote_syntax(&without_metadata)?;
    let quoted = expand_quote_syntax(&var_quoted)?;
    let expanded = expand_reader_conditionals(&quoted, target)?;
    let forms = parse_all(&expanded).map_err(|e| CljError::Read(e.to_string()))?;
    for ns in required_namespaces(&forms) {
        let dep = resolve_namespace(roots, &ns, target).ok_or_else(|| {
            CljError::Read(format!(
                "could not resolve required namespace `{ns}` from source paths: {}",
                roots
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect::<Vec<_>>()
                    .join(":")
            ))
        })?;
        load_file_graph_inner(&dep, roots, target, true, seen, exports, out)?;
    }
    if let Some(ns) = namespace_name(&forms) {
        exports.insert(ns, exported_names(&forms));
    }
    out.push(qualify_forms(forms, qualify_defs, exports)?);
    Ok(())
}

fn source_roots(entry: &Path, explicit: &[PathBuf]) -> Result<Vec<PathBuf>, CljError> {
    let mut roots = Vec::new();
    roots.push(
        entry
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .to_path_buf(),
    );
    roots.extend(deps_edn_source_roots(entry)?);
    roots.extend(explicit.iter().cloned());
    if let Some(env_paths) = std::env::var_os("KOTOBA_CLJ_PATH") {
        roots.extend(std::env::split_paths(&env_paths));
    }

    let mut seen = HashSet::new();
    Ok(roots
        .into_iter()
        .filter(|p| seen.insert(p.clone()))
        .collect())
}

fn deps_edn_source_roots(entry: &Path) -> Result<Vec<PathBuf>, CljError> {
    let Some(path) = find_deps_edn(entry) else {
        return Ok(Vec::new());
    };
    let dir = path.parent().unwrap_or_else(|| Path::new("."));
    let src = std::fs::read_to_string(&path)
        .map_err(|e| CljError::Read(format!("read {}: {e}", path.display())))?;
    let forms = parse_all(&src).map_err(|e| {
        CljError::Read(format!(
            "parse {} for :paths source roots: {e}",
            path.display()
        ))
    })?;
    let Some(EdnValue::Map(m)) = forms.first() else {
        return Ok(Vec::new());
    };
    let Some(EdnValue::Vector(paths)) = m.get(&EdnValue::kw_bare("paths")) else {
        return Ok(Vec::new());
    };
    Ok(paths
        .iter()
        .filter_map(|v| v.as_string())
        .map(|p| dir.join(p))
        .collect())
}

fn find_deps_edn(entry: &Path) -> Option<PathBuf> {
    let mut dir = entry.parent().unwrap_or_else(|| Path::new("."));
    loop {
        let candidate = dir.join("deps.edn");
        if candidate.exists() {
            return Some(candidate);
        }
        dir = dir.parent()?;
    }
}

fn strip_shebang(src: &str) -> &str {
    if let Some(rest) = src.strip_prefix("#!") {
        match rest.find('\n') {
            Some(i) => &rest[i + 1..],
            None => "",
        }
    } else {
        src
    }
}

fn resolve_namespace(roots: &[PathBuf], ns: &str, target: ReaderTarget) -> Option<PathBuf> {
    let rel = ns
        .split('.')
        .map(|segment| segment.replace('-', "_"))
        .collect::<Vec<_>>()
        .join("/");
    let extensions = match target {
        ReaderTarget::Kotoba => ["kotoba", "cljc", "clj", "cljs"],
        ReaderTarget::Clj => ["cljc", "clj", "kotoba", "cljs"],
        ReaderTarget::Cljs => ["cljc", "cljs", "clj", "kotoba"],
    };
    roots.iter().find_map(|root| {
        extensions
            .iter()
            .map(|ext| root.join(format!("{rel}.{ext}")))
            .find(|p| p.exists())
    })
}

fn qualify_source(src: &str) -> Result<String, CljError> {
    let forms = parse_all(src).map_err(|e| CljError::Read(e.to_string()))?;
    qualify_forms(forms, false, &HashMap::new())
}

fn qualify_forms(
    forms: Vec<EdnValue>,
    qualify_defs: bool,
    exports: &HashMap<String, HashSet<String>>,
) -> Result<String, CljError> {
    let ctx = NamespaceCtx::from_forms(&forms, exports);
    let forms = forms
        .into_iter()
        .map(|form| qualify_top_level(form, &ctx, qualify_defs))
        .collect::<Vec<_>>();
    Ok(forms.iter().map(to_string).collect::<Vec<_>>().join("\n"))
}

fn expand_reader_conditionals(src: &str, target: ReaderTarget) -> Result<String, CljError> {
    let bytes = src.as_bytes();
    let mut out = String::with_capacity(src.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                let end = skip_string(src, i)?;
                out.push_str(&src[i..end]);
                i = end;
            }
            b';' => {
                let end = skip_comment(src, i);
                out.push_str(&src[i..end]);
                i = end;
            }
            b'#' if bytes.get(i + 1) == Some(&b'?') => {
                let (splicing, open) = if bytes.get(i + 2) == Some(&b'@') {
                    (true, i + 3)
                } else {
                    (false, i + 2)
                };
                if bytes.get(open) != Some(&b'(') {
                    out.push(bytes[i] as char);
                    i += 1;
                    continue;
                }
                let close = find_matching(src, open)?;
                let inner = &src[open + 1..close];
                let selected = select_reader_branch(inner, target)?;
                match selected {
                    Some(value) if splicing => out.push_str(&splice_value(&value)),
                    Some(value) => out.push_str(&to_string(&value)),
                    None if splicing => {}
                    None => out.push_str("nil"),
                }
                i = close + 1;
            }
            _ => {
                let ch = src[i..].chars().next().expect("valid char boundary");
                out.push(ch);
                i += ch.len_utf8();
            }
        }
    }
    Ok(out)
}

fn expand_var_quote_syntax(src: &str) -> Result<String, CljError> {
    let bytes = src.as_bytes();
    let mut out = String::with_capacity(src.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                let end = skip_string(src, i)?;
                out.push_str(&src[i..end]);
                i = end;
            }
            b';' => {
                let end = skip_comment(src, i);
                out.push_str(&src[i..end]);
                i = end;
            }
            b'#' if bytes.get(i + 1) == Some(&b'\'') => {
                let form_start = skip_ws_bytes(src, i + 2);
                if form_start >= bytes.len() {
                    return Err(CljError::Read("var quote has no following form".into()));
                }
                let form_end = find_form_end(src, form_start)?;
                out.push_str("(var ");
                out.push_str(&src[form_start..form_end]);
                out.push(')');
                i = form_end;
            }
            _ => {
                let ch = src[i..].chars().next().expect("valid char boundary");
                out.push(ch);
                i += ch.len_utf8();
            }
        }
    }
    Ok(out)
}

fn expand_quote_syntax(src: &str) -> Result<String, CljError> {
    let bytes = src.as_bytes();
    let mut out = String::with_capacity(src.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                let end = skip_string(src, i)?;
                out.push_str(&src[i..end]);
                i = end;
            }
            b';' => {
                let end = skip_comment(src, i);
                out.push_str(&src[i..end]);
                i = end;
            }
            b'\'' => {
                let form_start = skip_ws_bytes(src, i + 1);
                if form_start >= bytes.len() {
                    return Err(CljError::Read("quote has no following form".into()));
                }
                let form_end = find_form_end(src, form_start)?;
                out.push_str("(quote ");
                out.push_str(&src[form_start..form_end]);
                out.push(')');
                i = form_end;
            }
            _ => {
                let ch = src[i..].chars().next().expect("valid char boundary");
                out.push(ch);
                i += ch.len_utf8();
            }
        }
    }
    Ok(out)
}

fn expand_discard_syntax(src: &str) -> Result<String, CljError> {
    let bytes = src.as_bytes();
    let mut out = String::with_capacity(src.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                let end = skip_string(src, i)?;
                out.push_str(&src[i..end]);
                i = end;
            }
            b';' => {
                let end = skip_comment(src, i);
                out.push_str(&src[i..end]);
                i = end;
            }
            b'#' if bytes.get(i + 1) == Some(&b'_') => {
                let form_start = skip_ws_and_comments(src, i + 2)?;
                if form_start >= bytes.len() {
                    return Err(CljError::Read(
                        "discard marker has no following form".into(),
                    ));
                }
                i = find_reader_form_end(src, form_start)?;
                out.push(' ');
            }
            _ => {
                let ch = src[i..].chars().next().expect("valid char boundary");
                out.push(ch);
                i += ch.len_utf8();
            }
        }
    }
    Ok(out)
}

fn expand_metadata_syntax(src: &str) -> Result<String, CljError> {
    let bytes = src.as_bytes();
    let mut out = String::with_capacity(src.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                let end = skip_string(src, i)?;
                out.push_str(&src[i..end]);
                i = end;
            }
            b';' => {
                let end = skip_comment(src, i);
                out.push_str(&src[i..end]);
                i = end;
            }
            b'^' if is_metadata_position(src, i) => {
                let metadata_start = skip_ws_bytes(src, i + 1);
                if metadata_start >= bytes.len() {
                    return Err(CljError::Read(
                        "metadata marker has no metadata form".into(),
                    ));
                }
                let metadata_end = find_form_end(src, metadata_start)?;
                i = skip_ws_bytes(src, metadata_end);
                out.push(' ');
            }
            _ => {
                let ch = src[i..].chars().next().expect("valid char boundary");
                out.push(ch);
                i += ch.len_utf8();
            }
        }
    }
    Ok(out)
}

fn is_metadata_position(src: &str, i: usize) -> bool {
    if i == 0 {
        return true;
    }
    src.as_bytes()
        .get(i - 1)
        .is_none_or(|b| matches!(b, b' ' | b'\t' | b'\n' | b'\r' | b',' | b'(' | b'[' | b'{'))
}

fn select_reader_branch(src: &str, target: ReaderTarget) -> Result<Option<EdnValue>, CljError> {
    let forms = parse_all(src)
        .map_err(|e| CljError::Read(format!("reader conditional parse error in `#?(...)`: {e}")))?;
    if forms.len() % 2 != 0 {
        return Err(CljError::Read(
            "reader conditional requires feature/expression pairs".into(),
        ));
    }

    for name in target.branch_names() {
        for pair in forms.chunks_exact(2) {
            if keyword_name(&pair[0]) == Some(*name) {
                return Ok(Some(pair[1].clone()));
            }
        }
    }
    Ok(None)
}

fn keyword_name(v: &EdnValue) -> Option<&str> {
    v.as_keyword().and_then(|k| {
        if k.namespace().is_none() {
            Some(k.name())
        } else {
            None
        }
    })
}

#[derive(Debug, Default)]
struct NamespaceCtx {
    current_ns: Option<String>,
    aliases: HashMap<String, String>,
    non_load_aliases: HashSet<String>,
    refers: HashMap<String, String>,
    refer_all: HashSet<String>,
    refer_all_excludes: HashMap<String, HashSet<String>>,
    renames: HashMap<String, String>,
    local_defs: HashSet<String>,
}

impl NamespaceCtx {
    fn from_forms(forms: &[EdnValue], exports: &HashMap<String, HashSet<String>>) -> Self {
        let mut ctx = Self::default();
        for form in forms {
            collect_namespace_ctx(form, &mut ctx);
        }
        for ns in ctx.refer_all.clone() {
            if let Some(names) = exports.get(&ns) {
                let excludes = ctx.refer_all_excludes.get(&ns);
                for name in names {
                    if excludes.is_some_and(|excluded| excluded.contains(name)) {
                        continue;
                    }
                    ctx.refers.insert(name.clone(), format!("{ns}/{name}"));
                }
            }
        }
        ctx
    }
}

fn collect_namespace_ctx(form: &EdnValue, ctx: &mut NamespaceCtx) {
    let EdnValue::List(items) = form else {
        return;
    };
    match list_head_name(items).as_deref() {
        Some("ns") => {
            if let Some(EdnValue::Symbol(s)) = items.get(1) {
                ctx.current_ns = Some(s.to_qualified());
            }
            read_ns_requires(items, ctx);
        }
        Some("require" | "require-macros") => {
            read_require_specs(&items[1..], ctx);
        }
        Some("use" | "use-macros") => {
            read_use_specs(&items[1..], ctx);
        }
        Some("def" | "defonce" | "defn" | "defn-" | "defgraph") => {
            if let Some(EdnValue::Symbol(s)) = items.get(1) {
                if s.namespace.is_none() {
                    ctx.local_defs.insert(s.name.clone());
                }
            }
        }
        Some("do") => {
            for item in &items[1..] {
                collect_namespace_ctx(item, ctx);
            }
        }
        _ => {}
    }
}

fn namespace_name(forms: &[EdnValue]) -> Option<String> {
    forms.iter().find_map(namespace_name_in_form)
}

fn namespace_name_in_form(form: &EdnValue) -> Option<String> {
    let EdnValue::List(items) = form else {
        return None;
    };
    match list_head_name(items).as_deref() {
        Some("ns") => match items.get(1) {
            Some(EdnValue::Symbol(s)) => Some(s.to_qualified()),
            _ => None,
        },
        Some("do") => items[1..].iter().find_map(namespace_name_in_form),
        _ => None,
    }
}

fn exported_names(forms: &[EdnValue]) -> HashSet<String> {
    let mut out = HashSet::new();
    for form in forms {
        collect_exported_names(form, &mut out);
    }
    out
}

fn collect_exported_names(form: &EdnValue, out: &mut HashSet<String>) {
    let EdnValue::List(items) = form else {
        return;
    };
    match list_head_name(items).as_deref() {
        Some("def" | "defonce" | "defn" | "defgraph") => {
            if let Some(EdnValue::Symbol(s)) = items.get(1) {
                out.insert(s.name.clone());
            }
        }
        Some("do") => {
            for item in &items[1..] {
                collect_exported_names(item, out);
            }
        }
        _ => {}
    }
}

fn required_namespaces(forms: &[EdnValue]) -> Vec<String> {
    let ctx = NamespaceCtx::from_forms(forms, &HashMap::new());
    let mut out = HashSet::new();
    out.extend(
        ctx.aliases
            .iter()
            .filter(|(alias, _)| !ctx.non_load_aliases.contains(*alias))
            .map(|(_, ns)| ns.clone()),
    );
    out.extend(ctx.refer_all.iter().cloned());
    out.extend(
        ctx.refers
            .values()
            .filter_map(|qualified| qualified.split('/').next())
            .map(str::to_string),
    );
    out.into_iter()
        .filter(|ns| !is_platform_namespace(ns))
        .collect()
}

fn is_platform_namespace(ns: &str) -> bool {
    ns == "clojure.core"
        || ns.starts_with("clojure.")
        || ns == "cljs.core"
        || ns.starts_with("cljs.")
}

fn read_ns_requires(items: &[EdnValue], ctx: &mut NamespaceCtx) {
    for clause in &items[2..] {
        let EdnValue::List(parts) = clause else {
            continue;
        };
        match keyword_name(parts.first().unwrap_or(&EdnValue::Nil)) {
            Some("require" | "require-macros") => {
                read_require_specs(&parts[1..], ctx);
            }
            Some("use" | "use-macros") => {
                read_use_specs(&parts[1..], ctx);
            }
            _ => {}
        }
    }
}

fn read_require_specs(specs: &[EdnValue], ctx: &mut NamespaceCtx) {
    for spec in specs {
        read_require_spec(unquote_decl_spec(spec), ctx);
    }
}

fn read_require_spec(spec: &EdnValue, ctx: &mut NamespaceCtx) {
    match spec {
        EdnValue::Symbol(ns) => {
            let ns = ns.to_qualified();
            ctx.aliases.entry(ns.clone()).or_insert(ns);
        }
        EdnValue::Vector(xs) => read_require_vector(xs, ctx),
        _ => {}
    }
}

fn read_require_vector(xs: &[EdnValue], ctx: &mut NamespaceCtx) {
    let Some(EdnValue::Symbol(ns)) = xs.first() else {
        return;
    };
    let ns = ns.to_qualified();
    if xs.get(1).is_some_and(|v| matches!(v, EdnValue::Vector(_))) {
        for child in &xs[1..] {
            let EdnValue::Vector(child) = child else {
                continue;
            };
            read_prefixed_require(&ns, child, ctx);
        }
        return;
    }
    read_require_options(&ns, &xs[1..], ctx);
}

fn read_prefixed_require(prefix: &str, xs: &[EdnValue], ctx: &mut NamespaceCtx) {
    let Some(EdnValue::Symbol(suffix)) = xs.first() else {
        return;
    };
    let ns = format!("{prefix}.{}", suffix.to_qualified());
    read_require_options(&ns, &xs[1..], ctx);
}

fn read_use_specs(specs: &[EdnValue], ctx: &mut NamespaceCtx) {
    for spec in specs {
        read_use_spec(unquote_decl_spec(spec), ctx);
    }
}

fn read_use_spec(spec: &EdnValue, ctx: &mut NamespaceCtx) {
    match spec {
        EdnValue::Symbol(ns) => {
            ctx.refer_all.insert(ns.to_qualified());
        }
        EdnValue::Vector(xs) => read_use_vector(xs, ctx),
        _ => {}
    }
}

fn read_use_vector(xs: &[EdnValue], ctx: &mut NamespaceCtx) {
    let Some(EdnValue::Symbol(ns)) = xs.first() else {
        return;
    };
    let ns = ns.to_qualified();
    if xs.get(1).is_some_and(|v| matches!(v, EdnValue::Vector(_))) {
        for child in &xs[1..] {
            let EdnValue::Vector(child) = child else {
                continue;
            };
            read_prefixed_use(&ns, child, ctx);
        }
        return;
    }
    read_use_options(&ns, &xs[1..], ctx);
}

fn read_prefixed_use(prefix: &str, xs: &[EdnValue], ctx: &mut NamespaceCtx) {
    let Some(EdnValue::Symbol(suffix)) = xs.first() else {
        return;
    };
    let ns = format!("{prefix}.{}", suffix.to_qualified());
    read_use_options(&ns, &xs[1..], ctx);
}

fn unquote_decl_spec(spec: &EdnValue) -> &EdnValue {
    let EdnValue::List(items) = spec else {
        return spec;
    };
    match (list_head_name(items).as_deref(), items.get(1), items.len()) {
        (Some("quote"), Some(inner), 2) => inner,
        _ => spec,
    }
}

fn read_require_options(ns: &str, opts: &[EdnValue], ctx: &mut NamespaceCtx) {
    let mut saw_alias_or_refer = false;
    let mut i = 0;
    while i + 1 < opts.len() {
        match keyword_name(&opts[i]) {
            Some("as") => {
                if let EdnValue::Symbol(alias) = &opts[i + 1] {
                    ctx.aliases.insert(alias.name.clone(), ns.to_string());
                    ctx.non_load_aliases.remove(&alias.name);
                    saw_alias_or_refer = true;
                }
            }
            Some("as-alias") => {
                if let EdnValue::Symbol(alias) = &opts[i + 1] {
                    ctx.aliases.insert(alias.name.clone(), ns.to_string());
                    ctx.non_load_aliases.insert(alias.name.clone());
                    saw_alias_or_refer = true;
                }
            }
            Some("refer" | "refer-macros") => {
                match &opts[i + 1] {
                    EdnValue::Vector(names) => {
                        for name in names {
                            if let EdnValue::Symbol(name) = name {
                                ctx.refers
                                    .insert(name.name.clone(), format!("{ns}/{}", name.name));
                            }
                        }
                    }
                    EdnValue::Keyword(k) if k.name() == "all" => {
                        ctx.refer_all.insert(ns.to_string());
                    }
                    _ => {}
                }
                saw_alias_or_refer = true;
            }
            Some("rename") => {
                if let EdnValue::Map(renames) = &opts[i + 1] {
                    for (from, to) in renames {
                        if let (EdnValue::Symbol(from), EdnValue::Symbol(to)) = (from, to) {
                            ctx.renames
                                .insert(to.name.clone(), format!("{ns}/{}", from.name));
                        }
                    }
                }
            }
            Some("exclude") => {
                read_refer_all_excludes(ns, &opts[i + 1], ctx);
            }
            _ => {}
        }
        i += 2;
    }
    if !saw_alias_or_refer && !ns.starts_with("clojure.") {
        ctx.aliases
            .entry(ns.to_string())
            .or_insert_with(|| ns.to_string());
    }
}

fn read_use_options(ns: &str, opts: &[EdnValue], ctx: &mut NamespaceCtx) {
    let mut saw_only = false;
    let mut i = 0;
    while i + 1 < opts.len() {
        match keyword_name(&opts[i]) {
            Some("only") => {
                if let EdnValue::Vector(names) = &opts[i + 1] {
                    for name in names {
                        if let EdnValue::Symbol(name) = name {
                            ctx.refers
                                .insert(name.name.clone(), format!("{ns}/{}", name.name));
                        }
                    }
                }
                saw_only = true;
            }
            Some("as") => {
                if let EdnValue::Symbol(alias) = &opts[i + 1] {
                    ctx.aliases.insert(alias.name.clone(), ns.to_string());
                }
            }
            Some("rename") => {
                if let EdnValue::Map(renames) = &opts[i + 1] {
                    for (from, to) in renames {
                        if let (EdnValue::Symbol(from), EdnValue::Symbol(to)) = (from, to) {
                            ctx.renames
                                .insert(to.name.clone(), format!("{ns}/{}", from.name));
                        }
                    }
                }
            }
            Some("exclude") => {
                read_refer_all_excludes(ns, &opts[i + 1], ctx);
            }
            _ => {}
        }
        i += 2;
    }
    if !saw_only {
        ctx.refer_all.insert(ns.to_string());
    }
}

fn read_refer_all_excludes(ns: &str, value: &EdnValue, ctx: &mut NamespaceCtx) {
    let EdnValue::Vector(names) = value else {
        return;
    };
    let excludes = ctx.refer_all_excludes.entry(ns.to_string()).or_default();
    for name in names {
        if let EdnValue::Symbol(name) = name {
            excludes.insert(name.name.clone());
        }
    }
}

fn qualify_top_level(form: EdnValue, ctx: &NamespaceCtx, qualify_defs: bool) -> EdnValue {
    let EdnValue::List(mut items) = form else {
        return form;
    };
    match list_head_name(&items).as_deref() {
        Some("def" | "defonce") => {
            if qualify_defs {
                if let Some(name) = items.get_mut(1) {
                    *name = qualify_definition_name(name.clone(), ctx);
                }
            }
            for item in items.iter_mut().skip(2) {
                *item = qualify_expr(item.clone(), ctx, qualify_defs);
            }
            EdnValue::List(items)
        }
        Some("defn" | "defn-") => qualify_defn_top_level(items, ctx, qualify_defs),
        Some("defgraph") => {
            if qualify_defs {
                if let Some(name) = items.get_mut(1) {
                    *name = qualify_definition_name(name.clone(), ctx);
                }
            }
            for item in items.iter_mut().skip(2) {
                *item = qualify_expr(item.clone(), ctx, qualify_defs);
            }
            EdnValue::List(items)
        }
        Some(
            "ns" | "require" | "require-macros" | "use" | "use-macros" | "refer-clojure" | "import"
            | "in-ns" | "alias" | "create-ns" | "remove-ns" | "gen-class" | "set!" | "defrecord"
            | "deftype" | "defprotocol" | "extend-type" | "extend-protocol" | "defmulti"
            | "defmethod" | "defmacro" | "defstruct" | "create-struct",
        ) => EdnValue::List(items),
        Some("do") => {
            let mut out = Vec::with_capacity(items.len());
            out.push(items.remove(0));
            out.extend(
                items
                    .into_iter()
                    .map(|item| qualify_top_level(item, ctx, qualify_defs)),
            );
            EdnValue::List(out)
        }
        _ => EdnValue::List(
            items
                .into_iter()
                .map(|v| qualify_expr(v, ctx, qualify_defs))
                .collect(),
        ),
    }
}

fn qualify_defn_top_level(
    mut items: Vec<EdnValue>,
    ctx: &NamespaceCtx,
    qualify_defs: bool,
) -> EdnValue {
    if qualify_defs {
        if let Some(name) = items.get_mut(1) {
            *name = qualify_definition_name(name.clone(), ctx);
        }
    }
    let mut idx = 2;
    if matches!(items.get(idx), Some(EdnValue::String(_))) {
        idx += 1;
    }
    if matches!(items.get(idx), Some(EdnValue::Map(_))) {
        idx += 1;
    }
    match items.get_mut(idx) {
        Some(EdnValue::Vector(_)) => {
            let shadow = param_shadow(items.get(idx));
            for item in items.iter_mut().skip(idx + 1) {
                *item = qualify_expr_with_shadow(item.clone(), ctx, qualify_defs, &shadow);
            }
        }
        Some(EdnValue::List(arity)) => {
            let shadow = param_shadow(arity.first());
            for item in arity.iter_mut().skip(1) {
                *item = qualify_expr_with_shadow(item.clone(), ctx, qualify_defs, &shadow);
            }
        }
        _ => {
            for item in items.iter_mut().skip(2) {
                *item = qualify_expr(item.clone(), ctx, qualify_defs);
            }
        }
    }
    EdnValue::List(items)
}

fn param_shadow(params: Option<&EdnValue>) -> HashSet<String> {
    let Some(EdnValue::Vector(params)) = params else {
        return HashSet::new();
    };
    let mut out = HashSet::new();
    for param in params {
        collect_pattern_shadow(param, &mut out);
    }
    out
}

fn collect_pattern_shadow(pattern: &EdnValue, out: &mut HashSet<String>) {
    match pattern {
        EdnValue::Symbol(s) if s.namespace.is_none() && s.name != "_" => {
            out.insert(s.name.clone());
        }
        EdnValue::Vector(items) => {
            let mut i = 0;
            while i < items.len() {
                if is_destructure_rest(&items[i]) || is_destructure_as(&items[i]) {
                    if let Some(name) = items.get(i + 1) {
                        collect_pattern_shadow(name, out);
                    }
                    i += 2;
                } else {
                    collect_pattern_shadow(&items[i], out);
                    i += 1;
                }
            }
        }
        EdnValue::Map(items) => {
            for (binding, value) in items {
                if is_destructure_keys(binding)
                    || is_destructure_strs(binding)
                    || is_destructure_as(binding)
                {
                    collect_pattern_shadow(value, out);
                } else if is_destructure_or(binding) {
                    if let EdnValue::Map(defaults) = value {
                        for name in defaults.keys() {
                            collect_pattern_shadow(name, out);
                        }
                    }
                } else {
                    collect_pattern_shadow(binding, out);
                }
            }
        }
        _ => {}
    }
}

fn is_destructure_rest(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Symbol(s) if s.namespace.is_none() && s.name == "&")
}

fn is_destructure_as(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Keyword(k) if k.namespace().is_none() && k.name() == "as")
}

fn is_destructure_keys(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Keyword(k) if k.namespace().is_none() && k.name() == "keys")
}

fn is_destructure_strs(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Keyword(k) if k.namespace().is_none() && k.name() == "strs")
}

fn is_destructure_or(v: &EdnValue) -> bool {
    matches!(v, EdnValue::Keyword(k) if k.namespace().is_none() && k.name() == "or")
}

fn qualify_expr(v: EdnValue, ctx: &NamespaceCtx, qualify_defs: bool) -> EdnValue {
    qualify_expr_with_shadow(v, ctx, qualify_defs, &HashSet::new())
}

fn qualify_expr_with_shadow(
    v: EdnValue,
    ctx: &NamespaceCtx,
    qualify_defs: bool,
    shadowed: &HashSet<String>,
) -> EdnValue {
    match v {
        EdnValue::List(items) => qualify_list_expr(items, ctx, qualify_defs, shadowed),
        EdnValue::Vector(xs) => EdnValue::Vector(
            xs.into_iter()
                .map(|v| qualify_expr_with_shadow(v, ctx, qualify_defs, shadowed))
                .collect(),
        ),
        EdnValue::Map(m) => EdnValue::Map(
            m.into_iter()
                .map(|(k, v)| {
                    (
                        qualify_expr_with_shadow(k, ctx, qualify_defs, shadowed),
                        qualify_expr_with_shadow(v, ctx, qualify_defs, shadowed),
                    )
                })
                .collect::<BTreeMap<_, _>>(),
        ),
        other => qualify_symbol_value(other, ctx, qualify_defs, shadowed),
    }
}

fn qualify_list_expr(
    items: Vec<EdnValue>,
    ctx: &NamespaceCtx,
    qualify_defs: bool,
    shadowed: &HashSet<String>,
) -> EdnValue {
    let Some(head) = items.first() else {
        return EdnValue::List(items);
    };
    let special = list_head_name(&items).unwrap_or_default();
    match special.as_str() {
        "let" | "loop" => {
            let mut out = items;
            let mut inner_shadow = shadowed.clone();
            if let Some(EdnValue::Vector(bindings)) = out.get_mut(1) {
                for i in (1..bindings.len()).step_by(2) {
                    bindings[i] = qualify_expr_with_shadow(
                        bindings[i].clone(),
                        ctx,
                        qualify_defs,
                        &inner_shadow,
                    );
                    collect_pattern_shadow(&bindings[i - 1], &mut inner_shadow);
                }
            }
            for item in out.iter_mut().skip(2) {
                *item = qualify_expr_with_shadow(item.clone(), ctx, qualify_defs, &inner_shadow);
            }
            EdnValue::List(out)
        }
        "if-let" | "when-let" => {
            let mut out = items;
            let mut inner_shadow = shadowed.clone();
            if let Some(EdnValue::Vector(bindings)) = out.get_mut(1) {
                if let Some(init) = bindings.get_mut(1) {
                    *init = qualify_expr_with_shadow(init.clone(), ctx, qualify_defs, shadowed);
                }
                if let Some(pattern) = bindings.first() {
                    collect_pattern_shadow(pattern, &mut inner_shadow);
                }
            }
            for item in out.iter_mut().skip(2) {
                *item = qualify_expr_with_shadow(item.clone(), ctx, qualify_defs, &inner_shadow);
            }
            EdnValue::List(out)
        }
        "as->" => {
            let mut out = items;
            let mut inner_shadow = shadowed.clone();
            if let Some(init) = out.get_mut(1) {
                *init = qualify_expr_with_shadow(init.clone(), ctx, qualify_defs, shadowed);
            }
            if let Some(EdnValue::Symbol(s)) = out.get(2) {
                if s.namespace.is_none() {
                    inner_shadow.insert(s.name.clone());
                }
            }
            for item in out.iter_mut().skip(3) {
                *item = qualify_expr_with_shadow(item.clone(), ctx, qualify_defs, &inner_shadow);
            }
            EdnValue::List(out)
        }
        "quote" => EdnValue::List(items),
        _ => {
            let mut out = Vec::with_capacity(items.len());
            out.push(qualify_call_head(head.clone(), ctx, qualify_defs));
            out.extend(
                items
                    .into_iter()
                    .skip(1)
                    .map(|v| qualify_expr_with_shadow(v, ctx, qualify_defs, shadowed)),
            );
            EdnValue::List(out)
        }
    }
}

fn qualify_definition_name(v: EdnValue, ctx: &NamespaceCtx) -> EdnValue {
    match (v, ctx.current_ns.as_deref()) {
        (EdnValue::Symbol(s), Some(ns)) if s.namespace.is_none() => {
            EdnValue::Symbol(Symbol::namespaced(ns, s.name))
        }
        (other, _) => other,
    }
}

fn qualify_call_head(v: EdnValue, ctx: &NamespaceCtx, qualify_defs: bool) -> EdnValue {
    let EdnValue::Symbol(s) = v else {
        return v;
    };
    if let Some(ns) = s
        .namespace
        .as_deref()
        .and_then(|alias| ctx.aliases.get(alias))
    {
        return EdnValue::Symbol(Symbol::namespaced(ns, s.name));
    }
    if s.namespace.is_none() {
        if let Some(full) = ctx.renames.get(&s.name) {
            return EdnValue::Symbol(Symbol::parse(full));
        }
        if let Some(full) = ctx.refers.get(&s.name) {
            return EdnValue::Symbol(Symbol::parse(full));
        }
        if qualify_defs && ctx.local_defs.contains(&s.name) {
            if let Some(ns) = &ctx.current_ns {
                return EdnValue::Symbol(Symbol::namespaced(ns, s.name));
            }
        }
    }
    EdnValue::Symbol(s)
}

fn qualify_symbol_value(
    v: EdnValue,
    ctx: &NamespaceCtx,
    qualify_defs: bool,
    shadowed: &HashSet<String>,
) -> EdnValue {
    match v {
        EdnValue::Symbol(s) => {
            if let Some(ns) = s
                .namespace
                .as_deref()
                .and_then(|alias| ctx.aliases.get(alias))
            {
                EdnValue::Symbol(Symbol::namespaced(ns, s.name))
            } else if qualify_defs
                && s.namespace.is_none()
                && !shadowed.contains(&s.name)
                && ctx.local_defs.contains(&s.name)
            {
                match ctx.current_ns.as_deref() {
                    Some(ns) => EdnValue::Symbol(Symbol::namespaced(ns, s.name)),
                    None => EdnValue::Symbol(s),
                }
            } else {
                EdnValue::Symbol(s)
            }
        }
        other => other,
    }
}

fn list_head_name(items: &[EdnValue]) -> Option<String> {
    match items.first() {
        Some(EdnValue::Symbol(s)) => Some(s.to_qualified()),
        _ => None,
    }
}

fn splice_value(v: &EdnValue) -> String {
    match v {
        EdnValue::List(xs) | EdnValue::Vector(xs) => {
            xs.iter().map(to_string).collect::<Vec<_>>().join(" ")
        }
        other => to_string(other),
    }
}

fn find_matching(src: &str, open: usize) -> Result<usize, CljError> {
    let bytes = src.as_bytes();
    let mut i = open;
    let mut stack = Vec::new();
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                i = skip_string(src, i)?;
                continue;
            }
            b';' => {
                i = skip_comment(src, i);
                continue;
            }
            b'(' | b'[' | b'{' => stack.push(bytes[i]),
            b')' | b']' | b'}' => {
                let Some(last) = stack.pop() else {
                    return Err(CljError::Read(format!(
                        "unbalanced reader conditional at byte {i}"
                    )));
                };
                if !matches!((last, bytes[i]), (b'(', b')') | (b'[', b']') | (b'{', b'}')) {
                    return Err(CljError::Read(format!(
                        "mismatched delimiter in reader conditional at byte {i}"
                    )));
                }
                if stack.is_empty() {
                    return Ok(i);
                }
            }
            _ => {}
        }
        i += 1;
    }
    Err(CljError::Read("unterminated reader conditional".into()))
}

fn find_form_end(src: &str, start: usize) -> Result<usize, CljError> {
    match src.as_bytes().get(start).copied() {
        Some(b'(' | b'[' | b'{') => find_matching(src, start).map(|i| i + 1),
        Some(b'"') => skip_string(src, start),
        Some(_) => Ok(read_token_end(src, start)),
        None => Err(CljError::Read("expected quoted form".into())),
    }
}

fn find_reader_form_end(src: &str, start: usize) -> Result<usize, CljError> {
    match src.as_bytes().get(start).copied() {
        Some(b'^') => {
            let metadata_start = skip_ws_and_comments(src, start + 1)?;
            if metadata_start >= src.len() {
                return Err(CljError::Read(
                    "metadata marker has no metadata form".into(),
                ));
            }
            let metadata_end = find_reader_form_end(src, metadata_start)?;
            let form_start = skip_ws_and_comments(src, metadata_end)?;
            if form_start >= src.len() {
                return Err(CljError::Read(
                    "metadata marker has no following form".into(),
                ));
            }
            find_reader_form_end(src, form_start)
        }
        Some(b'\'') => {
            let form_start = skip_ws_and_comments(src, start + 1)?;
            if form_start >= src.len() {
                return Err(CljError::Read("quote has no following form".into()));
            }
            find_reader_form_end(src, form_start)
        }
        Some(b'#') if src.as_bytes().get(start + 1) == Some(&b'_') => {
            let form_start = skip_ws_and_comments(src, start + 2)?;
            if form_start >= src.len() {
                return Err(CljError::Read(
                    "discard marker has no following form".into(),
                ));
            }
            find_reader_form_end(src, form_start)
        }
        _ => find_form_end(src, start),
    }
}

fn read_token_end(src: &str, start: usize) -> usize {
    let bytes = src.as_bytes();
    let mut i = start;
    while i < bytes.len() {
        if is_reader_terminator(bytes[i]) {
            break;
        }
        let ch = src[i..].chars().next().expect("valid char boundary");
        i += ch.len_utf8();
    }
    i
}

fn skip_ws_and_comments(src: &str, mut i: usize) -> Result<usize, CljError> {
    let bytes = src.as_bytes();
    loop {
        while i < bytes.len() && matches!(bytes[i], b' ' | b'\t' | b'\n' | b'\r' | b',') {
            i += 1;
        }
        if i < bytes.len() && bytes[i] == b';' {
            i = skip_comment(src, i);
            continue;
        }
        return Ok(i);
    }
}

fn skip_ws_bytes(src: &str, mut i: usize) -> usize {
    let bytes = src.as_bytes();
    while i < bytes.len() && matches!(bytes[i], b' ' | b'\t' | b'\n' | b'\r' | b',') {
        i += 1;
    }
    i
}

fn is_reader_terminator(b: u8) -> bool {
    matches!(
        b,
        b' ' | b'\t' | b'\n' | b'\r' | b',' | b';' | b'(' | b')' | b'[' | b']' | b'{' | b'}' | b'"'
    )
}

fn skip_string(src: &str, start: usize) -> Result<usize, CljError> {
    let bytes = src.as_bytes();
    let mut i = start + 1;
    while i < bytes.len() {
        match bytes[i] {
            b'\\' => i += 2,
            b'"' => return Ok(i + 1),
            _ => i += 1,
        }
    }
    Err(CljError::Read("unterminated string literal".into()))
}

fn skip_comment(src: &str, start: usize) -> usize {
    let bytes = src.as_bytes();
    let mut i = start;
    while i < bytes.len() {
        i += 1;
        if bytes[i - 1] == b'\n' {
            break;
        }
    }
    i
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expands_reader_conditional_for_kotoba_then_clj_then_default() {
        assert_eq!(
            normalize_source("#?(:kotoba 1 :clj 2 :default 3)", ReaderTarget::Kotoba).unwrap(),
            "1"
        );
        assert_eq!(
            normalize_source("#?(:cljs 1 :clj 2 :default 3)", ReaderTarget::Kotoba).unwrap(),
            "2"
        );
        assert_eq!(
            normalize_source("#?(:cljs 1 :default 3)", ReaderTarget::Kotoba).unwrap(),
            "3"
        );
    }

    #[test]
    fn splices_selected_forms() {
        assert_eq!(
            normalize_source("(do #?@(:clj [(inc 1) (inc 2)]))", ReaderTarget::Kotoba).unwrap(),
            "(do (inc 1) (inc 2))"
        );
    }

    #[test]
    fn ignores_reader_conditional_markers_in_strings_and_comments() {
        let src = "\"#?(:clj 1)\" ; #?(:clj 2)\n#?(:clj 3)";
        assert_eq!(
            normalize_source(src, ReaderTarget::Kotoba).unwrap(),
            "\"#?(:clj 1)\"\n3"
        );
    }

    #[test]
    fn expands_var_quote_before_plain_quote() {
        assert_eq!(
            normalize_source("#'demo/ok", ReaderTarget::Kotoba).unwrap(),
            "(var demo/ok)"
        );
        assert_eq!(
            normalize_source("\"#'kept\" ; #'ignored\n#'demo/ok", ReaderTarget::Kotoba).unwrap(),
            "\"#'kept\"\n(var demo/ok)"
        );
    }

    #[test]
    fn strips_metadata_reader_syntax() {
        assert_eq!(
            normalize_source(
                " ^:private (defn f [^long x ^String y] (+ x (str-len y)))",
                ReaderTarget::Kotoba,
            )
            .unwrap(),
            "(defn f [x y] (+ x (str-len y)))"
        );
        assert_eq!(
            normalize_source("(defn f [] (str-len \"^kept\"))", ReaderTarget::Kotoba).unwrap(),
            "(defn f [] (str-len \"^kept\"))"
        );
    }

    #[test]
    fn strips_discard_reader_syntax() {
        assert_eq!(
            normalize_source(
                "#_ (def ignored 1) (defn f [] 42) #_ ^:private '(a b)",
                ReaderTarget::Kotoba,
            )
            .unwrap(),
            "(defn f [] 42)"
        );
        assert_eq!(
            normalize_source(
                "\"#_kept\" ; #_ (ignored)\n(defn f [] 42)",
                ReaderTarget::Kotoba
            )
            .unwrap(),
            "\"#_kept\"\n(defn f [] 42)"
        );
    }
}

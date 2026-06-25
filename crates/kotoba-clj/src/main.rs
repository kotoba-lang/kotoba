use std::path::PathBuf;

fn main() {
    // `cli` feature: the `kotoba-clj build|run …` toolchain subcommands share this
    // binary with the legacy file runner. A first arg of `build`/`run` routes to the
    // subcommand dispatcher; anything else (a source file) falls through to the runner.
    #[cfg(feature = "cli")]
    {
        let mut args = std::env::args().skip(1);
        if let Some(sub) = args.next() {
            if sub == "build" || sub == "safe-build" || sub == "run" {
                let rest: Vec<String> = args.collect();
                if let Err(err) = kotoba_clj::cli::run(&sub, &rest) {
                    eprintln!("kotoba-clj: {err:#}");
                    std::process::exit(1);
                }
                return;
            }
        }
    }

    if let Err(err) = real_main() {
        eprintln!("kotoba-clj: {err}");
        std::process::exit(1);
    }
}

fn real_main() -> Result<(), String> {
    let opts = Options::parse(std::env::args().skip(1).collect())?;
    if !is_supported_source_ext(&opts.path) && !opts.allow_any_ext {
        return Err(format!(
            "expected a .kotoba/.clj/.cljc/.cljs file (got {}). Use --allow-any-ext to run anyway.",
            opts.path.display()
        ));
    }

    let wasm = if opts.prelude {
        kotoba_clj::compile_file_with_prelude_reader_target_and_source_paths(
            &opts.path,
            opts.reader_target,
            &opts.source_paths,
        )
    } else {
        kotoba_clj::compile_file_with_reader_target_and_source_paths(
            &opts.path,
            opts.reader_target,
            &opts.source_paths,
        )
    }
    .map_err(|e| e.to_string())?;

    if let Some(path) = opts.wasm_out {
        std::fs::write(&path, &wasm).map_err(|e| format!("write {}: {e}", path.display()))?;
    }

    let out = kotoba_clj::run::run(&wasm, &opts.func, &opts.args).map_err(|e| e.to_string())?;
    println!("{out}");
    Ok(())
}

#[derive(Debug, PartialEq, Eq)]
struct Options {
    path: PathBuf,
    func: String,
    args: Vec<i64>,
    prelude: bool,
    allow_any_ext: bool,
    reader_target: kotoba_clj::ReaderTarget,
    source_paths: Vec<PathBuf>,
    wasm_out: Option<PathBuf>,
}

impl Options {
    fn parse(argv: Vec<String>) -> Result<Self, String> {
        let mut func = "main".to_string();
        let mut prelude = true;
        let mut allow_any_ext = false;
        let mut reader_target = kotoba_clj::ReaderTarget::Kotoba;
        let mut source_paths = Vec::new();
        let mut wasm_out = None;
        let mut positional = Vec::new();
        let mut i = 0;
        while i < argv.len() {
            match argv[i].as_str() {
                "-h" | "--help" => return Err(usage()),
                "-f" | "--func" => {
                    i += 1;
                    func = argv
                        .get(i)
                        .cloned()
                        .ok_or_else(|| "--func requires a function name".to_string())?;
                }
                "--no-prelude" => prelude = false,
                "--allow-any-ext" => allow_any_ext = true,
                "--reader-target" => {
                    i += 1;
                    let target = argv
                        .get(i)
                        .ok_or_else(|| "--reader-target requires kotoba|clj|cljs".to_string())?;
                    reader_target = kotoba_clj::ReaderTarget::parse(target)
                        .ok_or_else(|| format!("unsupported reader target: {target}"))?;
                }
                "-S" | "--source-path" => {
                    i += 1;
                    let path = argv
                        .get(i)
                        .cloned()
                        .ok_or_else(|| "--source-path requires a directory".to_string())?;
                    source_paths.push(PathBuf::from(path));
                }
                "--wasm-out" => {
                    i += 1;
                    let path = argv
                        .get(i)
                        .cloned()
                        .ok_or_else(|| "--wasm-out requires a path".to_string())?;
                    wasm_out = Some(PathBuf::from(path));
                }
                "--" => {
                    positional.extend(argv[i + 1..].iter().cloned());
                    break;
                }
                flag if flag.starts_with('-') => {
                    return Err(format!("unknown option: {flag}\n{}", usage()))
                }
                value => positional.push(value.to_string()),
            }
            i += 1;
        }

        let path = positional
            .first()
            .cloned()
            .ok_or_else(usage)
            .map(PathBuf::from)?;
        let args = positional[1..]
            .iter()
            .map(|arg| {
                arg.parse::<i64>()
                    .map_err(|e| format!("argument {arg:?} is not an i64: {e}"))
            })
            .collect::<Result<Vec<_>, _>>()?;

        Ok(Self {
            path,
            func,
            args,
            prelude,
            allow_any_ext,
            reader_target,
            source_paths,
            wasm_out,
        })
    }
}

fn is_supported_source_ext(path: &std::path::Path) -> bool {
    matches!(
        path.extension().and_then(|ext| ext.to_str()),
        Some("kotoba" | "clj" | "cljc" | "cljs")
    )
}

fn usage() -> String {
    #[allow(unused_mut)]
    let mut s = "usage: kotoba-clj [--func NAME|-f NAME] [--no-prelude] [--reader-target kotoba|clj|cljs] [--source-path DIR|-S DIR] [--wasm-out OUT.wasm] [--allow-any-ext] FILE.{kotoba,clj,cljc,cljs} [i64 args...]\n\
     examples:\n\
       kotoba-clj app.kotoba\n\
       kotoba-clj --func fact math.kotoba 10\n\
       kotoba-clj -S src app.clj\n\
       kotoba-clj --reader-target kotoba agent.cljc\n\
       chmod +x app.kotoba && ./app.kotoba"
        .to_string();
    #[cfg(feature = "cli")]
    {
        s.push_str("\n\n  ");
        s.push_str(kotoba_clj::cli::SUBCOMMAND_USAGE);
    }
    s
}

#[cfg(test)]
mod tests {
    use super::{Options, PathBuf};

    #[test]
    fn parses_default_run() {
        assert_eq!(
            Options::parse(vec!["app.kotoba".into(), "1".into(), "2".into()]).unwrap(),
            Options {
                path: PathBuf::from("app.kotoba"),
                func: "main".into(),
                args: vec![1, 2],
                prelude: true,
                allow_any_ext: false,
                reader_target: kotoba_clj::ReaderTarget::Kotoba,
                source_paths: vec![],
                wasm_out: None,
            }
        );
    }

    #[test]
    fn parses_flags() {
        assert_eq!(
            Options::parse(vec![
                "--func".into(),
                "fact".into(),
                "--no-prelude".into(),
                "--allow-any-ext".into(),
                "--reader-target".into(),
                "cljs".into(),
                "-S".into(),
                "src".into(),
                "--source-path".into(),
                "vendor".into(),
                "--wasm-out".into(),
                "out.wasm".into(),
                "math.clj".into(),
                "5".into(),
            ])
            .unwrap(),
            Options {
                path: PathBuf::from("math.clj"),
                func: "fact".into(),
                args: vec![5],
                prelude: false,
                allow_any_ext: true,
                reader_target: kotoba_clj::ReaderTarget::Cljs,
                source_paths: vec![PathBuf::from("src"), PathBuf::from("vendor")],
                wasm_out: Some(PathBuf::from("out.wasm")),
            }
        );
    }
}

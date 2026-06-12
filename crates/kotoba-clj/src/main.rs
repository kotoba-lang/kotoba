use std::path::PathBuf;

fn main() {
    if let Err(err) = real_main() {
        eprintln!("kotoba-clj: {err}");
        std::process::exit(1);
    }
}

fn real_main() -> Result<(), String> {
    let opts = Options::parse(std::env::args().skip(1).collect())?;
    if opts.path.extension().is_none_or(|ext| ext != "kotoba") && !opts.allow_any_ext {
        return Err(format!(
            "expected a .kotoba file (got {}). Use --allow-any-ext to run anyway.",
            opts.path.display()
        ));
    }

    let wasm = if opts.prelude {
        kotoba_clj::compile_file_with_prelude(&opts.path)
    } else {
        kotoba_clj::compile_file(&opts.path)
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
    wasm_out: Option<PathBuf>,
}

impl Options {
    fn parse(argv: Vec<String>) -> Result<Self, String> {
        let mut func = "main".to_string();
        let mut prelude = true;
        let mut allow_any_ext = false;
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
            wasm_out,
        })
    }
}

fn usage() -> String {
    "usage: kotoba-clj [--func NAME|-f NAME] [--no-prelude] [--wasm-out OUT.wasm] [--allow-any-ext] FILE.kotoba [i64 args...]\n\
     examples:\n\
       kotoba-clj app.kotoba\n\
       kotoba-clj --func fact math.kotoba 10\n\
       chmod +x app.kotoba && ./app.kotoba"
        .to_string()
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
                wasm_out: Some(PathBuf::from("out.wasm")),
            }
        );
    }
}

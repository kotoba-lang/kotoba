use std::fs;
use std::path::PathBuf;

fn main() {
    let source = PathBuf::from(
        std::env::var("DEP_KOTOBA_ABI_WIT_CAPABILITY_V2_WIT")
            .expect("kotoba-abi-wit must publish its authoritative WIT path"),
    );
    let destination = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap())
        .join("wit/aiueos-capability-v2/aiueos-capability.wit");
    fs::create_dir_all(destination.parent().unwrap()).unwrap();
    fs::copy(&source, &destination).expect("copy authoritative Capability WIT v2");
    println!("cargo:rerun-if-changed={}", source.display());
}

use std::path::PathBuf;

fn main() {
    let path = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap())
        .join("wit/aiueos-capability-v2/aiueos-capability.wit");
    println!("cargo:rerun-if-changed={}", path.display());
    println!("cargo:capability_v2_wit={}", path.display());
}

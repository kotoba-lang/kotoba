// Known-answer vectors for client↔Rust key-tree interop (ADR-2606014000).
use kotoba_crypto::key_tree::{derive_session_seed, derive_signal_seed, derive_storage_key};
fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}
fn main() {
    let ark = [0x11u8; 32];
    println!("storage={}", hex(&derive_storage_key(&ark)));
    println!("signal={}", hex(&derive_signal_seed(&ark)));
    println!("session={}", hex(&derive_session_seed(&ark)));
}

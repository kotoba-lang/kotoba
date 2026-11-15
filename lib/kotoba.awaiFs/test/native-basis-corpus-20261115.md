# Native basis primitives in the frozen corpus gate, 2026-11-15

The Python-free `native_corpus_gate.sh` now stages and runs the existing Native logical signature, v1 logical commit, and one-parent basis tests. The source lock stages only their actual dependencies, including the existing `ed25519.selfhost` source. Three explicit mutation controls require failure when the expected signature payload, canonical logical root, or trusted issuer is changed. The workflow path filter includes the Ed25519 source so a change triggers the gate.

On macOS arm64 with the pinned compiler and packager, the complete gate passed 53 frozen cases, 15 primitives and 30 negative controls. The three new positive tests returned 0; the three respective mutation controls returned 2, 2 and 1. Source pin audit and input-drift checks passed. Exact source locks, artifacts and output remain under `.agent-output/native-signature-corpus-20261115/`. Linux runner and PR CI results must be checked independently.

The one-parent proof in this gate is synthetic and the logical parser remains a fixed-order safe-ASCII subset; the real stored-proof FS2, multi-Pack traversal, trusted issuer enrollment, parent closure, physical catalog binding, policy/receipt and OS-cache-loss fixture are not covered by these new cases.

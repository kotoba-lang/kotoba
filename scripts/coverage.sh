#!/usr/bin/env bash
# kotoba workspace test coverage via cargo-llvm-cov
# Usage:
#   ./scripts/coverage.sh                 # summary table (per-crate + total, --lib tests)
#   ./scripts/coverage.sh html            # + HTML report at target/llvm-cov/html/index.html
#   ./scripts/coverage.sh lcov            # + lcov.info at target/llvm-cov/lcov.info (CI / codecov)
#
# Requires: cargo-llvm-cov (cargo install cargo-llvm-cov) + rustup llvm-tools.
# NOTE: Homebrew rust has no llvm-tools component — we pin the run to the
# rustup stable toolchain so llvm-cov/llvm-profdata versions match rustc.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v rustup >/dev/null; then
  echo "error: rustup not found (Homebrew rust lacks llvm-tools; install rustup)" >&2
  exit 1
fi
if ! rustup run stable cargo llvm-cov --version >/dev/null 2>&1; then
  echo "error: cargo-llvm-cov not found — install with: cargo install cargo-llvm-cov" >&2
  exit 1
fi
rustup component add llvm-tools-preview >/dev/null 2>&1 || true

MODE="${1:-summary}"
case "$MODE" in
  summary)
    exec rustup run stable cargo llvm-cov --workspace --lib --summary-only
    ;;
  html)
    rustup run stable cargo llvm-cov --workspace --lib --html
    echo "HTML report: target/llvm-cov/html/index.html"
    ;;
  lcov)
    rustup run stable cargo llvm-cov --workspace --lib --lcov --output-path target/llvm-cov/lcov.info
    echo "lcov report: target/llvm-cov/lcov.info"
    ;;
  *)
    echo "usage: $0 [summary|html|lcov]" >&2
    exit 1
    ;;
esac

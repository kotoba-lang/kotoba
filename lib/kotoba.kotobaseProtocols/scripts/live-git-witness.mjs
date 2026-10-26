// Backward-compatible entry point; the CLI witness supersedes the earlier
// direct-XRPC probe so the public evidence exercises the actual Git transport.
await import("./live-git-cli-witness.mjs");

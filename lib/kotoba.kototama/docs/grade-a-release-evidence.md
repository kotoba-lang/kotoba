# Grade A release evidence

`kototama.release-evidence` builds a release evidence set containing:

- a deterministic `kototama.jar` with sorted entries and fixed timestamps;
- a CycloneDX 1.5 SBOM with Maven and Git dependency pins;
- an in-toto Statement / SLSA provenance document binding the artifact,
  source-root digest, Git revision, build type, and builder identity;
- an Ed25519 signature envelope over the artifact SHA-256.

The verifier independently checks the artifact digest, Ed25519 signature, SBOM
identity, and provenance subject. Qualification builds twice into different
directories and requires byte-identical artifact hashes, then mutates the JAR
and requires both digest and signature verification to fail.

Release operation supplies the signing seed through the process environment;
the seed is never written into the evidence:

```sh
KOTOTAMA_RELEASE_SIGNING_SEED_HEX=<64-hex-chars> \
  kbb -M:release-evidence dist/release-evidence

kbb -M:test -n kototama.release-evidence-test
```

T-08 remains `in-progress`: CI must publish this evidence for a tagged clean
checkout using a protected signing identity, and an independent auditor must
review the tender and confirm a clean remediation retest.

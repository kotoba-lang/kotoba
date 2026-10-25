// Command gen_sigs records real Storj signatures — one per scheme the network
// can present — and, in -verify mode, hands them back to Storj's own code to
// confirm they are still valid.
//
// Every scheme here was read out of storj.io/common rather than assumed, and
// two of them are not what a reasonable guess produces:
//
//   - Storj signs *messages* with RSA-PSS (pkcrypto.signRSAWithoutHashing
//     calls rsa.VerifyPSS), but X.509 *certificates* carry PKCS#1 v1.5. Same
//     key, same hash, two paddings, and a verifier that implements one and
//     uses it for both fails silently on the other.
//   - Piece keys are ed25519 and travel as 32 raw bytes, not as a DER
//     SubjectPublicKeyInfo like every other key here (storj.PiecePublicKey).
//
// Signing is randomised, so this cannot be a regenerate-and-diff fixture. It
// follows gen_identity.go instead: the recording is checked in and CI runs
// -verify, which holds it to the reference implementation rather than to a
// previous run of this program.
//
//	cd testdata && go run gen_sigs.go            # write sigs.edn
//	cd testdata && go run gen_sigs.go -verify    # check it
package main

import (
	"context"
	"crypto"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"regexp"
	"strings"
	"time"

	"storj.io/common/pb"
	"storj.io/common/pkcrypto"
	"storj.io/common/signing"
	"storj.io/common/storj"
)

const sigsPath = "sigs.edn"

// message is deliberately not a digest and not empty: a verifier that hashes
// the wrong number of times, or not at all, still passes on a 32-byte input
// often enough to be worth avoiding.
var message = []byte("storj.node.host.verify — reference vector, not a digest")

func fill32(start byte) []byte {
	b := make([]byte, 32)
	for i := range b {
		b[i] = start + byte(i)
	}
	return b
}

func main() {
	verify := flag.Bool("verify", false, "verify the recorded signatures instead of generating them")
	flag.Parse()
	if *verify {
		verifySigs()
		return
	}
	generate()
}

func generate() {
	ctx := context.Background()
	out := map[string]string{}
	var order []string
	put := func(k, v string) {
		out[k] = v
		order = append(order, k)
	}

	// ── ECDSA P-256, the scheme every current identity uses ──────────────────
	ecKey, err := pkcrypto.GeneratePrivateKey() // ecdsa.P256, per pkcrypto
	if err != nil {
		panic(err)
	}
	ecPub, err := pkcrypto.PublicKeyFromPrivate(ecKey)
	if err != nil {
		panic(err)
	}
	ecSPKI, err := x509.MarshalPKIXPublicKey(ecPub)
	if err != nil {
		panic(err)
	}
	ecSig, err := pkcrypto.HashAndSign(ecKey, message)
	if err != nil {
		panic(err)
	}
	put("ecdsa-spki", hex.EncodeToString(ecSPKI))
	put("ecdsa-sig", hex.EncodeToString(ecSig))

	// ── RSA-PSS, what pkcrypto uses for messages when the key is RSA ─────────
	rsaKey, err := pkcrypto.GeneratePrivateRSAKey(pkcrypto.StorjRSAKeyBits)
	if err != nil {
		panic(err)
	}
	rsaSPKI, err := x509.MarshalPKIXPublicKey(&rsaKey.PublicKey)
	if err != nil {
		panic(err)
	}
	pssSig, err := pkcrypto.HashAndSign(rsaKey, message)
	if err != nil {
		panic(err)
	}
	put("rsa-spki", hex.EncodeToString(rsaSPKI))
	put("rsa-pss-sig", hex.EncodeToString(pssSig))

	// ── RSA PKCS#1 v1.5, what an X.509 certificate signature is ──────────────
	digest := sha256.Sum256(message)
	pkcs1Sig, err := rsa.SignPKCS1v15(rand.Reader, rsaKey, crypto.SHA256, digest[:])
	if err != nil {
		panic(err)
	}
	put("rsa-pkcs1-sig", hex.EncodeToString(pkcs1Sig))

	// ── ed25519 piece key: 32 raw bytes, no SPKI, no pre-hash ────────────────
	piecePub, piecePriv, err := storj.NewPieceKey()
	if err != nil {
		panic(err)
	}
	pieceSig, err := piecePriv.Sign(message)
	if err != nil {
		panic(err)
	}
	put("ed25519-public-key", hex.EncodeToString(piecePub.Bytes()))
	put("ed25519-sig", hex.EncodeToString(pieceSig))

	put("message", hex.EncodeToString(message))

	// ── end to end: an OrderLimit signed the way a satellite signs it ────────
	//
	// This is the vector that actually matters. It closes the loop between
	// storj.node.pb/encode-order-limit-for-signing and a real signature: the
	// encoder was already checked against EncodeOrderLimit's output, but bytes
	// that merely match are not the same claim as bytes a signature verifies
	// over.
	var satID, nodeID storj.NodeID
	copy(satID[:], fill32(0x10))
	copy(nodeID[:], fill32(0x40))
	pieceID := storj.PieceID{}
	copy(pieceID[:], fill32(0x70))

	expiry := time.Date(2026, 8, 1, 0, 0, 0, 0, time.UTC)
	unsigned := &pb.OrderLimit{
		SerialNumber:    storj.SerialNumber{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16},
		SatelliteId:     satID,
		StorageNodeId:   nodeID,
		PieceId:         pieceID,
		Limit:           1 << 20,
		Action:          pb.PieceAction_PUT,
		OrderExpiration: expiry,
		UplinkPublicKey: piecePub,
	}
	signer := &signing.PrivateKey{Self: satID, Key: ecKey}
	signed, err := signing.SignOrderLimit(ctx, signer, unsigned)
	if err != nil {
		panic(err)
	}
	wire, err := pb.Marshal(signed)
	if err != nil {
		panic(err)
	}
	signingBytes, err := signing.EncodeOrderLimit(ctx, signed)
	if err != nil {
		panic(err)
	}
	put("order-limit-wire", hex.EncodeToString(wire))
	put("order-limit-signing-bytes", hex.EncodeToString(signingBytes))
	put("order-limit-satellite-spki", hex.EncodeToString(ecSPKI))
	put("order-limit-satellite-id", hex.EncodeToString(satID[:]))
	put("order-limit-storage-node-id", hex.EncodeToString(nodeID[:]))
	put("order-limit-expiration-unix", fmt.Sprint(expiry.Unix()))

	var b strings.Builder
	b.WriteString("{;; generated by testdata/gen_sigs.go — signing is randomised, so\n")
	b.WriteString(" ;; CI runs `go run gen_sigs.go -verify` rather than diffing a rerun\n")
	for _, k := range order {
		if k == "order-limit-expiration-unix" {
			fmt.Fprintf(&b, " :%-28s %s\n", k, out[k])
			continue
		}
		fmt.Fprintf(&b, " :%-28s %q\n", k, out[k])
	}
	b.WriteString("}\n")

	if err := os.WriteFile(sigsPath, []byte(b.String()), 0o644); err != nil {
		panic(err)
	}
	fmt.Print(b.String())
}

func sigField(src, name string) string {
	m := regexp.MustCompile(`:` + name + `\s+"([^"]*)"`).FindStringSubmatch(src)
	if m == nil {
		panic("missing field: " + name)
	}
	return m[1]
}

func unhexSig(s string) []byte {
	b, err := hex.DecodeString(s)
	if err != nil {
		panic(err)
	}
	return b
}

func checkSig(what string, ok bool) {
	if !ok {
		fmt.Printf("FAIL %s\n", what)
		os.Exit(1)
	}
	fmt.Printf("ok   %s\n", what)
}

func parsePub(spki []byte) crypto.PublicKey {
	k, err := x509.ParsePKIXPublicKey(spki)
	if err != nil {
		panic(err)
	}
	return k
}

func verifySigs() {
	raw, err := os.ReadFile(sigsPath)
	if err != nil {
		panic(err)
	}
	src := string(raw)
	msg := unhexSig(sigField(src, "message"))

	ecPub := parsePub(unhexSig(sigField(src, "ecdsa-spki")))
	checkSig("ecdsa-sha256 signature verifies",
		pkcrypto.HashAndVerifySignature(ecPub, msg, unhexSig(sigField(src, "ecdsa-sig"))) == nil)

	rsaPub := parsePub(unhexSig(sigField(src, "rsa-spki")))
	checkSig("rsa-pss-sha256 signature verifies",
		pkcrypto.HashAndVerifySignature(rsaPub, msg, unhexSig(sigField(src, "rsa-pss-sig"))) == nil)

	digest := sha256.Sum256(msg)
	checkSig("rsa-pkcs1-sha256 signature verifies",
		rsa.VerifyPKCS1v15(rsaPub.(*rsa.PublicKey), crypto.SHA256, digest[:],
			unhexSig(sigField(src, "rsa-pkcs1-sig"))) == nil)

	// and the two RSA schemes really are distinct, not accidentally the same
	// bytes — otherwise the vector would prove nothing about telling them apart
	checkSig("the two RSA signatures differ",
		sigField(src, "rsa-pss-sig") != sigField(src, "rsa-pkcs1-sig"))
	checkSig("pkcs1 does not verify as pss",
		pkcrypto.HashAndVerifySignature(rsaPub, msg, unhexSig(sigField(src, "rsa-pkcs1-sig"))) != nil)

	pub, err := storj.PiecePublicKeyFromBytes(unhexSig(sigField(src, "ed25519-public-key")))
	if err != nil {
		panic(err)
	}
	checkSig("ed25519 piece signature verifies",
		pub.Verify(msg, unhexSig(sigField(src, "ed25519-sig"))) == nil)
	checkSig("the recorded piece key is a raw ed25519 key",
		len(unhexSig(sigField(src, "ed25519-public-key"))) == ed25519.PublicKeySize)

	// the end-to-end order limit
	ctx := context.Background()
	var limit pb.OrderLimit
	if err := pb.Unmarshal(unhexSig(sigField(src, "order-limit-wire")), &limit); err != nil {
		panic(err)
	}
	signee := &signing.PublicKey{Key: ecPub}
	checkSig("the recorded order limit's satellite signature verifies",
		signing.VerifyOrderLimitSignature(ctx, signee, &limit) == nil)

	encoded, err := signing.EncodeOrderLimit(ctx, &limit)
	if err != nil {
		panic(err)
	}
	checkSig("the recorded signing bytes are what EncodeOrderLimit produces",
		hex.EncodeToString(encoded) == sigField(src, "order-limit-signing-bytes"))
}

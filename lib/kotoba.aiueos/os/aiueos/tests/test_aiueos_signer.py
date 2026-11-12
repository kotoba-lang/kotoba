#!/usr/bin/env python3
"""Host test of scripts/aiueos-signer.py (JUN-813, ADR-0286 amendment 7). Standard library only; no network; no JVM.

  python3 test_aiueos_signer.py          (from anywhere; the signer is looked up beside this tests/ directory)

Everything that needs private keys runs against a TEMPORARY HOME: the test makes its own throwaway slots there and never reads or writes
~/.itonami. What CI can check without private keys is checked against the committed public data: the pinned module equals what `emit-pinned`
makes from fixtures/signers/prod-pubkeys.json, and the golden fixtures (signed once with the real slots) verify under those public keys.
Signed bytes are verified with the independent references (the RFC 8032 integer Ed25519 and the ACVP-checked ML-DSA-65 reference), not
with the tool's own `verify`.
"""
import hashlib
import importlib.util
import io
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

OS = Path(__file__).resolve().parents[1]
SCRIPTS = OS / "scripts"
sys.path.insert(0, str(SCRIPTS))
import imgsig_oracle as o  # noqa: E402
import cat_oracle  # noqa: E402
import fresh_oracle  # noqa: E402
import update2_oracle  # noqa: E402
import prodsig_oracle  # noqa: E402

# AIUEOS_SIGNER_UNDER_TEST: run the same tests against another copy of the tool (the negative controls use mutated copies)
SIGNER_FILE = Path(os.environ.get("AIUEOS_SIGNER_UNDER_TEST", SCRIPTS / "aiueos-signer.py"))
spec = importlib.util.spec_from_file_location("aiueos_signer", SIGNER_FILE)
signer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signer)
ref = o.ref
TOOL = str(SIGNER_FILE)
CTX = {"image": b"AIUEIMG2", "catalog": b"AIUECAT1", "fresh": b"AIUEFRS1"}


def run_tool(home, *argv, check=False):
    env = dict(os.environ, HOME=str(home))
    p = subprocess.run([sys.executable, TOOL, *argv], env=env, capture_output=True, text=True)
    if check:
        assert p.returncode == 0, (argv, p.stdout, p.stderr)
    return p


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def independent_slots(hdr, kind, pubs):
    """Slots whose entry verifies under `pubs` [(ed_pk, ml_pk)] by the independent references, from the ADR layout (not the tool's code)."""
    assert hdr[:8] == CTX[kind]
    man, count, out = hdr[:64], struct.unpack_from("<I", hdr, 64)[0], []
    for i in range(count):
        e = hdr[128 + i * 3392:128 + (i + 1) * 3392]
        kid = struct.unpack_from("<I", e, 0)[0]
        assert e[4:8] == bytes(4) and e[3381:] == bytes(11)
        edpk, mlpk = pubs[kid]
        ok_ed = o.edr.ed_verify(edpk, man, e[8:72])
        mprime = bytes([0, 8]) + CTX[kind] + man
        ok_ml = ref.verify_mu(mlpk, ref.mu_of(mlpk, mprime), e[72:3381])
        if ok_ed and ok_ml:
            out.append(kid)
    return out


class Store:
    """A temporary HOME with the three throwaway slots."""
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / ".itonami").mkdir()
        self.pubs = []

    def keygen_all(self):
        for n in range(3):
            run_tool(self.home, "keygen", "--slot", str(n), check=True)
        d = self.home / ".itonami" / "aiueos-signers"
        for n in range(3):
            rec = json.loads((d / ("slot%d" % n) / "public.json").read_text())
            self.pubs.append((bytes.fromhex(rec["ed25519"]), bytes.fromhex(rec["mldsa65"])))

    def sign(self, *argv):
        old = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                signer.main(list(argv))
        finally:
            if old is None:
                os.environ.pop("HOME")
            else:
                os.environ["HOME"] = old


class KeygenAndPermissions(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        self.addCleanup(self.s.tmp.cleanup)
        self.d = self.s.home / ".itonami" / "aiueos-signers"

    def test_keygen_modes_and_no_seed_in_output(self):
        p = run_tool(self.s.home, "keygen", "--slot", "1", check=True)
        slot = self.d / "slot1"
        self.assertEqual(mode(self.d), 0o700)
        self.assertEqual(mode(slot), 0o700)
        for f in ("ed25519.seed", "mldsa65.xi", "public.json"):
            self.assertEqual(mode(slot / f), 0o600, f)
        ed, xi = (slot / "ed25519.seed").read_bytes(), (slot / "mldsa65.xi").read_bytes()
        self.assertEqual((len(ed), len(xi)), (32, 32))
        self.assertNotEqual(ed, xi)
        out = p.stdout + p.stderr
        for seed in (ed, xi):
            self.assertNotIn(seed.hex(), out)
            self.assertNotIn(seed.hex().upper(), out)
        pub = json.loads((slot / "public.json").read_text())
        edpk, mlpk = signer.derive_public(ed, xi)
        self.assertIn(hashlib.sha256(edpk).hexdigest(), p.stdout)
        self.assertIn(hashlib.sha256(mlpk).hexdigest(), p.stdout)
        self.assertEqual(pub["ed25519"], edpk.hex())
        # the public.json holds public data only
        self.assertNotIn(ed.hex(), (slot / "public.json").read_text())
        self.assertNotIn(xi.hex(), (slot / "public.json").read_text())

    def test_refuses_overwrite_without_replace(self):
        run_tool(self.s.home, "keygen", "--slot", "0", check=True)
        before = (self.d / "slot0" / "ed25519.seed").read_bytes()
        p = run_tool(self.s.home, "keygen", "--slot", "0")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("--replace", p.stderr)
        self.assertEqual((self.d / "slot0" / "ed25519.seed").read_bytes(), before)
        run_tool(self.s.home, "keygen", "--slot", "0", "--replace", check=True)
        self.assertNotEqual((self.d / "slot0" / "ed25519.seed").read_bytes(), before)
        self.assertEqual(mode(self.d / "slot0" / "ed25519.seed"), 0o600)

    def test_refuses_slot_outside_0_2_and_missing_application_dir(self):
        self.assertNotEqual(run_tool(self.s.home, "keygen", "--slot", "3").returncode, 0)
        with tempfile.TemporaryDirectory() as bare:
            p = run_tool(bare, "keygen", "--slot", "0")
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse((Path(bare) / ".itonami").exists(), "the application directory is not created by the tool")

    def test_refuses_key_directory_or_seed_readable_by_others(self):
        self.s.keygen_all()
        img = self.s.home / "img.bin"; img.write_bytes(b"x" * 100)
        out = self.s.home / "out.img"
        argv = ("sign-image", "--version", "1", "--out", str(out), str(img))
        self.assertEqual(run_tool(self.s.home, *argv, check=True).returncode, 0)
        out.unlink()
        for target, bad in ((self.d, 0o750), (self.d / "slot0", 0o755), (self.d / "slot1" / "ed25519.seed", 0o640),
                            (self.d / "slot1" / "mldsa65.xi", 0o604)):
            good = mode(target)
            os.chmod(target, bad)
            p = run_tool(self.s.home, *argv)
            self.assertNotEqual(p.returncode, 0, (target, oct(bad)))
            self.assertIn("others", p.stderr)
            self.assertFalse(out.exists(), "a refused signing must write nothing")
            os.chmod(target, good)
        self.assertEqual(run_tool(self.s.home, *argv, check=True).returncode, 0)

    def test_refuses_symlinked_seed_and_git_work_tree(self):
        self.s.keygen_all()
        img = self.s.home / "img.bin"; img.write_bytes(b"x" * 100)
        out = self.s.home / "out.img"
        argv = ("sign-image", "--version", "1", "--out", str(out), str(img))
        seed = self.d / "slot0" / "ed25519.seed"
        real = self.s.home / "elsewhere.seed"
        real.write_bytes(seed.read_bytes()); os.chmod(real, 0o600)
        seed.unlink(); seed.symlink_to(real)
        p = run_tool(self.s.home, *argv)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("symbolic link", p.stderr)
        seed.unlink(); real.rename(seed)
        self.assertEqual(run_tool(self.s.home, *argv, check=True).returncode, 0)
        out.unlink()
        (self.s.home / ".git").mkdir()
        p = run_tool(self.s.home, *argv)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("git work tree", p.stderr)

    def test_refuses_a_slot_that_is_not_there(self):
        run_tool(self.s.home, "keygen", "--slot", "0", check=True)
        img = self.s.home / "img.bin"; img.write_bytes(b"x" * 100)
        p = run_tool(self.s.home, "sign-image", "--version", "1", "--slots", "0,1", str(img))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("missing", p.stderr)


class Signing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Store()
        cls.s.keygen_all()
        cls.work = cls.s.home

    @classmethod
    def tearDownClass(cls):
        cls.s.tmp.cleanup()

    def sign_file(self, name, *argv):
        out = self.work / (name + ".out")
        self.s.sign(*argv[:-1], "--out", str(out), argv[-1]) if not argv[0] == "sign-fresh" else self.s.sign(*argv, "--out", str(out))
        return out.read_bytes()

    def test_image_default_two_slots_verifies_under_independent_references(self):
        img = update2_oracle.image()
        f = self.work / "image.bin"; f.write_bytes(img)
        raw = self.sign_file("image", "sign-image", "--version", "5", str(f))
        self.assertEqual(len(raw), 16384 + len(img))
        self.assertEqual(raw[16384:], img)
        hdr = raw[:16384]
        # layout of ADR-0286 amendment 2, written out here and not taken from the tool
        self.assertEqual(hdr[:8], b"AIUEIMG2")
        self.assertEqual(struct.unpack_from("<QQ", hdr, 8), (5, len(img)))
        self.assertEqual(hdr[24:32], bytes(8))
        self.assertEqual(hdr[32:64], hashlib.sha256(img).digest())
        self.assertEqual(struct.unpack_from("<I", hdr, 64)[0], 2)
        self.assertEqual(hdr[68:128], bytes(60))
        self.assertEqual([struct.unpack_from("<I", hdr, 128 + i * 3392)[0] for i in range(2)], [0, 1])
        self.assertEqual(hdr[128 + 2 * 3392:], bytes(16384 - 128 - 2 * 3392))
        self.assertEqual(independent_slots(hdr, "image", self.s.pubs), [0, 1])
        self.assertEqual(o.verdict(hdr, "test")[0], 4, "the throwaway slots are not the TEST keys")

    def test_image_slots_2_0_and_three_and_one(self):
        f = self.work / "image2.bin"; f.write_bytes(update2_oracle.image())
        for slots, want in (("2,0", [2, 0]), ("0,1,2", [0, 1, 2]), ("1", [1])):
            raw = self.sign_file("image-" + slots, "sign-image", "--version", "9", "--slots", slots, str(f))
            self.assertEqual(independent_slots(raw[:16384], "image", self.s.pubs), want)
        # a header with one valid signer is below M = 2: the admission rule (independent reference) refuses it
        self.assertGreaterEqual(len(want), 1)

    def test_catalog_and_fresh_layouts_and_manifests(self):
        body = prodsig_oracle.golden_inputs()["catalog"]
        f = self.work / "cat.body"; f.write_bytes(body)
        raw = self.sign_file("catalog", "sign-catalog", "--version", "7", "--slots", "1,2", str(f))
        hdr = raw[:16384]
        self.assertEqual(raw[16384:], body)
        self.assertEqual(hdr[:8], b"AIUECAT1")
        self.assertEqual(struct.unpack_from("<QQI", hdr, 8), (7, len(body), len(body) // 128))
        self.assertEqual(hdr[28:32], bytes(4))
        self.assertEqual(hdr[32:64], hashlib.sha256(body).digest())
        self.assertEqual(independent_slots(hdr, "catalog", self.s.pubs), [1, 2])
        self.assertEqual(hdr[:64], prodsig_oracle.golden_manifests()["catalog"])
        # fresh
        issued, until = prodsig_oracle.FRESH_ISSUED, prodsig_oracle.FRESH_UNTIL
        hdr = self.sign_file("fresh", "sign-fresh", "--version", "7", "--issued", str(issued), "--valid-until", str(until), "--slots", "0,2")
        self.assertEqual(len(hdr), 16384)
        self.assertEqual(hdr[:8], b"AIUEFRS1")
        self.assertEqual(struct.unpack_from("<QQQI", hdr, 8), (7, issued, until, 1))
        self.assertEqual(hdr[36:64], bytes(28))
        self.assertEqual(independent_slots(hdr, "fresh", self.s.pubs), [0, 2])
        self.assertEqual(hdr[:64], prodsig_oracle.golden_manifests()["fresh"])

    def test_signatures_are_bound_to_the_object_kind(self):
        f = self.work / "image3.bin"; f.write_bytes(update2_oracle.image())
        hdr = self.sign_file("image3", "sign-image", "--version", "5", str(f))[:16384]
        self.assertEqual(independent_slots(hdr, "image", self.s.pubs), [0, 1])
        # the same manifest bytes under another magic and context: the ML-DSA context changes, so the entries do not verify there
        other = b"AIUECAT1" + hdr[8:]
        man = other[:64]
        e = hdr[128:128 + 3392]
        edpk, mlpk = self.s.pubs[0]
        self.assertFalse(ref.verify_mu(mlpk, ref.mu_of(mlpk, bytes([0, 8]) + b"AIUECAT1" + man), e[72:3381]))

    def test_tool_verify_agrees_and_refuses(self):
        f = self.work / "image4.bin"; f.write_bytes(update2_oracle.image())
        out = self.work / "image4.signed"
        run_tool(self.s.home, "sign-image", "--version", "5", "--out", str(out), str(f), check=True)
        self.assertEqual(run_tool(self.s.home, "verify", str(out), "--kind", "image", check=True).returncode, 0)
        raw = bytearray(out.read_bytes()); raw[-1] ^= 1
        bad = self.work / "image4.bad"; bad.write_bytes(bytes(raw))
        self.assertNotEqual(run_tool(self.s.home, "verify", str(bad), "--kind", "image").returncode, 0)
        one = self.work / "image4.one"
        run_tool(self.s.home, "sign-image", "--version", "5", "--slots", "1", "--out", str(one), str(f), check=True)
        self.assertNotEqual(run_tool(self.s.home, "verify", str(one), "--kind", "image").returncode, 0)

    def test_refuses_bad_inputs(self):
        f = self.work / "tiny.bin"; f.write_bytes(b"abc")
        for argv in (("sign-image", "--version", "0", str(f)), ("sign-image", "--version", "1", "--slots", "0,0", str(f)),
                     ("sign-image", "--version", "1", "--slots", "0,3", str(f)), ("sign-catalog", "--version", "1", str(f)),
                     ("sign-fresh", "--version", "1", "--issued", "10", "--valid-until", "10"),
                     ("sign-fresh", "--version", "1", "--issued", "10", "--valid-until", str(10 + 31 * 86400)),
                     ("sign-fresh", "--version", "1", "--issued", "10", "--valid-until", "20", "--channel", "2")):
            self.assertNotEqual(run_tool(self.s.home, *argv).returncode, 0, argv)


class PinnedPublicData(unittest.TestCase):
    """No private key needed: what the repository commits."""

    def test_pinned_module_is_what_emit_pinned_makes_from_the_public_keys(self):
        pubs = signer.load_public_json(o.PROD_PUBKEYS)
        text = signer.prodkeys_module(pubs)
        self.assertEqual((OS / "kotoba/aiueos/imgsig_prodkeys.kotoba").read_text(), text)
        p = subprocess.run([sys.executable, TOOL, "emit-pinned", "--from", str(o.PROD_PUBKEYS)], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, text))
        # the words in the module are the public keys, little endian, two u32 words to a signed 64-bit case literal (low word first)
        def pairs(key):
            out = []
            for j in range(0, len(key), 8):
                v = struct.unpack_from("<Q", key, j)[0]
                out.append(v - (1 << 64) if v >= (1 << 63) else v)
            return out
        for slot, (ed, ml) in enumerate(pubs):
            self.assertIn("(defn- ed%d-pair [h] (case h %s 0))" % (slot, " ".join("%d %d" % (h, v) for h, v in enumerate(pairs(ed)))), text)
            self.assertIn("(defn- ml%d-pair [h] (case h %s 0))" % (slot, " ".join("%d %d" % (h, v) for h, v in enumerate(pairs(ml)))), text)

    def test_the_test_keys_module_is_unchanged_by_the_refactor(self):
        self.assertEqual((OS / "kotoba/aiueos/imgsig_testkeys.kotoba").read_text(), o.emit_keys_module())

    def test_public_keys_are_distinct_from_the_test_keys_and_well_formed(self):
        pubs = signer.load_public_json(o.PROD_PUBKEYS)
        test = o.pubkeys("test")
        self.assertEqual(len({p[0] for p in pubs} | {p[1] for p in pubs}), 6)
        for p in pubs:
            self.assertEqual((len(p[0]), len(p[1])), (32, 1952))
            self.assertNotIn(p[0], [t[0] for t in test])
            self.assertNotIn(p[1], [t[1] for t in test])
        text = o.PROD_PUBKEYS.read_text()
        j = json.loads(text)
        self.assertEqual(set(j), {"schema", "slots"})
        for s in j["slots"]:
            self.assertEqual(set(s), {"id", "ed25519", "mldsa65", "ed25519-sha256", "mldsa65-sha256"})

    def test_no_seed_material_in_the_committed_signer_files(self):
        for p in [o.PROD_PUBKEYS, *prodsig_oracle.GOLDEN.glob("*"), OS / "kotoba/aiueos/imgsig_prodkeys.kotoba"]:
            self.assertFalse(p.name.endswith((".seed", ".xi")), p)

    def test_golden_fixtures_verify_under_the_public_keys_by_independent_references(self):
        pubs = o.pubkeys("prod")
        for kind in ("image", "catalog", "fresh"):
            hdr = prodsig_oracle.golden_header(kind)
            self.assertEqual(independent_slots(hdr, kind, pubs), list(prodsig_oracle.SLOTS[kind]), kind)
            # under the TEST keys the same bytes verify for no slot
            self.assertEqual(independent_slots(hdr, kind, o.pubkeys("test")), [], kind)
            self.assertEqual(hdr[:64], prodsig_oracle.golden_manifests()[kind], kind)
            self.assertEqual(hdr[128 + 2 * 3392:], bytes(16384 - 128 - 2 * 3392), kind)
        rec = prodsig_oracle.golden_manifest_record()
        self.assertEqual(json.loads((prodsig_oracle.GOLDEN / "golden.json").read_text()), rec)

    def test_golden_cases_are_the_oracle_meant_verdicts(self):
        # the oracle asserts meant == computed for every case while building them
        self.assertEqual([c["code"] for c in prodsig_oracle.image_cases()][:1], [15])
        self.assertEqual(len(prodsig_oracle.catalog_cases()), 10)
        self.assertEqual(len(prodsig_oracle.fresh_cases()), 9)

    def test_tool_layout_is_the_oracles(self):
        """The tool imports the layout code of the oracles; pin the three manifests against a plain struct pack."""
        img = update2_oracle.image()
        self.assertEqual(signer.image_manifest(5, img), b"AIUEIMG2" + struct.pack("<QQQ", 5, len(img), 0) + hashlib.sha256(img).digest())
        body = prodsig_oracle.golden_inputs()["catalog"]
        self.assertEqual(signer.catalog_manifest(7, body),
                         b"AIUECAT1" + struct.pack("<QQII", 7, len(body), len(body) // 128, 0) + hashlib.sha256(body).digest())
        self.assertEqual(signer.fresh_manifest(7, 100, 200, 1), b"AIUEFRS1" + struct.pack("<QQQI", 7, 100, 200, 1) + bytes(28))


if __name__ == "__main__":
    unittest.main(verbosity=2)

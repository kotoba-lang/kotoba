"""pytest plugin: record every XML built by kotoba_iso20022 during the test run."""
import functools, hashlib, os, pathlib
OUT = pathlib.Path(os.environ["ISO_DUMP_DIR"])

def pytest_configure(config):
    import kotoba_iso20022 as pkg
    from kotoba_iso20022 import codec, bah
    names = [n for n in dir(codec) if n.startswith("build_")] + ["build_bah", "build_business_message"]
    for name in names:
        mod = bah if name in ("build_bah", "build_business_message") else codec
        orig = getattr(mod, name, None)
        if orig is None:
            continue
        @functools.wraps(orig)
        def wrapper(*a, __orig=orig, __name=name, **k):
            xml = __orig(*a, **k)
            if isinstance(xml, str):
                h = hashlib.sha256(xml.encode()).hexdigest()[:12]
                (OUT / f"{__name}-{h}.xml").write_text(xml, encoding="utf-8")
            return xml
        setattr(mod, name, wrapper)
        if hasattr(pkg, name):
            setattr(pkg, name, wrapper)

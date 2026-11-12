#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# copy current host sources of the codegen chain into the JVM's first classpath root, staged like build-native-image.py
S=${KR_WORK:-/tmp/kotoba-route}; H=$(cd "$(dirname "$0")" && pwd)
D=$S/jvm/src
mkdir -p $D/kotoba/native $D/kotoba/codegen
python3 - $D <<'P'
import sys, re, glob, os, importlib.util
spec = importlib.util.spec_from_file_location("b", "/private/tmp/wt-A-amu-measure/scripts/build-native-image.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
D = sys.argv[1]
pairs = [(f, f"{D}/kotoba/native/{os.path.basename(f)[:-5]}.cljc") for f in glob.glob("/private/tmp/wt-D-kotoba-native/src/kotoba/native/*.cljk") if not f.endswith("elf64.clj.cljk")]
pairs += [(f, f"{D}/kotoba/codegen/{os.path.basename(f)[:-5]}.cljc") for f in glob.glob("/private/tmp/wt-D-kotoba-codegen/src/kotoba/codegen/*.cljk")]
pairs += [("/private/tmp/wt-D-osaho/src/kotoba/kir.cljk", f"{D}/kotoba/kir.cljc")]
pairs += [("/private/tmp/wt-D-kotoba-mir/src/kotoba/mir.cljk", f"{D}/kotoba/mir.cljc"), ("/private/tmp/wt-D-kotoba-gmir/src/kotoba/gmir.cljk", f"{D}/kotoba/gmir.cljc")]
for src, dst in pairs:
    t = open(src).read()
    t = b.quote_ns_exports(t)
    t = re.sub(r"\(catch\s+(?:js/Error|:default)\s", "(catch Throwable ", t)
    open(dst, "w").write(t)
P

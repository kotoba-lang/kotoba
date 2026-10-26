#!/bin/sh
set -eu

ARCH="${1:-aarch64}"
case "$ARCH" in
  aarch64) PLATFORM=linux/arm64 ;;
  x86_64) PLATFORM=linux/amd64 ;;
  *) echo "unsupported architecture: $ARCH" >&2; exit 2 ;;
esac

kbb -T:build uber
rm -rf target/jre-linux target/linux-runtime-root
mkdir -p target

docker run --rm --platform "$PLATFORM" \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" -w /work eclipse-temurin:25-jdk \
  sh -eu -c '
    /opt/java/openjdk/bin/jlink \
      --add-modules java.base,java.logging,java.management,java.naming,java.xml,jdk.crypto.ec,jdk.unsupported \
      --strip-debug --no-header-files --no-man-pages --compress=zip-6 \
      --output target/jre-linux
    mkdir -p target/linux-runtime-root
    find target/jre-linux -type f \( -name java -o -name "*.so" \) -print0 |
      xargs -0 -n1 ldd 2>/dev/null |
      awk "match(\$0, /\/[[:graph:]]+/) { print substr(\$0, RSTART, RLENGTH) }" |
      sed "s/[()]$//" | sort -u |
      while read lib; do
        [ -f "$lib" ] && cp --parents "$lib" target/linux-runtime-root/
      done
  '

file target/jre-linux/bin/java

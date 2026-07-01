class Kotoba < Formula
  desc "CLJC/EDN-authoritative Kotoba CLI launcher"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "cdf1099d970aa6e5be0e88099fc58bcefea58cadec63392863c3b7538a883655"
  license "Apache-2.0"
  head "https://github.com/kotoba-lang/kotoba.git", branch: "main"

  depends_on "clojure"

  def install
    libexec.install "deps.edn", "src", "bin"
    (bin/"kotoba").write <<~EOS
      #!/bin/sh
      export KOTOBA_CLJ_HOME="#{libexec}"
      exec "#{libexec}/bin/kotoba-clj" "$@"
    EOS
  end

  test do
    ENV["KOTOBA_CLJ_HOME"] = libexec
    out = shell_output("#{bin}/kotoba check --kind cli-contract --json")
    assert_match "kotoba.cli", out
    assert_match "command-count", out
  end
end

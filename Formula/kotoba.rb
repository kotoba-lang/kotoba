class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.26.tar.gz"
  sha256 "942c3adc2420a00f154eb08bc988a69326e9eae9adf16893e92a1b2cd6ae60b1"
  license "Apache-2.0"

  bottle do
    root_url "https://github.com/kotoba-lang/homebrew-kotoba/releases/download/kotoba-0.6.26"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "b3081c12ff606b14de543a5178d676112cb447206298ccfedf2f8bb15acac408"
    sha256 cellar: :any_skip_relocation, sequoia:       "b29e055a450652ab4795021da7535b8bc531f2c9cd3c6bd88e09b6b8f187b2a4"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "87932e53358d202af5ce5e4907acc63ae636039b188d09cc9e1f0f7f1250958a"
  end

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.26/kotoba-darwin-arm64.tar.gz"
        sha256 "3d9eb436982229e0333f5f09e4ca371e2a80cf6d4abee170fa51ce83eda3bfa2"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.26/kotoba-darwin-amd64.tar.gz"
        sha256 "b192f279325a0a1dd7bbd4380410c445fbf9439a6b96902594d6ba76510fb312"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.26/kotoba-linux-amd64.tar.gz"
      sha256 "5596a1de5a0fb8c7ca1409d1c4ffdcbeaa1b3161d3cbb9d360ee1cb4bc76329c"
    end
  end

  def install
    resource("binary").stage do
      bin.install "kotoba"
    end
  end

  test do
    output = shell_output("#{bin}/kotoba selfhost check --json")
    assert_match '"kotoba.cli\\/ok?":true', output
    assert_match '"kotoba.cli\\/code":"valid"', output

    (testpath/"safe-window-name.kotoba").write <<~KOTOBA
      (ns homebrew.timing (:export [shot-hit]))
      (defn shot-hit [delta-present delta-ms window-ms]
        (if delta-present (if (<= delta-ms window-ms) 1 0) 0))
    KOTOBA
    output = shell_output(
      "#{bin}/kotoba compile #{testpath}/safe-window-name.kotoba " \
      "--target web -o #{testpath}/safe-window-name.mjs --json",
    )
    assert_match '"kotoba.cli\\/code":"emitted"', output
    assert_match "k$window$002dms", (testpath/"safe-window-name.mjs").read

    (testpath/"src/shared").mkpath
    (testpath/"src/shared/value.cljc").write <<~CLJC
      (ns shared.value "bounded bottle project documentation" (:export [answer]))
      (defn answer [] 42)
    CLJC
    (testpath/"main.cljc").write <<~CLJC
      (ns shared.app
        (:require [shared.value :as value])
        (:export [main]))
      (defn main [] (value/answer))
    CLJC
    output = shell_output(
      "#{bin}/kotoba compile #{testpath}/main.cljc " \
      "--source-path #{testpath}/src --target web " \
      "--output #{testpath}/shared-app.mjs --json",
    )
    assert_match '"kotoba.cli\\/code":"emitted"', output
    assert_match '"kotoba.artifact\\/module-graph-digest"', output
    assert_path_exists testpath/"shared-app.mjs"
  end
end

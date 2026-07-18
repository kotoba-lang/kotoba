class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.25.tar.gz"
  sha256 "480a3063de1ff9bfc068f5fc2b8f7a11873b7abb0f3c9683c2af7bc15d747e12"
  license "Apache-2.0"

  bottle do
    root_url "https://github.com/kotoba-lang/homebrew-kotoba/releases/download/kotoba-0.6.25"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "7612b1639eaa03e7c606fdd5d634190fccc733a709feca635d3a396c582b9612"
    sha256 cellar: :any_skip_relocation, sequoia:       "d38eb2a47062fd72c9ad76a4485e51101f3d7bbf40b1fcd15f51b9d3884e028d"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "f1e9c7766418275147b31caff2e6e32a8c50cc7b1211f5e559f5f81e0fe9c7c3"
  end

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.25/kotoba-darwin-arm64.tar.gz"
        sha256 "f1f14e5bfb32bf0eaff320b803fcaf9fd218fe061f87aacf4727958e5bcf4b98"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.25/kotoba-darwin-amd64.tar.gz"
        sha256 "34ba8d2645f9e1cee5114e272964095684bf5b63c39fdcae2b4fdfa150714667"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.25/kotoba-linux-amd64.tar.gz"
      sha256 "c682a06aba5e183ea54341dea1fedf7362e3eae380568c4b640cc6e770e8ee32"
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
      (ns shared.value (:export [answer]))
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

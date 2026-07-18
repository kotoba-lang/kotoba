class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.24.tar.gz"
  sha256 "03c29ddb270158f643e0a50e5d9b2cdeae1e9c43443062c23f0b4882a226b850"
  license "Apache-2.0"

  bottle do
    root_url "https://github.com/kotoba-lang/homebrew-kotoba/releases/download/kotoba-0.6.24"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "fbfbd1ccaa59d39e5da0314afe1fa6adadd037d52e4587b80884555c56596a2b"
    sha256 cellar: :any_skip_relocation, sequoia:       "0cb15520a604b7cbacfd943ec9344a6c052b6e4d4d0811a05edde8a286af6f52"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "eea1767476181760cbdd60ab4c09d132e779725f9582e9ea0d852f2bdbfc5e85"
  end

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.24/kotoba-darwin-arm64.tar.gz"
        sha256 "35da0c32a9d5961f5c8b12eda02f25ce115f3792b5496971bb80efb752ff1a64"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.24/kotoba-darwin-amd64.tar.gz"
        sha256 "e992c078eddd105ff939cc0ad3b44f24e8b487117bccc666118a202f968fa0e7"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.24/kotoba-linux-amd64.tar.gz"
      sha256 "a0a5985d356f282fac578e0d51ad76ab388c97f27d788d8e02400a950706f822"
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

    (testpath/"shared").mkpath
    (testpath/"shared/value.cljc").write <<~CLJC
      (ns shared.value (:export [answer]))
      (defn answer [] 42)
    CLJC
    (testpath/"shared/app.cljc").write <<~CLJC
      (ns shared.app
        (:require [shared.value :as value])
        (:export [main]))
      (defn main [] (value/answer))
    CLJC
    output = shell_output(
      "#{bin}/kotoba compile #{testpath}/shared/app.cljc " \
      "--source-path #{testpath} --target web " \
      "--output #{testpath}/shared-app.mjs --json",
    )
    assert_match '"kotoba.cli\\/code":"emitted"', output
    assert_match '"kotoba.artifact\\/module-graph-digest"', output
    assert_path_exists testpath/"shared-app.mjs"
  end
end

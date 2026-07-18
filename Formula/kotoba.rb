class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.23.tar.gz"
  sha256 "580527ad8961aa957a0595efea41afecb77aa5f3e3f6d79c2405414a02ac437a"
  license "Apache-2.0"

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.23/kotoba-darwin-arm64.tar.gz"
        sha256 "bafd50e53b662090711ce58573bd7dc05206be2937ceb59d935a18a32b803fff"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.23/kotoba-darwin-amd64.tar.gz"
        sha256 "f52b1c2fbc711fc7d4953e47e9eb4e76deb2d763277d7b959d85867c0f227825"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.23/kotoba-linux-amd64.tar.gz"
      sha256 "5998b8be5c3f5a6af75bf5173ceed2305ff267cee9007ec0d9ca6fbb652c0830"
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
  end
end

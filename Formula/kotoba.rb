class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.22.tar.gz"
  sha256 "71bf92b90cd10c5bbaa990c992b769351810cc54d29107c1e4811b57f58c31e7"
  license "Apache-2.0"

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.22/kotoba-darwin-arm64.tar.gz"
        sha256 "b985d1b81688a113daf134488d5d5904a791cd1f4a107ac9307aa6bd49b82582"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.22/kotoba-darwin-amd64.tar.gz"
        sha256 "1f5ca13d5981cf1b598460a584e093441ddd878280b18c15cda09595d7c94a91"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.22/kotoba-linux-amd64.tar.gz"
      sha256 "9d0280e0b8f44eaa0842b749bfa58ffa8d92465bc41d85080de69eaa3c8afdd2"
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
  end
end

class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.1.tar.gz"
  sha256 "bcb06b31fb01d015ccc7fc0c3085fdce26735fcfb7f30aa90f5c757bdd6a8138"
  license "Apache-2.0"

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.1/kotoba-darwin-arm64.tar.gz"
        sha256 "50c17d701f7a157ae065f5c104774acc80c0f229df45ed842da97ba7aeb4578b"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.1/kotoba-darwin-amd64.tar.gz"
        sha256 "93491c872329be5607aae0a446a0bac30c7f6e58cb43e20ee60cd154bcc3651f"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.1/kotoba-linux-amd64.tar.gz"
      sha256 "08885fd9a6ba847b25cc6b85753298f6ba829fb2b7e016c9f137fc415ffa482d"
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

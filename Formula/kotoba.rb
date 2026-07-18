class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.27.tar.gz"
  sha256 "77dab7775100a58d3e8299a2215fc5524607c35fea02d952c5e2227ac73fe803"
  license "Apache-2.0"

  bottle do
    root_url "https://github.com/kotoba-lang/homebrew-kotoba/releases/download/kotoba-0.6.27"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "89217b55b9f20a01f0fab929f0fa138636c705c27c2f8f6c158ae6e9e77a7851"
    sha256 cellar: :any_skip_relocation, sequoia:       "5fde5b6d21fd522284d4bcd055d063a6c53a1b40b2f8ac07888419cda078aa8a"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "cf9514156138c845da143e1cc021cb34675517b6fe385cacc5d94ea0fe263b45"
  end

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.27/kotoba-darwin-arm64.tar.gz"
        sha256 "7768c0de0a770453282132811015fea68264bf84c3853505699164e4d6a9a086"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.27/kotoba-darwin-amd64.tar.gz"
        sha256 "45e06484c4fb4183c9a9ba138ab1dbea2fec32544a77ecd225be04750e830b88"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.27/kotoba-linux-amd64.tar.gz"
      sha256 "74091a517b8b5871cef723b675c9a34f786c3c1ee7e4c166bde1ead9668c95ef"
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

    (testpath/"typed/fixture").mkpath
    (testpath/"typed/fixture/coverage.kotoba").write <<~KOTOBA
      (ns fixture.coverage (:export [ready?]))
      (defn ready? [covered [:set :keyword]] :bool
        (typed-set-contains [:set :keyword] covered :ready))
    KOTOBA
    (testpath/"typed/fixture/app.kotoba").write <<~KOTOBA
      (ns fixture.app
        (:require [fixture.coverage :as coverage])
        (:export [main]))
      (defn main [] :i64
        (if (coverage/ready? (typed-set [:set :keyword] :ready)) 42 0))
    KOTOBA
    web = shell_output(
      "#{bin}/kotoba compile #{testpath}/typed/fixture/app.kotoba " \
      "--source-path #{testpath}/typed --target web " \
      "--output #{testpath}/typed-app.mjs --json",
    )
    assert_match '"kotoba.artifact\\/value-profile":"typed-v1"', web
    assert_match '"kotoba.artifact\\/module-graph-digest"', web
    wasm = shell_output(
      "#{bin}/kotoba compile #{testpath}/typed/fixture/app.kotoba " \
      "--source-path #{testpath}/typed --target wasm " \
      "--output #{testpath}/typed-app.wasm --json",
    )
    assert_match '"value-profile":"typed-v1"', wasm
    assert_match '"value-abi":"externref-v1"', wasm
    assert_path_exists testpath/"typed-app.wasm"
  end
end

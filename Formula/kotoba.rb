class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.28.tar.gz"
  sha256 "bf39efc9be56d29e608d46fdff46b36dd92b87e431392718de6474596047467d"
  license "Apache-2.0"

  bottle do
    root_url "https://github.com/kotoba-lang/homebrew-kotoba/releases/download/kotoba-0.6.28"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "e2391c550bfc0f82bbc49ee332d980817480ad4b8c9d5418859421ca26143336"
    sha256 cellar: :any_skip_relocation, sequoia:       "bfeb93ef8a148ec97b9936db0e304733343b7ba7c006cc342281aca5372fb7bd"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "11084b4d0d6a19900ce554d1985fef7f837f1e96947fb1471bd1fd6ec3bc3531"
  end

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.28/kotoba-darwin-arm64.tar.gz"
        sha256 "9e34cf3dbe3cdc8caca38247fc33c34f8fb3b37cf960baf8da0de815f501a092"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.28/kotoba-darwin-amd64.tar.gz"
        sha256 "d4ca17bbc3486918a03f6effe7aae30f3b4e7a9144a57dea9757022f136939ca"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.28/kotoba-linux-amd64.tar.gz"
      sha256 "cc02e7887fd16bfd16dd249cfb3ebe52f866f97285dabb6059617cc2de56668a"
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
      (ns fixture.coverage (:export [none-report make-report choose-report]))
      (defn none-report []
        [:option [:record :fixture/report [[:value :i64]]]]
        (option-none-of [:option [:record :fixture/report [[:value :i64]]]]))
      (defn make-report [] [:record :fixture/report [[:value :i64]]]
        (record [:record :fixture/report [[:value :i64]]] 42))
      (defn choose-report
        [left [:option [:record :fixture/report [[:value :i64]]]]
         right [:option [:record :fixture/report [[:value :i64]]]]]
        [:option [:record :fixture/report [[:value :i64]]]]
        (match-option left [:option [:record :fixture/report [[:value :i64]]]]
          (none right)
          (some left-report
            (match-option right [:option [:record :fixture/report [[:value :i64]]]]
              (none left)
              (some right-report right)))))
    KOTOBA
    (testpath/"typed/fixture/app.kotoba").write <<~KOTOBA
      (ns fixture.app
        (:require [fixture.coverage :as coverage])
        (:export [main]))
      (defn main [] :i64
        (record-get [:record :fixture/report [[:value :i64]]]
          (option-value-of [:option [:record :fixture/report [[:value :i64]]]]
            (coverage/choose-report
              (coverage/none-report)
              (option-some-of [:option [:record :fixture/report [[:value :i64]]]]
                (coverage/make-report)))
            (coverage/make-report))
          :value))
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

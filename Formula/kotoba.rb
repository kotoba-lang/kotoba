class Kotoba < Formula
  desc "Capability-safe Kotoba language compiler and CLI"
  homepage "https://github.com/kotoba-lang/kotoba"
  url "https://github.com/kotoba-lang/kotoba/archive/refs/tags/v0.6.29.tar.gz"
  sha256 "f3e21f81f6435ff540ff93036d6632e26424d7f7fb52ff157d8b6a30cfb57a10"
  license "Apache-2.0"

  bottle do
    root_url "https://github.com/kotoba-lang/homebrew-kotoba/releases/download/kotoba-0.6.29"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "6ce6056e61dc0f025c69db7c49e6a93711b5d0189d9b980a0dc61ff34869776b"
    sha256 cellar: :any_skip_relocation, sequoia:       "758278ae6998cd44debb282fe1d91d5026c3519e5cc0c28833b9df29621211c9"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "f50be4a03e9c127df193de22e7f1694960ad61190ecb57243ac97c432d1e5da3"
  end

  resource "binary" do
    on_macos do
      on_arm do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.29/kotoba-darwin-arm64.tar.gz"
        sha256 "35835c5495388084b2987403d20cbccab2e5e02667a45db068e8a83e342c9b47"
      end
      on_intel do
        url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.29/kotoba-darwin-amd64.tar.gz"
        sha256 "395a369c51dbecd54348256b77e6eef3d5e1c8fdb13d58eee42ffe2eeeb1d067"
      end
    end
    on_linux do
      url "https://github.com/kotoba-lang/kotoba/releases/download/v0.6.29/kotoba-linux-amd64.tar.gz"
      sha256 "287ddf7874d3e198a941f011b3bdc4a6032d6d15e191be83c686231163ccb508"
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
      (ns fixture.coverage
        (:export [ready? make-report none-report choose-report covered-count map-score]))
      (def label-map-type [:map :keyword :string])
      (defn ready? [covered [:set :keyword]] :bool
        (typed-set-contains [:set :keyword] covered :ready))
      (defn none-report []
        [:option [:record :fixture/report
                  [[:label :string] [:covered [:set :keyword]]]]]
        (option-none-of
          [:option [:record :fixture/report
                    [[:label :string] [:covered [:set :keyword]]]]]))
      (defn make-report []
        [:record :fixture/report [[:label :string] [:covered [:set :keyword]]]]
        (record
          [:record :fixture/report [[:label :string] [:covered [:set :keyword]]]]
          "qualified" (typed-set [:set :keyword] :ready :reviewed)))
      (defn choose-report
        [left [:option [:record :fixture/report
                        [[:label :string] [:covered [:set :keyword]]]]]
         right [:option [:record :fixture/report
                         [[:label :string] [:covered [:set :keyword]]]]]]
        [:option [:record :fixture/report
                  [[:label :string] [:covered [:set :keyword]]]]]
        (match-option left
          [:option [:record :fixture/report
                    [[:label :string] [:covered [:set :keyword]]]]]
          (none right)
          (some left-report
            (match-option right
              [:option [:record :fixture/report
                        [[:label :string] [:covered [:set :keyword]]]]]
              (none left)
              (some right-report right)))))
      (defn covered-count
        [report [:record :fixture/report
                 [[:label :string] [:covered [:set :keyword]]]]]
        :i64
        (typed-set-count [:set :keyword]
          (record-get
            [:record :fixture/report [[:label :string] [:covered [:set :keyword]]]]
            report :covered)))
      (defn map-score [] :i64
        (let [labels (typed-map-assoc label-map-type
                       (typed-map-assoc label-map-type
                         (typed-map-new label-map-type) :ready "yes")
                       :reviewed "yes")
              first-entry (option-value-of
                            [:option [:vector [:keyword :string]]]
                            (typed-map-entry-at label-map-type labels 0)
                            (hetero-vector [:vector [:keyword :string]] :missing "no"))]
          (if (= (typed-map-count label-map-type labels) 2)
            (if (typed-map-contains label-map-type labels :ready)
              (if (string=?
                    (option-value-of [:option :string]
                      (typed-map-get label-map-type labels :reviewed) "no")
                    "yes")
                (if (= (hetero-vector-count
                         [:vector [:keyword :string]] first-entry) 2)
                  2
                  0)
                0)
              0)
            0)))
    KOTOBA
    (testpath/"typed/fixture/app.kotoba").write <<~KOTOBA
      (ns fixture.app
        (:require [fixture.coverage :as coverage])
        (:export [main]))
      (defn main [] :i64
        (let [covered (typed-set [:set :keyword] :ready :reviewed)]
          (if (coverage/ready? covered)
            (if (string=? "Kotoba" "Kotoba")
              (+ 38
                (coverage/map-score)
                (coverage/covered-count
                  (option-value-of
                    [:option [:record :fixture/report
                              [[:label :string] [:covered [:set :keyword]]]]]
                    (coverage/choose-report
                      (coverage/none-report)
                      (option-some-of
                        [:option [:record :fixture/report
                                  [[:label :string] [:covered [:set :keyword]]]]]
                        (coverage/make-report)))
                    (coverage/make-report))))
              1)
            0)))
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

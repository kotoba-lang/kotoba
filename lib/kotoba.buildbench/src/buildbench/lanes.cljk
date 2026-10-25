(ns buildbench.lanes
  "The toolchain lanes, and what each one has to prove before it is timed.

  A lane is not just a command. It is a command plus the check that the thing
  the command produced is the program we asked for. Without that second half
  a build-time benchmark measures how fast a compiler can be wrong: the
  fastest way to emit an artifact is to emit a broken one.

  Every lane therefore reports one of three things, and they are never the
  same value:

    :measured      — samples, and the artifact answered correctly
    :unavailable   — the tool is not on this host (never 0, never omitted)
    :invalid       — the tool ran and produced something that is not the
                     program; the error text is kept, not discarded"
  (:require ["node:child_process" :as cp]
            ["node:fs" :as fs]
            ["node:path" :as path]
            ["node:os" :as os]
            [clojure.string :as str]))

(defn- home [] (or (.-HOME (.-env js/process)) ""))

(defn first-existing [paths]
  (first (filter #(and % (fs/existsSync %)) paths)))

(defn which [cmd]
  (let [r (cp/spawnSync "which" #js [cmd] #js {:encoding "utf8"})]
    (when (zero? (.-status r)) (str/trim (.-stdout r)))))

(defn version-of
  "The tool's version, or its resolved path when it has no version command.

  `kotoba` 0.7.3 has no `--version` and answers `--help` with a usage error,
  so the naive probe records a JSON error object as the version string and
  anything downstream prints it as though it were one. When the probe does
  not come back looking like a version, fall back to the realpath — Homebrew
  keeps the version in it, and a path is at least true."
  [cmd args]
  (let [r (cp/spawnSync cmd (clj->js args) #js {:encoding "utf8"})
        line (when r (first (str/split-lines (str/trim (str (.-stdout r) (.-stderr r))))))
        version-ish? (and line
                          (< (count line) 120)
                          (re-find #"\d+\.\d+" line)
                          (not (str/starts-with? line "{")))]
    (cond
      version-ish? line
      (fs/existsSync cmd) (try (fs/realpathSync cmd) (catch :default _ cmd))
      :else line)))

;; ── artifact validation ──────────────────────────────────────────────────

(defn validate-wasm
  "Instantiate the module and call its entry. Returns nil on success, or a
  string saying what went wrong — which is how the LEB128 function-index
  overflow in the released 0.7.3 emitter was found rather than timed."
  [file entry expected]
  (try
    (let [bytes (fs/readFileSync file)
          module (js/WebAssembly.Module. bytes)
          instance (js/WebAssembly.Instance. module #js {})
          f (aget (.-exports instance) entry)]
      (cond
        (nil? f) (str "module exports no " entry)
        :else (let [v (f)
                    n (js/Number v)]
                (when-not (= n expected)
                  (str entry "() returned " n ", expected " expected)))))
    (catch :default e (str "instantiate failed: " (.-message e)))))

(defn validate-kexe
  "A sealed Kotoba executable is an EDN header followed by machine code, not
  a Mach-O or ELF image, so it is checked structurally: the format marker has
  to be there and there has to be a payload behind it.

  This is a weaker check than the Wasm lanes get, which are instantiated and
  called. Saying so is the point — an unexecuted artifact must not be
  reported as if it had answered."
  [file _expected]
  (try
    (let [b (fs/readFileSync file)
          head (.toString (.subarray b 0 64) "utf8")]
      (cond
        (not (str/starts-with? head "{:format :kotoba.kexe/v1"))
        (str "not a sealed kexe: begins " (pr-str (subs head 0 (min 32 (count head)))))
        (< (.-length b) 512)
        (str "kexe is " (.-length b) " bytes: header with no meaningful payload")
        :else nil))
    (catch :default e (str "read failed: " (.-message e)))))

(defn validate-magic [file magic what]
  (try
    (let [b (fs/readFileSync file)]
      (if (< (.-length b) (count magic))
        (str what " is " (.-length b) " bytes, too short to be a " what)
        (let [head (map #(aget b %) (range (count magic)))]
          (when-not (= (vec head) (vec magic))
            (str what " has magic "
                 (str/join " " (map #(.toString % 16) head))
                 ", expected " (str/join " " (map #(.toString % 16) magic)))))))
    (catch :default e (str "read failed: " (.-message e)))))

(def jdk-home
  "A JDK that can actually run, not just a stub that suggests installing one.

  macOS ships a `/usr/bin/javac` shim that exits with an advertisement when no
  JDK is present. Resolving `javac` through `which` therefore finds a lane that
  looks available and fails every sample, which is a worse answer than
  `unavailable`."
  (first (filter #(fs/existsSync (path/join % "javac"))
                 ["/opt/homebrew/opt/openjdk/bin"
                  "/usr/local/opt/openjdk/bin"
                  "/opt/homebrew/bin"
                  "/usr/bin"])))

(defn- jdk-tool [n] (when jdk-home (path/join jdk-home n)))

(defn- jdk-runnable? []
  (when-let [j (jdk-tool "java")]
    (let [r (cp/spawnSync j #js ["-version"] #js {:encoding "utf8"})]
      (zero? (or (.-status r) 1)))))

(defn validate-jvm [dir expected]
  (or (validate-magic (path/join dir "Main.class") [0xCA 0xFE 0xBA 0xBE] "JVM class")
      (let [r (cp/spawnSync (jdk-tool "java") #js ["-cp" dir "Main"] #js {:encoding "utf8"})]
        (when-not (zero? (or (.-status r) 1))
          (str "java -cp " dir " Main exited " (.-status r) ": "
               (str/trim (str (.-stderr r))))))))

;; Mach-O 64-bit little-endian: cf fa ed fe
(def macho-magic [0xCF 0xFA 0xED 0xFE])
;; ELF
(def elf-magic [0x7F 0x45 0x4C 0x46])

(defn- native-magic []
  (if (= "darwin" (.-platform js/process)) macho-magic elf-magic))

(defn- native-target []
  (let [arch (.-arch js/process)
        os (.-platform js/process)
        os-suffix (case os "darwin" "macos" "linux" "linux" "win32" "windows" nil)]
    (when os-suffix
      (str (case arch "arm64" "aarch64" "x64" "x86_64" nil) "-" os-suffix))))

;; ── lane definitions ─────────────────────────────────────────────────────
;;
;; `amu` is a repository path, not a global binary, so it is passed in.

(defn write-fuel-policy!
  "Kotoba declares resource bounds that C, Rust and Java do not.

  A Kotoba module carries a call-fuel budget, and the default is 512 calls —
  which the workload crosses at exactly K=512, where `main` calls 512 leaves.
  Measured naively, the Kotoba lane starts 'failing' there, and a benchmark
  would be publishing a correctly-enforced resource bound as a compiler
  defect. It is the opposite of a defect: it is the language refusing to emit
  a module that can run longer than its author declared.

  So the bound is raised explicitly and recorded in the report, rather than
  being tripped over. The comparators have no equivalent to raise."
  [dir fuel]
  (let [p (path/join dir "buildbench-fuel.edn")]
    (fs/writeFileSync p (str "{:budgets {:fuel " fuel "}}\n"))
    p))

(def probe-sources
  "A two-line program in each language, for the pre-timing probe."
  {:kotoba {:filename "main.kotoba" :source "(defn main [] :i64\n  (+ 40 2))\n"}
   :rust {:filename "main.rs"
          :source "#[unsafe(no_mangle)]\npub extern \"C\" fn main() -> i64 { 42 }\n"}
   :c {:filename "main.c" :source "long long main(void) { return 42; }\n"}
   :java {:filename "Main.java"
          :source "public final class Main {\n  public static void main(String[] a) {}\n}\n"}})

(defn probe
  "Build a two-line program through one lane, before anything is timed.

  Returns nil if the lane works, or the tool's own error text if it does not.
  Used for two decisions, both of which have to happen before the clock
  starts: whether a fuel policy is accepted at all, and whether a lane that
  looks installed can actually reach its target. A host with Apple Clang has
  a `clang` on `PATH` that cannot emit wasm32 — reporting that as `failed`
  at every size would bury a host capability gap in the results as though it
  were a property of the workload.

  Used to decide whether a lane's fuel policy is accepted at all: kotoba
  0.7.1 rejects `{:budgets {:fuel n}}` as a malformed capability policy while
  0.7.3 accepts it. A lane that cannot take the policy still runs — at the
  compiler default — and the report records which lanes got the raised bound
  rather than implying all of them did."
  [lane]
  (let [dir (fs/mkdtempSync (path/join (os/tmpdir) "buildbench-probe-"))]
    (try
      (doseq [[_ {:keys [filename source]}] probe-sources]
        (fs/writeFileSync (path/join dir filename) source))
      (let [out (path/join dir (:output lane))
            [cmd argv] ((:argv lane) dir out)
            r (cp/spawnSync cmd (clj->js argv) #js {:encoding "utf8" :cwd dir})]
        (when-not (zero? (or (.-status r) 1))
          (str/trim (subs (str (.-stderr r) (.-stdout r)) 0 300))))
      (catch :default e (str "probe threw: " (.-message e)))
      (finally (fs/rmSync dir #js {:recursive true :force true})))))

(defn lane-works? [lane] (nil? (probe lane)))

(defn lanes
  [{:keys [amu clang fuel-policy]}]
  (let [amu-bin (when (and amu (fs/existsSync (path/join amu "bin" "amu")))
                  (path/join amu "bin" "amu"))
        clang-bin (or clang (which "clang"))
        wasm-clang (or (when (fs/existsSync "/opt/homebrew/opt/llvm/bin/clang")
                         "/opt/homebrew/opt/llvm/bin/clang")
                       clang-bin)
        nt (native-target)
        ;; A rustup toolchain carries the wasm32 std that a Homebrew rustc
        ;; usually does not, so prefer it — and let the probe decide whether
        ;; the choice actually reaches the target.
        rustc-bin (or (first-existing [(path/join (home) ".cargo" "bin" "rustc")])
                      (which "rustc"))]
    (->>
     [{:id :kotoba-wasm-cli
       :label "Kotoba CLI"
       :target "WebAssembly"
       :note "the released kotoba binary, the artifact a user installs today"
       :language :kotoba
       :tool (which "kotoba")
       :version-cmd ["kotoba" ["compile" "--help"]]
       :argv (fn [dir out] ["kotoba" (cond-> ["compile" (path/join dir "main.kotoba")
                                              "--target" "wasm" "--output" out "--json"]
                                       fuel-policy (into ["--policy" fuel-policy]))])
       :output "cli.wasm"
       :validate (fn [out _dir expected] (validate-wasm out "main" expected))}

      {:id :amu-wasm
       :label "Amu"
       :target "WebAssembly"
       :note "the current compiler, process-cold, hosted on nbb"
       :language :kotoba
       :tool amu-bin
       :version-cmd (when amu-bin ["git" ["-C" amu "rev-parse" "--short" "HEAD"]])
       :argv (fn [dir out] [amu-bin (cond-> ["compile" (path/join dir "main.kotoba")
                                             "--target" "wasm32" "--output" out]
                                      fuel-policy (into ["--policy" fuel-policy]))])
       :output "amu.wasm"
       :validate (fn [out _dir expected] (validate-wasm out "main" expected))}

      {:id :amu-native
       :label "Amu"
       :target (str "Native " (or nt "unsupported"))
       :note "AOT machine code, process-cold, hosted on nbb"
       :language :kotoba
       :tool (when nt amu-bin)
       :version-cmd (when amu-bin ["git" ["-C" amu "rev-parse" "--short" "HEAD"]])
       :argv (fn [dir out] [amu-bin (cond-> ["compile" (path/join dir "main.kotoba")
                                             "--target" nt "--output" out]
                                      fuel-policy (into ["--policy" fuel-policy]))])
       :output "amu.kexe"
       :validate (fn [out _dir expected] (validate-kexe out expected))}

      {:id :rustc-wasm
       :label "Rust / rustc"
       :target "WebAssembly"
       :language :rust
       :tool rustc-bin
       :version-cmd (when rustc-bin [rustc-bin ["--version"]])
       :argv (fn [dir out] [rustc-bin ["--edition=2024" "--crate-type=cdylib"
                                     "--target=wasm32-unknown-unknown"
                                     "-C" "opt-level=0" "-C" "debuginfo=0"
                                     "-C" "panic=abort"
                                     "-o" out (path/join dir "main.rs")]])
       :output "rust.wasm"
       :validate (fn [out _dir expected] (validate-wasm out "main" expected))}

      {:id :rustc-native
       :label "Rust / rustc"
       :target "Native host"
       :language :rust
       :tool rustc-bin
       :version-cmd (when rustc-bin [rustc-bin ["--version"]])
       :argv (fn [dir out] [rustc-bin ["--edition=2024" "--crate-type=cdylib"
                                     "-C" "opt-level=0" "-C" "debuginfo=0"
                                     "-o" out (path/join dir "main.rs")]])
       :output (if (= "darwin" (.-platform js/process)) "librust.dylib" "librust.so")
       :validate (fn [out _dir _expected]
                   (validate-magic out (native-magic) "native image"))}

      {:id :clang-wasm
       :label "C / Clang"
       :target "WebAssembly"
       :language :c
       :tool wasm-clang
       :version-cmd (when wasm-clang [wasm-clang ["--version"]])
       :argv (fn [dir out] [wasm-clang ["--target=wasm32" "-O0" "-nostdlib"
                                        "-Wno-main-return-type"
                                        "-Wl,--no-entry" "-Wl,--export=main"
                                        "-o" out (path/join dir "main.c")]])
       :output "c.wasm"
       :validate (fn [out _dir expected] (validate-wasm out "main" expected))}

      {:id :clang-native
       :label "C / Clang"
       :target "Native host"
       :language :c
       :tool clang-bin
       :version-cmd (when clang-bin [clang-bin ["--version"]])
       :argv (fn [dir out] [clang-bin ["-O0" "-shared" "-Wno-main-return-type"
                                       "-o" out (path/join dir "main.c")]])
       :output (if (= "darwin" (.-platform js/process)) "libc.dylib" "libc.so")
       :validate (fn [out _dir _expected]
                   (validate-magic out (native-magic) "native image"))}

      {:id :javac
       :label "JVM / javac"
       :target "JVM class"
       :language :java
       :tool (when (jdk-runnable?) (jdk-tool "javac"))
       :version-cmd (when (jdk-runnable?) [(jdk-tool "javac") ["-version"]])
       :argv (fn [dir out] [(jdk-tool "javac")
                            ["-g:none" "-d" out (path/join dir "Main.java")]])
       :output "jout"
       :output-dir? true
       :validate (fn [out _dir expected] (validate-jvm out expected))}]
     (map (fn [lane] (assoc lane :available? (some? (:tool lane)))))
     vec)))

(ns bim.interchange.dwg
  "Verified DWG export through an explicitly configured DXF→DWG converter."
  (:require [bim.interchange :as interchange]
            [kotoba.lang.text :as string])
  (:import [java.nio.charset StandardCharsets]
           [java.nio.file Files Path StandardOpenOption]
           [java.nio.file.attribute FileAttribute]))

(def supported-signatures
  #{"AC1009" "AC1012" "AC1014" "AC1015" "AC1018" "AC1021" "AC1024"
    "AC1027" "AC1032"})

(defn- substitute [argument input output]
  (-> argument
      (string/replace "{input}" (str input))
      (string/replace "{output}" (str output))))

(defn- dwg-signature [^Path path]
  (when (and (Files/isRegularFile path (make-array java.nio.file.LinkOption 0))
             (<= 6 (Files/size path)))
    (String. (Files/readAllBytes path) 0 6 StandardCharsets/US_ASCII)))

(defn export-floor-plan!
  "Generate DXF and invoke a configured converter command. The command vector
  must contain {input} and {output} placeholders. Success requires exit code 0
  and a recognized Autodesk DWG file signature; DXF bytes are never mislabeled
  as DWG. Returns output metadata, leaving the DWG at output-path."
  [storey output-path {:keys [command annotations environment]}]
  (when-not (and (sequential? command)
                 (some #(string/includes? % "{input}") command)
                 (some #(string/includes? % "{output}") command))
    (throw (ex-info "DWG converter command requires {input} and {output} placeholders"
                    {:command command})))
  (let [input (Files/createTempFile "kotoba-bim-dwg-" ".dxf"
                                    (make-array FileAttribute 0))
        output (.toAbsolutePath (.normalize (Path/of (str output-path) (make-array String 0))))]
    (try
      (Files/writeString input (interchange/floor-plan-dxf storey {:annotations annotations})
                         StandardCharsets/UTF_8
                         (into-array StandardOpenOption [StandardOpenOption/WRITE
                                                         StandardOpenOption/TRUNCATE_EXISTING]))
      (let [arguments (mapv #(substitute % input output) command)
            builder (ProcessBuilder. arguments)
            _ (doseq [[key value] environment] (.put (.environment builder) key (str value)))
            process (.start builder)
            status (.waitFor process)
            signature (dwg-signature output)]
        (when-not (zero? status)
          (throw (ex-info "DWG converter failed" {:exit status :command (first command)})))
        (when-not (contains? supported-signatures signature)
          (throw (ex-info "converter output is not a recognized DWG"
                          {:output (str output) :signature signature})))
        {:dwg/path (str output) :dwg/signature signature :dwg/size (Files/size output)})
      (finally (Files/deleteIfExists input)))))

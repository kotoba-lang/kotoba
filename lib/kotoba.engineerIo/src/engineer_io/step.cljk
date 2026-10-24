(ns engineer-io.step
  "STEP file header/footer generator (AP214 subset). Restored from
  kami-eng-io's `step` module (deleted PR #82).")

(defn generate-header
  "A minimal STEP AP214 header for `filename`, authored by `author`."
  [filename author]
  (str "ISO-10303-21;\nHEADER;\n"
       "FILE_DESCRIPTION(('KAMI Engineering SDK export'), '2;1');\n"
       "FILE_NAME('" filename "', '2026-04-09', ('" author "'), "
       "('etzhayyim'), 'KAMI-ENG-SDK', 'kami-cad', '');\n"
       "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\n"
       "ENDSEC;\nDATA;\n"))

(defn generate-footer
  "The fixed STEP file footer."
  []
  "ENDSEC;\nEND-ISO-10303-21;\n")

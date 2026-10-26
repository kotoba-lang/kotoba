# aiueos desktop IME dictionary

`aiueos-kanji.dic` is the kana-kanji dictionary the guest browser desktop's
input method converts through (ADR-0235). It travels in the initramfs as
`ime/aiueos-kanji.dic`, like the font, and the kernel hands it to Kotoba
`kotoba_aiueos_browser_key`. The hosted IME oracle
(`src/aiueos/compositor/ime.cljk`) reads the same file.

- **Source:** Unicode 17.0.0 Unihan database, `Unihan.zip`,
  <https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip>. SHA-256 of the
  fetched zip (2026-09-25):
  `f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e`.
  Two of its files are read: `Unihan_Readings.txt` (`kJapanese`, each kanji's
  readings in kana) and `Unihan_OtherMappings.txt` (`kJoyoKanji`,
  `kJinmeiyoKanji`, for the candidate order).
- **License:** Unicode License v3 (`Unicode-License-v3.txt` beside this
  file). Copyright © 1991-2026 Unicode, Inc.
- **Contents:** every kanji of `os/aiueos/fonts/aiueos-16.fnt` (the JIS X 0208
  kanji, 6,355), 6,344 of them with readings; 3,871 readings, 23,679
  reading/kanji pairs, the longest reading 10 code points, the most
  candidates 345 (こう). 189,892 bytes.
- **What it is not:** a word dictionary. Every candidate is one kanji. Unihan
  does not mark where a kun reading's okurigana starts, so a kun reading is a
  whole word (くわえる) and converts to the kanji alone (加). There is no
  learning and no frequency beyond the order rule.
- **Candidate order** (the rule is written in the generator's header):
  Jouyou, then Jinmeiyou, then the rest of JIS level 1, then level 2; within
  a tier, the reading's position in the kanji's own `kJapanese` list; then
  code point. か gives 下 仮 何 佳 価 加 …, やま 山 岾, しょう 傷 償 勝 ….
- **Rebuild / check** (with `Unihan.zip` unpacked into `<dir>`):

  ```sh
  kbb --backend sci os/aiueos/scripts/gen-ime-dictionary.cljk <dir> os/aiueos/fonts/aiueos-16.fnt os/aiueos/ime/aiueos-kanji.dic
  kbb --backend sci os/aiueos/scripts/gen-ime-dictionary.cljk --check <dir> os/aiueos/fonts/aiueos-16.fnt os/aiueos/ime/aiueos-kanji.dic
  ```

  The format (`aiueos-dict/v1`) is described in the header of
  `os/aiueos/scripts/gen-ime-dictionary.cljk`.

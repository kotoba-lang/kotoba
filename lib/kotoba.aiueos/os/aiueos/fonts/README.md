# aiueos desktop font

`aiueos-16.fnt` is the font the guest browser desktop draws with (ADR-0224).
It travels in the initramfs as `font/aiueos-16.fnt`.

- **Source:** GNU Unifont 17.0.05, `unifont_jp-17.0.05.bdf.gz`
  (Japanese glyph forms), <https://ftp.gnu.org/gnu/unifont/unifont-17.0.05/>.
  SHA-256 of the fetched `.bdf.gz`:
  `d3a4c98e41efcf38b49bd520a049230cc040d44433ab9c2cdcd9f1f481443976`.
  The GNU detached signature was fetched but not checked (the signing key
  `95D2E9AB8740D8046387FD151A09227B1F435A33` was not retrievable from the
  keyservers tried on 2026-09-24).
- **License:** Unifont glyphs are dual licensed since 13.0.04 (Unifont NEWS):
  SIL Open Font License 1.1, or GNU GPL v2+ with the GNU font embedding
  exception. This subset is used and redistributed under the **SIL OFL 1.1**
  (`OFL-1.1.txt` beside this file). Copyright (C) 1998-2026 Roman Czyborra,
  Paul Hardy, Qianqian Fang, Andrew Miller, Johnnie Weaver, David Corbett,
  and the other Unifont contributors.
- **Subset:** every code point JIS X 0208 can name, printable ASCII, U+3000,
  U+FFFD -- 7,422 glyphs, 267,208 bytes.
- **Rebuild / check:**

  ```sh
  kbb --backend sci --classpath ../text/src os/aiueos/scripts/make-font.cljk unifont_jp-17.0.05.bdf os/aiueos/fonts/aiueos-16.fnt
  kbb --backend sci --classpath ../text/src os/aiueos/scripts/make-font.cljk --check unifont_jp-17.0.05.bdf os/aiueos/fonts/aiueos-16.fnt
  ```

  The format (`aiueos-font/v1`) is described in the header of
  `os/aiueos/scripts/make-font.cljk`.

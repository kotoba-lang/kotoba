/* browser-ime built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object (same ABI).
   Inputs are the kernel's own: each trajectory starts from main.c's guest-browser surface (the boot record, the
   aiueos / ブラウザ titles and bodies, a 1920x1080, 1280x800 or 1024x768 viewport, the font and dictionary the
   initramfs carries, fonts/aiueos-16.fnt and ime/aiueos-kanji.dic, linked in by assets.S) and runs main.c's desktop
   loop: a tablet batch (press, release, move, wheel, gesture, at the launcher, the dock, the tray, a window's
   titlebar, controls, resize handle or body, or anywhere) sets words 2046 / 2047 / 2029 / 2033 and goes to
   browser-reduce; a key (code * 4 + value: the stages' keys, letters, digits, symbols, modifiers, editing and window
   keys, any code, and readings typed as romaji then converted, cycled, committed or cancelled) goes to browser-ime
   with the dictionary, and its answer is followed as main.c follows it (a PIN
   verdict, a clipboard completion against a 260-byte clipboard, a press, a focus); C's own writes come in between
   (a notification, the settings body, the clock, the network state, the contrast, the app register, a scale); every
   event ends with browser-frame2. Then edge cases: states with random words set, fully random states, and every
   length the export checks (state 0 / 127 / 128 / 129 / 8191 / 8192 / 8193 / 2^40, a null state, a dictionary,
   clipboard or font of other lengths or null). Every call of the object under test runs the old and the native
   object on two copies of the state (and clipboard) through the #UD guard and compares the answer, the trap and
   every state and clipboard byte; the trajectory goes on from the old object's state. The other two objects are
   the kernel's objects in kotoba/. The font and dictionary are checked unchanged at the end. */
#include "diff.h"
#define TESTED 1 /* 1 browser-ime, 2 browser-reduce, 3 browser-frame2 */
extern int64_t kotoba_aiueos_browser_key(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_browser_reduce(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_browser_frame2(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_browser_key_native(int64_t, int64_t, int64_t, int64_t, int64_t);
extern const uint8_t font_blob[], font_blob_end[], dict_blob[], dict_blob_end[];
#define P_S 0x51570000000000a1ll  /* stands for the state copy */
#define P_CP 0x51570000000000a2ll /* stands for the clipboard copy */
static uint32_t S[2048 + 16] __attribute__((aligned(64))), A[2048 + 16] __attribute__((aligned(64))), B[2048 + 16] __attribute__((aligned(64)));
static uint32_t CP[65 + 16] __attribute__((aligned(64))), CPA[65 + 16] __attribute__((aligned(64))), CPB[65 + 16] __attribute__((aligned(64)));
static int64_t FONT, DICT, FONTN, DICTN;
static unsigned n_calls, n_traj, n_steps, n_edge;
static int dead; /* the trajectory trapped */
static uint32_t seq;
static uint32_t queue[64]; static unsigned q_n, q_at; /* a reading being typed */
static uint64_t fnv(const uint8_t *p, uint64_t n) { uint64_t h = 1469598103934665603ull; for (uint64_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; } return h; }
static uint32_t pick(const uint32_t *v, unsigned n) { return v[rnd() % n]; }
static int64_t sub(int64_t a, uint32_t *st, uint32_t *cp) { return a == P_S ? (int64_t)(uintptr_t)st : a == P_CP ? (int64_t)(uintptr_t)cp : a; }
/* the object under test: old on A (and CPA), native on B (and CPB); the state goes on from A */
static int64_t tested(int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4) {
  void *fo, *fn = (void *)kotoba_aiueos_browser_key_native;
#if TESTED == 1
  fo = (void *)kotoba_aiueos_browser_key;
#elif TESTED == 2
  fo = (void *)kotoba_aiueos_browser_reduce;
#else
  fo = (void *)kotoba_aiueos_browser_frame2;
#endif
  for (int i = 0; i < 2048 + 16; i++) A[i] = B[i] = S[i];
  for (int i = 0; i < 65 + 16; i++) CPA[i] = CPB[i] = CP[i];
  int64_t r1 = guarded_call(fo, sub(a0, A, CPA), sub(a1, A, CPA), sub(a2, A, CPA), sub(a3, A, CPA), sub(a4, A, CPA)); int t1 = (int)guard_trapped;
  int64_t r2 = guarded_call(fn, sub(a0, B, CPB), sub(a1, B, CPB), sub(a2, B, CPB), sub(a3, B, CPB), sub(a4, B, CPB)); int t2 = (int)guard_trapped;
  int eq = r1 == r2 && t1 == t2, at = -1;
  for (int i = 0; i < 2048 + 16; i++) if (A[i] != B[i]) { eq = 0; if (at < 0) at = i; }
  for (int i = 0; i < 65 + 16; i++) if (CPA[i] != CPB[i]) { eq = 0; if (at < 0) at = 10000 + i; }
  n_all++; if (t1) n_trap++; else if (r1 != 0) n_nz++;
  if (!eq && n_bad++ < 10) {
    puts_("DIFF "); hex(n_all, 8); hex((uint64_t)a1, 16); hex((uint64_t)a2, 16); hex((uint64_t)a3, 16); hex((uint64_t)a4, 16);
    hex((uint64_t)r1, 16); hex((uint64_t)t1, 1); hex((uint64_t)r2, 16); hex((uint64_t)t2, 1); hex((uint64_t)at, 8);
    if (at >= 0 && at < 2064) { hex(A[at], 8); hex(B[at], 8); }
    putc_('\n');
  }
  for (int i = 0; i < 2048 + 16; i++) S[i] = A[i];
  for (int i = 0; i < 65 + 16; i++) CP[i] = CPA[i];
  if (t1) dead = 1;
  return r1;
}
static int64_t direct(void *f, int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4) {
  int64_t r = guarded_call(f, sub(a0, S, CP), sub(a1, S, CP), sub(a2, S, CP), sub(a3, S, CP), sub(a4, S, CP));
  if (guard_trapped) dead = 1;
  return r;
}
static int64_t KEY(int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4) {
  n_calls += TESTED == 1;
  return TESTED == 1 ? tested(a0, a1, a2, a3, a4) : direct((void *)kotoba_aiueos_browser_key, a0, a1, a2, a3, a4);
}
static int64_t REDUCE(int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4) {
  n_calls += TESTED == 2;
  return TESTED == 2 ? tested(a0, a1, a2, a3, a4) : direct((void *)kotoba_aiueos_browser_reduce, a0, a1, a2, a3, a4);
}
static int64_t FRAME(int64_t a0, int64_t a1, int64_t a2, int64_t a3) {
  n_calls += TESTED == 3;
  return TESTED == 3 ? tested(a0, a1, a2, a3, 0) : direct((void *)kotoba_aiueos_browser_frame2, a0, a1, a2, a3, 0);
}
/* main.c's guest-browser surface */
static const uint32_t boot[15] = {1, 2, 2, 0, 0, 1, 32, 32, 720, 540, 2, 96, 72, 640, 480};
static const uint32_t title1[] = {97, 105, 117, 101, 111, 115};
static const uint32_t body1[] = {107, 111, 116, 111, 98, 97, 45, 108, 97, 110, 103, 47, 98, 114, 111, 119, 115, 101, 114, 10, 12502, 12521, 12454, 12470, 12364, 30011, 38754, 12391, 12377};
static const uint32_t title2[] = {12502, 12521, 12454, 12470};
static const uint32_t body2[] = {26085, 26412, 35486, 12398, 25991, 23383, 12418, 34920, 31034, 12391, 12365, 12414, 12377, 12290};
static const uint32_t title4[5] = {12473, 12463, 12525, 12540, 12523};
static void init_state(void) {
  static const uint32_t vws[3] = {1920, 1280, 1024}, vhs[3] = {1080, 800, 768};
  unsigned v = (unsigned)(rnd() % 3);
  for (int i = 0; i < 2048 + 16; i++) S[i] = 0;
  for (int i = 0; i < 65 + 16; i++) CP[i] = 0;
  for (int i = 0; i < 15; i++) S[i] = boot[i];
  S[3] = vws[v]; S[4] = vhs[v];
  for (unsigned i = 0; i < sizeof(title1) / 4; i++) S[32 + i] = title1[i];
  for (unsigned i = 0; i < sizeof(body1) / 4; i++) S[160 + i] = body1[i];
  for (unsigned i = 0; i < sizeof(title2) / 4; i++) S[64 + i] = title2[i];
  for (unsigned i = 0; i < sizeof(body2) / 4; i++) S[224 + i] = body2[i];
  if (rnd() % 2) { /* the later stages: four windows, the app register, the scroll stage's window 4 */
    static const uint32_t w34[10] = {3, 160, 120, 600, 400, 4, 80, 80, 520, 360};
    S[1] = 4; for (int i = 0; i < 10; i++) S[15 + i] = w34[i];
    for (unsigned i = 0; i < 5; i++) S[128 + i] = title4[i];
    unsigned b = 0;
    for (uint32_t line = 1; line <= 20; line++) {
      if (line >= 10) S[352 + b++] = 48U + line / 10U;
      S[352 + b++] = 48U + line % 10U;
      if (line < 20) S[352 + b++] = 10U;
      if (b > 60) break;
    }
    S[31] = rnd() % 2 ? 15 : 7; S[2] = 1 + (uint32_t)(rnd() % 4);
  } else if (rnd() % 2) S[31] = rnd() % 2 ? 7 : 8;
  if (rnd() % 3 == 0) S[432] = 1;
  if (rnd() % 4 == 0) S[1970] = 1;
  seq = 0; dead = 0; q_n = q_at = 0;
}
static void notify_post(const char *text) {
  for (uint32_t k = 0; k < 4U; k++) {
    uint32_t base = 1971U + 8U * k;
    if (S[base] == 0) {
      uint32_t i = 0;
      for (; i < 7U && text[i]; i++) S[base + 1U + i] = (uint32_t)(uint8_t)text[i];
      for (; i < 7U; i++) S[base + 1U + i] = 0;
      S[base] = 1U;
      return;
    }
  }
}
static uint32_t put_text(uint32_t at, const char *t) { while (*t) S[at++] = (uint32_t)(uint8_t)*t++; return at; }
static void c_write(void) {
  switch (rnd() % 9) {
  case 0: notify_post(rnd() % 2 ? "Saved" : "Wi-Fi on"); break;
  case 1: { uint32_t at = put_text(224, rnd() % 2 ? "Contrast: High" : "Contrast: Normal"); S[at++] = 10U;
            at = put_text(at, "Scale: 125%"); S[at++] = 10U; at = put_text(at, "Network: On"); while (at < 288U) S[at++] = 0; } break;
  case 2: S[1968] = 1 + (uint32_t)(rnd() % 1440); break;
  case 3: S[1969] = (uint32_t)(rnd() % 4); break;
  case 4: S[2039] = (uint32_t)(rnd() % 2); break;
  case 5: S[31] = rnd() % 2 ? 7 : (S[31] | 8U); break;
  case 6: { static const uint32_t pct[4] = {100, 125, 150, 200}; uint32_t p = pick(pct, 4); S[3] = 1920U * 100U / p; S[4] = 1080U * 100U / p; } break;
  case 7: S[2033] = 0; break;
  default: S[432] = 1; break;
  }
}
/* main.c's keys: the uiux, clipboard, selection and damage stages', then the rest of the keyboard */
static const uint32_t stage_keys[] = {68U * 4U + 1U, 68U * 4U, 64U * 4U + 1U, 64U * 4U, 42U * 4U + 1U, 42U * 4U, 28U * 4U + 1U, 28U * 4U,
  1U * 4U + 1U, 1U * 4U, 87U * 4U + 1U, 87U * 4U, 56U * 4U + 1U, 12U * 4U + 1U, 12U * 4U, 56U * 4U, 117, 225, 153, 152, 224, 116,
  181, 180, 21, 20, 13, 12, 17, 16, 113, 112, 65, 64, 169, 421, 420, 168, 185, 184, 425, 424, 57, 56, 61, 60, 14U * 4U + 1U, 6, 10};
static const uint32_t letter_codes[] = {16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 30, 31, 32, 33, 34, 35, 36, 37, 38, 44, 45, 46, 47, 48, 49, 50};
static const uint32_t other_codes[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 26, 27, 28, 29, 39, 40, 41, 42, 43, 51, 52, 53, 54, 56,
  57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 87, 88, 97, 100, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 125};
/* readings typed as romaji, then Space (convert, cycle), then Enter, Escape, Backspace or more */
static const char *const words[] = {"yama", "kawa", "nihon", "nihongo", "kanji", "watashi", "ki", "hi", "ka", "sakura", "toukyou",
  "kyou", "gakkou", "sensei", "hon", "ame", "umi", "sora", "hito", "inu", "neko", "kotoba", "jisho", "denwa", "kuruma", "michi",
  "shinbun", "tegami", "ongaku", "eki", "mizu", "yamada", "kan", "nn", "kitte", "matcha"};
static uint32_t letter_code(char c) {
  static const char *row = "qwertyuiopasdfghjklzxcvbnm";
  static const uint32_t code[26] = {16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 30, 31, 32, 33, 34, 35, 36, 37, 38, 44, 45, 46, 47, 48, 49, 50};
  for (int i = 0; i < 26; i++) if (row[i] == c) return code[i];
  return 57;
}
static void queue_word(void) {
  const char *w = words[rnd() % (sizeof(words) / sizeof(words[0]))];
  q_n = q_at = 0;
  if (rnd() % 4 == 0 && S[432] == 0) { queue[q_n++] = 41U * 4U + 1U; queue[q_n++] = 41U * 4U; } /* Hankaku/Zenkaku: on */
  for (; *w && q_n < 40; w++) { queue[q_n++] = letter_code(*w) * 4U + 1U; queue[q_n++] = letter_code(*w) * 4U; }
  unsigned sp = (unsigned)(rnd() % 4);
  for (unsigned i = 0; i < sp; i++) { queue[q_n++] = 57U * 4U + 1U; queue[q_n++] = 57U * 4U; }
  static const uint32_t ends[6] = {28, 1, 14, 57, 105, 0};
  uint32_t e = ends[rnd() % 6];
  if (e) { queue[q_n++] = e * 4U + 1U; queue[q_n++] = e * 4U; }
}
static uint32_t gen_key(void) {
  if (q_at < q_n) return queue[q_at++];
  if (rnd() % 6 == 0) { queue_word(); return queue[q_at++]; }
  unsigned c = (unsigned)(rnd() % 16);
  if (c < 4) return pick(stage_keys, sizeof(stage_keys) / 4);
  if (c < 10) { uint32_t k = pick(letter_codes, sizeof(letter_codes) / 4); return k * 4U + (rnd() % 4 ? 1U : 0U); }
  if (c < 15) { uint32_t k = pick(other_codes, sizeof(other_codes) / 4); return k * 4U + (uint32_t)(rnd() % 3); }
  return (uint32_t)(rnd() % 1024);
}
static void gen_point(uint32_t *px, uint32_t *py) {
  uint32_t vw = S[3], vh = S[4], n = S[1] > 4 ? 4 : S[1];
  unsigned c = (unsigned)(rnd() % 12);
  uint32_t k = n ? (uint32_t)(rnd() % n) : 0, x = S[6 + 5 * k], y = S[7 + 5 * k];
  uint64_t w = S[8 + 5 * k], h = S[9 + 5 * k];
  switch (c) {
  case 0: *px = 6 + 102 * (uint32_t)(rnd() % 4) + (uint32_t)(rnd() % 100); *py = (uint32_t)(rnd() % 30); break; /* launcher */
  case 1: *px = (vw - 184) / 2 + 8 + 44 * (uint32_t)(rnd() % 4) + (uint32_t)(rnd() % 40); *py = vh - 52 + (uint32_t)(rnd() % 52); break; /* dock */
  case 2: *px = 6 + 126 * (uint32_t)(rnd() % 4) + (uint32_t)(rnd() % 124); *py = vh - 30 + (uint32_t)(rnd() % 26); break; /* tray */
  case 3: *px = x + (uint32_t)(rnd() % (w + 1)); *py = y + (uint32_t)(rnd() % 30); break; /* titlebar */
  case 4: { static const uint32_t off[3] = {24, 44, 64}; *px = x + (uint32_t)w - pick(off, 3) + (uint32_t)(rnd() % 18); *py = y + 5 + (uint32_t)(rnd() % 18); } break; /* controls */
  case 5: *px = x + (uint32_t)w - (uint32_t)(rnd() % 18); *py = y + (uint32_t)h - (uint32_t)(rnd() % 18); break; /* resize handle */
  case 6: case 7: *px = x + (uint32_t)(rnd() % (w + 1)); *py = y + (uint32_t)(rnd() % (h + 1)); break; /* body */
  case 8: *px = vw - 216 + (uint32_t)(rnd() % 216); *py = (uint32_t)(rnd() % 160); break; /* notifications, clock */
  case 9: *px = (uint32_t)(rnd() % ((uint64_t)vw + 1)); *py = (uint32_t)(rnd() % ((uint64_t)vh + 1)); break;
  case 10: { static const uint32_t at[8][2] = {{380, 142}, {380, 40}, {476, 146}, {500, 320}, {54, 14}, {456, 146}, {574, 772}, {60, 780}};
             unsigned i = (unsigned)(rnd() % 8); *px = at[i][0]; *py = at[i][1]; } break; /* the uiux stage's points */
  default: *px = (uint32_t)(rnd() % 4096); *py = (uint32_t)(rnd() % 4096); break;
  }
}
/* one event of main.c's desktop loop */
static void step(void) {
  static const uint32_t srcs[16] = {1, 4, 1, 4, 3, 3, 6, 7, 1, 4, 3, 6, 7, 8, 9, 10};
  unsigned c = q_at < q_n ? 19 : (unsigned)(rnd() % 20);
  n_steps++;
  if (c < 2) c_write();
  else if (c < 10) {
    uint32_t px, py, src = rnd() % 32 ? pick(srcs, 16) : (uint32_t)(rnd() % 12);
    gen_point(&px, &py);
    S[2046] = px + 1U; S[2047] = py; S[2029] = ++seq;
    S[2033] = src == 1 ? 1U : (src == 4 ? 0U : S[2033]);
    (void)REDUCE(P_S, rnd() % 16 ? 8192 : 128, src, px, py);
  } else {
    uint32_t key = gen_key();
    int64_t kr = KEY(P_S, 8192, DICT, DICTN, key);
    if (dead) return;
    if (kr >= 100000000LL) (void)KEY(P_S, 8192, DICT, DICTN, rnd() % 2 ? 6U : 10U);
    else if (kr == 512 || kr == 513) {
      if (rnd() % 8) (void)KEY(P_S, 8192, P_CP, 260, (key & ~3U) | 3U);
    } else if (kr >= 65536) { uint32_t at = (uint32_t)(kr - 65536); (void)REDUCE(P_S, 8192, 1, at >> 11, at & 2047U); }
    else if (kr > 256) (void)REDUCE(P_S, 8192, 5, (uint64_t)(kr - 256), 0);
  }
  if (dead) return;
  (void)FRAME(P_S, 8192, FONT, FONTN);
}
/* the export's length checks and other edge inputs, on the current state */
static void edge(void) {
  static const int64_t sbs[9] = {8192, 8192, 8192, 0, 127, 128, 129, 8191, 8193};
  int64_t sb = rnd() % 32 ? sbs[rnd() % 9] : (int64_t)1 << 40;
  int64_t s = rnd() % 24 ? P_S : 0;
  n_edge++;
#if TESTED == 1
  int64_t d, db; unsigned v = (unsigned)(rnd() % 12);
  if (v < 6) { d = DICT; db = DICTN; } else if (v == 6) { d = 0; db = DICTN; } else if (v == 7) { d = DICT; db = (int64_t)(rnd() % 32); }
  else if (v == 8) { d = DICT; db = DICTN - 1 - (int64_t)(rnd() % 64); } else if (v == 9) { d = DICT; db = DICTN + (int64_t)(rnd() % 64); }
  else if (v == 10) { d = P_CP; db = rnd() % 2 ? 260 : (int64_t)(259 + rnd() % 3); } else { d = DICT; db = 260; }
  uint64_t ev = rnd() % 4 ? gen_key() : (uint64_t)rnd();
  if (d == P_CP || rnd() % 6 == 0) ev = (ev & ~3ull) | 3ull;
  if (d == P_CP) for (int i = 0; i < 65; i++) CP[i] = i == 0 ? (uint32_t)(rnd() % 70) : (rnd() % 4 ? 0x3041 + (uint32_t)(rnd() % 80) : (uint32_t)rnd());
  (void)tested(s, sb, d, db, (int64_t)ev);
#elif TESTED == 2
  uint32_t px, py; gen_point(&px, &py);
  int64_t kind = rnd() % 8 ? (int64_t)(rnd() % 12) : (int64_t)rnd();
  int64_t a = rnd() % 8 ? (int64_t)px : (int64_t)rnd(), b = rnd() % 8 ? (int64_t)py : (int64_t)rnd();
  if (kind == 5 && rnd() % 2) a = (int64_t)(rnd() % 6);
  (void)tested(s, rnd() % 4 ? sb : 128, kind, a, b);
#else
  int64_t f = rnd() % 24 ? FONT : 0, fb; unsigned v = (unsigned)(rnd() % 10);
  if (v < 6) fb = FONTN; else if (v == 6) fb = (int64_t)(rnd() % 40); else if (v == 7) fb = FONTN - 1 - (int64_t)(rnd() % 4096);
  else if (v == 8) fb = FONTN + (int64_t)(rnd() % 64); else fb = 16 + 36 * (int64_t)(rnd() % 8000);
  (void)tested(s, sb, f, fb, 0);
#endif
}
static void scramble(unsigned how) {
  /* random words: anywhere, or in the words the objects read (records, ids, scratch, slots, notifications) */
  static const uint32_t hot[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 26, 27, 28, 29, 30, 31, 416, 417, 418, 419, 420, 421, 423, 424,
    425, 426, 427, 428, 429, 430, 432, 433, 434, 445, 446, 478, 479, 1968, 1969, 1970, 1971, 1979, 1987, 1995, 2003, 2004, 2005, 2006,
    2007, 2008, 2009, 2010, 2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035, 2036, 2037, 2038, 2039, 2040, 2041, 2042, 2043,
    2044, 2045, 2046, 2047};
  if (how == 0) { for (int i = 0; i < 2048; i++) S[i] = (uint32_t)rnd(); return; }
  unsigned k = 1 + (unsigned)(rnd() % 8);
  for (unsigned j = 0; j < k; j++) {
    uint32_t i = rnd() % 2 ? pick(hot, sizeof(hot) / 4) : (uint32_t)(rnd() % 2048);
    unsigned m = (unsigned)(rnd() % 4);
    S[i] = m == 0 ? (uint32_t)rnd() : m == 1 ? (uint32_t)(rnd() % 8) : m == 2 ? (uint32_t)(rnd() % 300) : S[i] + 1;
  }
}
void test_main(void) {
  guard_init(); puts_("IMEDIFF\n");
  FONT = (int64_t)(uintptr_t)font_blob; FONTN = (int64_t)(font_blob_end - font_blob);
  DICT = (int64_t)(uintptr_t)dict_blob; DICTN = (int64_t)(dict_blob_end - dict_blob);
  uint64_t hf = fnv(font_blob, (uint64_t)FONTN), hd = fnv(dict_blob, (uint64_t)DICTN);
  for (unsigned t = 0; t < 800; t++) {
    init_state(); n_traj++;
    unsigned len = 8 + (unsigned)(rnd() % 300);
    for (unsigned i = 0; i < len && !dead; i++) step();
    for (unsigned i = 0; i < 40 && !dead; i++) { if (rnd() % 3 == 0) scramble(1 + (unsigned)(rnd() % 3)); edge(); }
    if (t % 8 == 7) { init_state(); scramble(0); for (unsigned i = 0; i < 4; i++) { dead = 0; edge(); } }
  }
  if (fnv(font_blob, (uint64_t)FONTN) != hf || fnv(dict_blob, (uint64_t)DICTN) != hd) { puts_("DIFF font-or-dictionary-written\n"); n_bad++; }
  puts_("TRAJ "); hex(n_traj, 8); puts_("STEPS "); hex(n_steps, 8); puts_("CALLS "); hex(n_calls, 8); puts_("EDGE "); hex(n_edge, 8); putc_('\n');
  report();
}

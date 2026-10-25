(ns av1.tables
  "AV1 constant tables needed for coefficient decoding / dequantization /
   inverse transform / DC intra prediction, transcribed field-for-field from
   the spec (AOMediaCodec/av1-spec master, 06.bitstream.syntax.md /
   07.bitstream.semantics.md / 08.decoding.process.md / 09.parsing.process.md /
   10.additional.tables.md, fetched 2026-07-13) -- same sourcing discipline as
   every other av1.* namespace in this repo (no numbers reconstructed from
   memory; every table below was mechanically extracted from the spec's own
   markdown source with a small brace-matching parser, then spot-checked by
   element count against the spec's own declared array dimensions, to rule out
   manual transcription error for the large tables).

   SCOPE (Phase 1 continuation, ADR-2607122000 Migration step 9 -- see
   av1.decode-block namespace docstring for the full scope statement): this
   phase's pixel-reconstruction milestone deliberately supports exactly ONE
   transform size (TX_32X32) and DCT_DCT only, so only the CDF-table slices
   needed for that one size / that one plane type (luma, ptype=0 -- this repo
   is monochrome/luma-only in this phase, see av1.decode-block) are included
   here, not the full spec tables across all TX_SIZES x PLANE_TYPES. Each
   *_Cdf table below is indexed [q-ctx-idx 0..3][...] per
   09.parsing.process.md's `init_coeff_cdfs()` COEFF_CDF_Q_CTXS selection
   (base_q_idx <=20 -> 0, <=60 -> 1, <=120 -> 2, else -> 3); q-ctx-idx is
   picked at runtime from the frame's actual base_q_idx (av1.decode-block/q-ctx-idx),
   not hardcoded, so any base_q_idx works even though only TX_32X32 is
   supported as a transform size.")

;; ---------------------------------------------------------------------
;; TX_SIZES_ALL enum (10.additional.tables.md, Tx_Size_Sqr/Tx_Width tables'
;; implicit index order) -- kept for the handful of generic size-derived
;; formulas below (txSzCtx, get_tx_class, dqDenom) even though only
;; TX_32X32 has table data past this point.
(def TX_4X4 0) (def TX_8X8 1) (def TX_16X16 2) (def TX_32X32 3) (def TX_64X64 4)
(def TX_4X8 5) (def TX_8X4 6) (def TX_8X16 7) (def TX_16X8 8) (def TX_16X32 9)
(def TX_32X16 10) (def TX_32X64 11) (def TX_64X32 12) (def TX_4X16 13) (def TX_16X4 14)
(def TX_8X32 15) (def TX_32X8 16) (def TX_16X64 17) (def TX_64X16 18)

;; 10.additional.tables.md: Tx_Size_Sqr[t] = square tx size w/ side Min(w,h).
(def Tx-Size-Sqr
  [TX_4X4 TX_8X8 TX_16X16 TX_32X32 TX_64X64 TX_4X4 TX_4X4 TX_8X8 TX_8X8
   TX_16X16 TX_16X16 TX_32X32 TX_32X32 TX_4X4 TX_4X4 TX_8X8 TX_8X8 TX_16X16 TX_16X16])

;; Tx_Size_Sqr_Up[t] = square tx size w/ side Max(w,h).
(def Tx-Size-Sqr-Up
  [TX_4X4 TX_8X8 TX_16X16 TX_32X32 TX_64X64 TX_8X8 TX_8X8 TX_16X16 TX_16X16
   TX_32X32 TX_32X32 TX_64X64 TX_64X64 TX_16X16 TX_16X16 TX_32X32 TX_32X32 TX_64X64 TX_64X64])

(def Tx-Width  [4 8 16 32 64 4 8 8 16 16 32 32 64 4 16 8 32 16 64])
(def Tx-Height [4 8 16 32 64 8 4 16 8 32 16 64 32 16 4 32 8 64 16])
(def Tx-Width-Log2  [2 3 4 5 6 2 3 3 4 4 5 5 6 2 4 3 5 4 6])
(def Tx-Height-Log2 [2 3 4 5 6 3 2 4 3 5 4 6 5 4 2 5 3 6 4])

;; Adjusted_Tx_Size[t] -- identity for every square size up to TX_32X32
;; (only entries this phase's get_coeff_base_ctx/coeff_br context derivation
;; can reach, since we only support TX_32X32).
(def Adjusted-Tx-Size-32x32 TX_32X32)

;; Transform_Row_Shift[TX_32X32] (08.decoding.process.md #2D inverse transform
;; process). Full per-size table not needed since only TX_32X32 is supported.
(def Transform-Row-Shift-32x32 2)

;; Max_Tx_Size_Rect[BLOCK_SIZES] (06.bitstream.syntax.md #TX size syntax) --
;; full table (all 22 luma block sizes), expressed via the TX_* constants
;; above; av1.decode-block throws unless the result is TX_32X32 (this
;; phase's only supported size), but the table itself is transcribed in
;; full since it's cheap and content-independent.
(def Max-Tx-Size-Rect
  [TX_4X4 TX_4X8 TX_8X4 TX_8X8 TX_8X16 TX_16X8 TX_16X16 TX_16X32 TX_32X16 TX_32X32
   TX_32X64 TX_64X32 TX_64X64 TX_64X64 TX_64X64 TX_64X64 TX_4X16 TX_16X4 TX_8X32
   TX_32X8 TX_16X64 TX_64X16])

;; 09.parsing.process.md "intra_frame_y_mode": Intra_Mode_Context[INTRA_MODES],
;; transcribed in full (all 13 entries, not just the DC/V/H-reachable
;; prefix -- see av1.decode-block/read-y-mode's ctx-of, which looks up a
;; neighbor's ALREADY-DECODED YMode here). Intra_Mode_Context[DC_PRED(=0)]
;; == Intra_Mode_Context[SMOOTH_PRED(=9)] == Intra_Mode_Context[PAETH_PRED(=12)]
;; == 0, which is why every intra_frame_y_mode ctx in this repo's
;; {DC_PRED,V_PRED,H_PRED,SMOOTH_PRED,PAETH_PRED} scope is always (0,0) as
;; long as no neighbor ever decoded to V_PRED/H_PRED (ctx 1/2) -- see
;; av1.decode-block namespace docstring's PAETH/SMOOTH sections for why
;; neither mode introduces any new reachable ctx pair.
(def Intra-Mode-Context [0 1 2 3 4 4 4 4 3 0 1 2 0])

;; 08.decoding.process.md #Smooth intra prediction process /
;; 10.additional.tables.md: Sm_Weights_Tx_4x4/8x8/16x16/32x32/64x64 --
;; smWeightsX/smWeightsY are selected by log2W/log2H (2/3/4/5/6 ->
;; 4x4/8x8/16x16/32x32/64x64) per the spec's dispatch table (see
;; av1.intra-pred/smooth-predict). All five sizes are transcribed in full
;; (even though this phase's only supported luma block size is
;; 32x32/log2W=log2H=5) the same way Max-Tx-Size-Rect above is
;; transcribed in full despite only TX_32X32 being reachable --
;; smooth-predict is written generically over log2W/log2H the same way
;; dc-predict/v-predict/h-predict/paeth-predict are, so the unreachable
;; sizes cost nothing extra to include. Independently cross-checked
;; against a SECOND source (aomedia.googlesource.com/aom main branch,
;; aom_dsp/intrapred_common.h's smooth_weights[]/smooth_weights_u16[]
;; arrays) -- byte-for-byte identical to the spec's own transcription
;; below (both fetched 2026-07-13); every array's element count was also
;; checked against its own declared dimension (4/8/16/32/64) and its
;; monotonic-non-increasing-from-255 shape (weights decay from ~1x down
;; to ~1/block_size, per the spec's own "quadratic from '1' to '1 /
;; block_size'" comment in intrapred_common.h) before being accepted, the
;; same discipline used for every large table in this namespace.
(def Sm-Weights-Tx-4x4 [255 149 85 64])
(def Sm-Weights-Tx-8x8 [255 197 146 105 73 50 37 32])
(def Sm-Weights-Tx-16x16
  [255 225 196 170 145 123 102 84 68 54 43 33 26 20 17 16])
(def Sm-Weights-Tx-32x32
  [255 240 225 210 196 182 169 157 145 133 122 111 101 92 83 74
   66 59 52 45 39 34 29 25 21 17 14 12 10 9 8 8])
(def Sm-Weights-Tx-64x64
  [255 248 240 233 225 218 210 203 196 189 182 176 169 163 156 150
   144 138 133 127 121 116 111 106 101 96 91 86 82 77 73 69
   65 61 57 54 50 47 44 41 38 35 32 29 27 25 22 20 18 16 15
   13 12 10 9 8 7 6 6 5 5 4 4 4])

;; 08.decoding.process.md #Butterfly functions: Cos128_Lookup[65].
(def Cos128-Lookup
  [4096 4095 4091 4085 4076 4065 4052 4036 4017 3996 3973 3948 3920 3889 3857 3822 3784 3745 3703 3659 3612 3564 3513 3461 3406 3349 3290 3229 3166 3102 3035 2967 2896 2824 2751 2675 2598 2520 2440 2359 2276 2191 2106 2019 1931 1842 1751 1660 1567 1474 1380 1285 1189 1092 995 897 799 700 601 501 401 301 201 101 0])

;; 08.decoding.process.md #Dequantization functions: Dc_Qlookup[0]
;; (8-bit row only -- this repo is 8-bit-only, no high-bitdepth support).
(def Dc-Qlookup-8bit
  [4 8 8 9 10 11 12 12 13 14 15 16 17 18 19 19 20 21 22 23 24 25 26 26 27 28 29 30 31 32 32 33 34 35 36 37 38 38 39 40 41 42 43 43 44 45 46 47 48 48 49 50 51 52 53 53 54 55 56 57 57 58 59 60 61 62 62 63 64 65 66 66 67 68 69 70 70 71 72 73 74 74 75 76 77 78 78 79 80 81 81 82 83 84 85 85 87 88 90 92 93 95 96 98 99 101 102 104 105 107 108 110 111 113 114 116 117 118 120 121 123 125 127 129 131 134 136 138 140 142 144 146 148 150 152 154 156 158 161 164 166 169 172 174 177 180 182 185 187 190 192 195 199 202 205 208 211 214 217 220 223 226 230 233 237 240 243 247 250 253 257 261 265 269 272 276 280 284 288 292 296 300 304 309 313 317 322 326 330 335 340 344 349 354 359 364 369 374 379 384 389 395 400 406 411 417 423 429 435 441 447 454 461 467 475 482 489 497 505 513 522 530 539 549 559 569 579 590 602 614 626 640 654 668 684 700 717 736 755 775 796 819 843 869 896 925 955 988 1022 1058 1098 1139 1184 1232 1282 1336])

;; Ac_Qlookup[0] (8-bit row).
(def Ac-Qlookup-8bit
  [4 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 101 102 104 106 108 110 112 114 116 118 120 122 124 126 128 130 132 134 136 138 140 142 144 146 148 150 152 155 158 161 164 167 170 173 176 179 182 185 188 191 194 197 200 203 207 211 215 219 223 227 231 235 239 243 247 251 255 260 265 270 275 280 285 290 295 300 305 311 317 323 329 335 341 347 353 359 366 373 380 387 394 401 408 416 424 432 440 448 456 465 474 483 492 501 510 520 530 540 550 560 571 582 593 604 615 627 639 651 663 676 689 702 715 729 743 757 771 786 801 816 832 848 864 881 898 915 933 951 969 988 1007 1026 1046 1066 1087 1108 1129 1151 1173 1196 1219 1243 1267 1292 1317 1343 1369 1396 1423 1451 1479 1508 1537 1567 1597 1628 1660 1692 1725 1759 1793 1828])

;; 10.additional.tables.md Default_Scan_32x32[1024] -- get_scan()
;; always resolves to this table for our scope (PlaneTxType is always
;; DCT_DCT, so preferRow/preferCol in get_scan() are never true, and
;; Tx_Size_Sqr_Up[TX_32X32] == TX_32X32 falls through to
;; get_default_scan(TX_32X32) == Default_Scan_32x32).
(def Default-Scan-32x32
  [0 1 32 64 33 2 3 34 65 96 128 97 66 35 4 5 36 67 98 129 160 192 161 130 99 68 37 6 7 38 69 100 131 162 193 224 256 225 194 163 132 101 70 39 8 9 40 71 102 133 164 195 226 257 288 320 289 258 227 196 165 134 103 72 41 10 11 42 73 104 135 166 197 228 259 290 321 352 384 353 322 291 260 229 198 167 136 105 74 43 12 13 44 75 106 137 168 199 230 261 292 323 354 385 416 448 417 386 355 324 293 262 231 200 169 138 107 76 45 14 15 46 77 108 139 170 201 232 263 294 325 356 387 418 449 480 512 481 450 419 388 357 326 295 264 233 202 171 140 109 78 47 16 17 48 79 110 141 172 203 234 265 296 327 358 389 420 451 482 513 544 576 545 514 483 452 421 390 359 328 297 266 235 204 173 142 111 80 49 18 19 50 81 112 143 174 205 236 267 298 329 360 391 422 453 484 515 546 577 608 640 609 578 547 516 485 454 423 392 361 330 299 268 237 206 175 144 113 82 51 20 21 52 83 114 145 176 207 238 269 300 331 362 393 424 455 486 517 548 579 610 641 672 704 673 642 611 580 549 518 487 456 425 394 363 332 301 270 239 208 177 146 115 84 53 22 23 54 85 116 147 178 209 240 271 302 333 364 395 426 457 488 519 550 581 612 643 674 705 736 768 737 706 675 644 613 582 551 520 489 458 427 396 365 334 303 272 241 210 179 148 117 86 55 24 25 56 87 118 149 180 211 242 273 304 335 366 397 428 459 490 521 552 583 614 645 676 707 738 769 800 832 801 770 739 708 677 646 615 584 553 522 491 460 429 398 367 336 305 274 243 212 181 150 119 88 57 26 27 58 89 120 151 182 213 244 275 306 337 368 399 430 461 492 523 554 585 616 647 678 709 740 771 802 833 864 896 865 834 803 772 741 710 679 648 617 586 555 524 493 462 431 400 369 338 307 276 245 214 183 152 121 90 59 28 29 60 91 122 153 184 215 246 277 308 339 370 401 432 463 494 525 556 587 618 649 680 711 742 773 804 835 866 897 928 960 929 898 867 836 805 774 743 712 681 650 619 588 557 526 495 464 433 402 371 340 309 278 247 216 185 154 123 92 61 30 31 62 93 124 155 186 217 248 279 310 341 372 403 434 465 496 527 558 589 620 651 682 713 744 775 806 837 868 899 930 961 992 993 962 931 900 869 838 807 776 745 714 683 652 621 590 559 528 497 466 435 404 373 342 311 280 249 218 187 156 125 94 63 95 126 157 188 219 250 281 312 343 374 405 436 467 498 529 560 591 622 653 684 715 746 777 808 839 870 901 932 963 994 995 964 933 902 871 840 809 778 747 716 685 654 623 592 561 530 499 468 437 406 375 344 313 282 251 220 189 158 127 159 190 221 252 283 314 345 376 407 438 469 500 531 562 593 624 655 686 717 748 779 810 841 872 903 934 965 996 997 966 935 904 873 842 811 780 749 718 687 656 625 594 563 532 501 470 439 408 377 346 315 284 253 222 191 223 254 285 316 347 378 409 440 471 502 533 564 595 626 657 688 719 750 781 812 843 874 905 936 967 998 999 968 937 906 875 844 813 782 751 720 689 658 627 596 565 534 503 472 441 410 379 348 317 286 255 287 318 349 380 411 442 473 504 535 566 597 628 659 690 721 752 783 814 845 876 907 938 969 1000 1001 970 939 908 877 846 815 784 753 722 691 660 629 598 567 536 505 474 443 412 381 350 319 351 382 413 444 475 506 537 568 599 630 661 692 723 754 785 816 847 878 909 940 971 1002 1003 972 941 910 879 848 817 786 755 724 693 662 631 600 569 538 507 476 445 414 383 415 446 477 508 539 570 601 632 663 694 725 756 787 818 849 880 911 942 973 1004 1005 974 943 912 881 850 819 788 757 726 695 664 633 602 571 540 509 478 447 479 510 541 572 603 634 665 696 727 758 789 820 851 882 913 944 975 1006 1007 976 945 914 883 852 821 790 759 728 697 666 635 604 573 542 511 543 574 605 636 667 698 729 760 791 822 853 884 915 946 977 1008 1009 978 947 916 885 854 823 792 761 730 699 668 637 606 575 607 638 669 700 731 762 793 824 855 886 917 948 979 1010 1011 980 949 918 887 856 825 794 763 732 701 670 639 671 702 733 764 795 826 857 888 919 950 981 1012 1013 982 951 920 889 858 827 796 765 734 703 735 766 797 828 859 890 921 952 983 1014 1015 984 953 922 891 860 829 798 767 799 830 861 892 923 954 985 1016 1017 986 955 924 893 862 831 863 894 925 956 987 1018 1019 988 957 926 895 927 958 989 1020 1021 990 959 991 1022 1023])

;; ---------------------------------------------------------------------
;; Small coefficients-syntax constants (03.symbols.md).
(def NUM_BASE_LEVELS 2)
(def COEFF_BASE_RANGE 12)
(def BR_CDF_SIZE 4)
(def SIG_COEF_CONTEXTS_EOB 4)
(def SIG_COEF_CONTEXTS_2D 26)
(def SIG_COEF_CONTEXTS 42)
(def SIG_REF_DIFF_OFFSET_NUM 5)

;; TX_CLASS_2D only -- this repo's DCT_DCT-only scope never reaches
;; TX_CLASS_HORIZ/TX_CLASS_VERT (those classes only arise for
;; H_DCT/H_ADST/H_FLIPADST / V_DCT/V_ADST/V_FLIPADST transform types,
;; av1.decode-block throws before this point for any non-DCT_DCT TxType).
(def TX_CLASS_2D 0)

;; 09.parsing.process.md get_coeff_base_ctx's Sig_Ref_Diff_Offset[TX_CLASS_2D]
;; row only (10.additional.tables.md).
(def Sig-Ref-Diff-Offset-2D [[0 1] [1 0] [1 1] [0 2] [2 0]])

;; coeff_br's Mag_Ref_Offset_With_Tx_Class[TX_CLASS_2D] row only.
(def Mag-Ref-Offset-With-Tx-Class-2D [[0 1] [1 0] [1 1]])

;; Coeff_Base_Ctx_Offset[TX_32X32][5][5] row only (10.additional.tables.md;
;; this repo only supports TX_32X32, see av1.tables namespace docstring).
(def Coeff-Base-Ctx-Offset-32x32
  [[0 1 6 6 21]
   [1 6 6 21 21]
   [6 6 21 21 21]
   [6 21 21 21 21]
   [21 21 21 21 21]])

;; ---------------------------------------------------------------------
;; Default CDF tables (10.additional.tables.md), sliced to this phase's
;; scope: TX_32X32 only (txSzCtx index 3 of the TX_SIZES dimension where
;; applicable) and luma only (ptype 0 of the PLANE_TYPES dimension, since
;; this repo is monochrome-only in this phase). All 4 COEFF_CDF_Q_CTXS
;; buckets (base_q_idx <=20/<=60/<=120/>120) are included since q-ctx-idx
;; is picked at runtime from the frame's actual base_q_idx, not hardcoded.

;; Default_Skip_Cdf[SKIP_CONTEXTS=3][3] -- full table (small, not
;; q-idx-dependent, so no idx dimension here).
(def Default-Skip-Cdf
  [
    [31671 32768 0]
    [16515 32768 0]
    [4576 32768 0]
  ])

;; Default_Intra_Frame_Y_Mode_Cdf[abovemode=0][leftmode=0] row only
;; (14 entries: 13-symbol cdf + adaptation counter) -- av1.decode-block
;; properly computes the real (abovemode,leftmode) ctx from each leaf's
;; actual neighbor YModes (via Intra-Mode-Context above -- see its docstring)
;; and throws if it's ever anything other than (0,0), since this is the only
;; TileIntraFrameYModeCdf[abovemode][leftmode] entry transcribed (out of
;; the full 5x5 abovemode/leftmode space -- see av1.decode-block namespace
;; docstring). The row's 13 cdf symbols cover every INTRA_MODES value
;; (0..12, including SMOOTH_PRED=9 and PAETH_PRED=12), not just DC/V/H --
;; only the *row selection* (which (abovemode,leftmode) ctx pair) was ever
;; restricted, not this row's own symbol coverage; neither the PAETH-
;; coverage extension nor the SMOOTH-coverage extension (see
;; av1.decode-block namespace docstring's PAETH/SMOOTH sections) needed
;; any change to this cdf row itself -- both only needed to widen
;; ctx-of's neighbor-mode lookup (Intra-Mode-Context, above -- already
;; transcribed in full and already maps both SMOOTH_PRED(9)->0 and
;; PAETH_PRED(12)->0, same as DC_PRED(0)->0) to allow that mode as a
;; decodable/re-consultable neighbor mode.
(def Default-Intra-Frame-Y-Mode-Cdf-0-0
  [15588 17027 19338 20218 20682 21110 21825 23244 24189 28165 29093 30466 32768 0])

;; MAX_ANGLE_DELTA / ANGLE_STEP (03.symbols.md) -- angle_delta_y's decoded
;; symbol (0..2*MAX_ANGLE_DELTA) maps to AngleDeltaY = symbol - MAX_ANGLE_DELTA.
(def MAX_ANGLE_DELTA 3)

;; Default_Angle_Delta_Cdf[DIRECTIONAL_MODES][(2*MAX_ANGLE_DELTA+1)+1]
;; (10.additional.tables.md), row-sliced to only the two entries
;; av1.decode-block/read-angle-delta-y can ever consult: index 0
;; (YMode-V_PRED for YMode==V_PRED) and index 1 (YMode-V_PRED for
;; YMode==H_PRED) -- the full table has DIRECTIONAL_MODES==8 rows (also
;; covering D45/D135/D113/D157/D203/D67), but av1.decode-block/read-y-mode
;; already throws before any of those modes could reach this table.
(def Default-Angle-Delta-Cdf
  [[2180 5032 7567 22776 26989 30217 32768 0]
   [2301 5608 8801 23487 26974 30330 32768 0]])

;; Default_Txb_Skip_Cdf[q-ctx-idx][TX_32X32][ctx][3], ctx = TXB_SKIP_CONTEXTS (13).
(def Default-Txb-Skip-Cdf-32x32
  [
    [
      [17920 32768 0]
      [1818 32768 0]
      [7282 32768 0]
      [25273 32768 0]
      [10923 32768 0]
      [31554 32768 0]
      [32624 32768 0]
      [1366 32768 0]
      [15628 32768 0]
      [30462 32768 0]
      [146 32768 0]
      [5132 32768 0]
      [31657 32768 0]
    ]
    [
      [26726 32768 0]
      [1045 32768 0]
      [11703 32768 0]
      [20590 32768 0]
      [18554 32768 0]
      [25970 32768 0]
      [31938 32768 0]
      [5583 32768 0]
      [21313 32768 0]
      [29390 32768 0]
      [641 32768 0]
      [22265 32768 0]
      [31452 32768 0]
    ]
    [
      [30669 32768 0]
      [3832 32768 0]
      [11663 32768 0]
      [18889 32768 0]
      [19782 32768 0]
      [23313 32768 0]
      [31330 32768 0]
      [5124 32768 0]
      [18719 32768 0]
      [28468 32768 0]
      [3082 32768 0]
      [20982 32768 0]
      [29443 32768 0]
    ]
    [
      [31671 32768 0]
      [2056 32768 0]
      [11746 32768 0]
      [16852 32768 0]
      [18635 32768 0]
      [24715 32768 0]
      [31484 32768 0]
      [4656 32768 0]
      [16074 32768 0]
      [24704 32768 0]
      [1806 32768 0]
      [14645 32768 0]
      [25336 32768 0]
    ]
  ])

;; Default_Eob_Pt_1024_Cdf[q-ctx-idx][ptype=luma][12] -- eobMultisize==6
;; (TX_32X32, since Min(5,5)+Min(5,5)-4==6) always selects this table.
(def Default-Eob-Pt-1024-Cdf-Luma
  [
    [393 421 751 1623 3160 6352 13345 18047 22571 25830 32768 0]
    [696 948 3145 5702 9706 13217 17851 21856 25692 28034 32768 0]
    [2784 3831 7041 10521 14847 18844 23155 26682 29229 31045 32768 0]
    [6698 8334 11961 15762 20186 23862 27434 29326 31082 32050 32768 0]
  ])

;; Default_Eob_Extra_Cdf[q-ctx-idx][TX_32X32][ptype=luma][ctx][3], ctx = EOB_COEF_CONTEXTS (9).
(def Default-Eob-Extra-Cdf-32x32-Luma
  [
    [
      [27399 32768 0]
      [16327 32768 0]
      [18071 32768 0]
      [19584 32768 0]
      [20721 32768 0]
      [18432 32768 0]
      [19560 32768 0]
      [10150 32768 0]
      [8805 32768 0]
    ]
    [
      [25991 32768 0]
      [20314 32768 0]
      [17731 32768 0]
      [19678 32768 0]
      [18649 32768 0]
      [17307 32768 0]
      [21798 32768 0]
      [17549 32768 0]
      [15630 32768 0]
    ]
    [
      [23312 32768 0]
      [21607 32768 0]
      [16526 32768 0]
      [18957 32768 0]
      [18034 32768 0]
      [18934 32768 0]
      [24247 32768 0]
      [16921 32768 0]
      [17080 32768 0]
    ]
    [
      [21442 32768 0]
      [22358 32768 0]
      [18503 32768 0]
      [20291 32768 0]
      [19945 32768 0]
      [21294 32768 0]
      [21178 32768 0]
      [19400 32768 0]
      [10556 32768 0]
    ]
  ])

;; Default_Dc_Sign_Cdf[q-ctx-idx][ptype=luma][ctx][3], ctx = DC_SIGN_CONTEXTS (3).
(def Default-Dc-Sign-Cdf-Luma
  [
    [
      [16000 32768 0]
      [13056 32768 0]
      [18816 32768 0]
    ]
    [
      [16000 32768 0]
      [13056 32768 0]
      [18816 32768 0]
    ]
    [
      [16000 32768 0]
      [13056 32768 0]
      [18816 32768 0]
    ]
    [
      [16000 32768 0]
      [13056 32768 0]
      [18816 32768 0]
    ]
  ])

;; Default_Coeff_Base_Eob_Cdf[q-ctx-idx][TX_32X32][ptype=luma][ctx][4], ctx = SIG_COEF_CONTEXTS_EOB (4).
(def Default-Coeff-Base-Eob-Cdf-32x32-Luma
  [
    [
      [1787 2532 32768 0]
      [30832 31662 32768 0]
      [31824 32682 32768 0]
      [32133 32569 32768 0]
    ]
    [
      [1044 2257 32768 0]
      [30755 31923 32768 0]
      [32208 32693 32768 0]
      [32244 32615 32768 0]
    ]
    [
      [2809 19301 32768 0]
      [32205 32622 32768 0]
      [32338 32730 32768 0]
      [31786 32616 32768 0]
    ]
    [
      [24647 30463 32768 0]
      [32412 32695 32768 0]
      [32468 32720 32768 0]
      [31269 32523 32768 0]
    ]
  ])

;; Default_Coeff_Base_Cdf[q-ctx-idx][TX_32X32][ptype=luma][ctx][5], ctx = SIG_COEF_CONTEXTS (42).
(def Default-Coeff-Base-Cdf-32x32-Luma
  [
    [
      [5141 7096 8260 32768 0]
      [27186 29022 29789 32768 0]
      [6668 12568 15682 32768 0]
      [2172 6181 8638 32768 0]
      [1126 3379 4531 32768 0]
      [443 1361 2254 32768 0]
      [26083 31153 32436 32768 0]
      [13486 24603 28483 32768 0]
      [6508 14840 19910 32768 0]
      [3386 8800 13286 32768 0]
      [1530 4322 7054 32768 0]
      [29639 32080 32548 32768 0]
      [15897 27552 30290 32768 0]
      [8588 20047 25383 32768 0]
      [4889 13339 19269 32768 0]
      [2240 6871 10498 32768 0]
      [28165 32197 32517 32768 0]
      [20735 30427 31568 32768 0]
      [14325 24671 27692 32768 0]
      [5119 12554 17805 32768 0]
      [1810 5441 8261 32768 0]
      [31212 32724 32748 32768 0]
      [23352 31766 32545 32768 0]
      [14669 27570 31059 32768 0]
      [8492 20894 27272 32768 0]
      [3644 10194 15204 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [3078 6839 9890 32768 0]
      [13837 20450 24479 32768 0]
      [5914 14222 19328 32768 0]
      [3866 10267 14762 32768 0]
      [2612 7208 11042 32768 0]
      [1067 2991 4776 32768 0]
      [25817 31646 32529 32768 0]
      [13708 26338 30385 32768 0]
      [7328 18585 24870 32768 0]
      [4691 13080 19276 32768 0]
      [1825 5253 8352 32768 0]
      [29386 32315 32624 32768 0]
      [17160 29001 31360 32768 0]
      [9602 21862 27396 32768 0]
      [5915 15772 22148 32768 0]
      [2786 7779 12047 32768 0]
      [29246 32450 32663 32768 0]
      [18696 29929 31818 32768 0]
      [10510 23369 28560 32768 0]
      [6229 16499 23125 32768 0]
      [2608 7448 11705 32768 0]
      [30753 32710 32748 32768 0]
      [21638 31487 32503 32768 0]
      [12937 26854 30870 32768 0]
      [8182 20596 26970 32768 0]
      [3637 10269 15497 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [4456 11274 15533 32768 0]
      [21219 29079 31616 32768 0]
      [11173 23774 28567 32768 0]
      [7282 18293 24263 32768 0]
      [4890 13286 19115 32768 0]
      [1890 5508 8659 32768 0]
      [26651 32136 32647 32768 0]
      [14630 28254 31455 32768 0]
      [8716 21287 27395 32768 0]
      [5615 15331 22008 32768 0]
      [2675 7700 12150 32768 0]
      [29954 32526 32690 32768 0]
      [16126 28982 31633 32768 0]
      [9030 21361 27352 32768 0]
      [5411 14793 21271 32768 0]
      [2943 8422 13163 32768 0]
      [29539 32601 32730 32768 0]
      [18125 30385 32201 32768 0]
      [10422 24090 29468 32768 0]
      [6468 17487 24438 32768 0]
      [2970 8653 13531 32768 0]
      [30912 32715 32748 32768 0]
      [20666 31373 32497 32768 0]
      [12509 26640 30917 32768 0]
      [8058 20629 27290 32768 0]
      [4231 12006 18052 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [5992 14304 19765 32768 0]
      [22612 31238 32456 32768 0]
      [13456 27162 31087 32768 0]
      [8001 20062 26504 32768 0]
      [5168 14105 20764 32768 0]
      [2632 7771 12385 32768 0]
      [27034 32344 32709 32768 0]
      [15850 29415 31997 32768 0]
      [9494 22776 28841 32768 0]
      [6151 16830 23969 32768 0]
      [3461 10039 15722 32768 0]
      [30134 32569 32731 32768 0]
      [15638 29422 31945 32768 0]
      [9150 21865 28218 32768 0]
      [5647 15719 22676 32768 0]
      [3402 9772 15477 32768 0]
      [28530 32586 32735 32768 0]
      [17139 30298 32292 32768 0]
      [10200 24039 29685 32768 0]
      [6419 17674 24786 32768 0]
      [3544 10225 15824 32768 0]
      [31333 32726 32748 32768 0]
      [20618 31487 32544 32768 0]
      [12901 27217 31232 32768 0]
      [8624 21734 28171 32768 0]
      [5104 14191 20748 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
  ])

;; Default_Coeff_Br_Cdf[q-ctx-idx][Min(TX_32X32,TX_32X32)][ptype=luma][ctx][5], ctx = LEVEL_CONTEXTS (21).
(def Default-Coeff-Br-Cdf-32x32-Luma
  [
    [
      [2331 3662 5244 32768 0]
      [2891 4771 6145 32768 0]
      [4598 7623 9729 32768 0]
      [3520 6845 9199 32768 0]
      [3417 6119 9324 32768 0]
      [2601 5412 7385 32768 0]
      [600 1173 1744 32768 0]
      [7672 13286 17469 32768 0]
      [4232 7792 10793 32768 0]
      [2915 5317 7397 32768 0]
      [2318 4356 6152 32768 0]
      [2127 4000 5554 32768 0]
      [1850 3478 5275 32768 0]
      [977 1933 2843 32768 0]
      [18280 24387 27989 32768 0]
      [15852 22671 26185 32768 0]
      [13845 20951 24789 32768 0]
      [11055 17966 22129 32768 0]
      [9138 15422 19801 32768 0]
      [7454 13145 17456 32768 0]
      [3370 6393 9013 32768 0]
    ]
    [
      [5705 10930 15725 32768 0]
      [7946 12765 16115 32768 0]
      [6801 12123 16226 32768 0]
      [5462 10135 14200 32768 0]
      [4189 8011 11507 32768 0]
      [3191 6229 9408 32768 0]
      [1057 2137 3212 32768 0]
      [10018 17067 21491 32768 0]
      [7380 12582 16453 32768 0]
      [6068 10845 14339 32768 0]
      [5098 9198 12555 32768 0]
      [4312 8010 11119 32768 0]
      [3700 6966 9781 32768 0]
      [1693 3326 4887 32768 0]
      [18757 24930 27774 32768 0]
      [17648 24596 27817 32768 0]
      [14707 22052 26026 32768 0]
      [11720 18852 23292 32768 0]
      [9357 15952 20525 32768 0]
      [7810 13753 18210 32768 0]
      [3879 7333 10328 32768 0]
    ]
    [
      [9040 14786 18360 32768 0]
      [9979 15718 19415 32768 0]
      [7913 13918 18311 32768 0]
      [5859 10889 15184 32768 0]
      [4593 8677 12510 32768 0]
      [3820 7396 10791 32768 0]
      [1730 3471 5192 32768 0]
      [11803 18365 22709 32768 0]
      [11419 18058 22225 32768 0]
      [9418 15774 20243 32768 0]
      [7539 13325 17657 32768 0]
      [6233 11317 15384 32768 0]
      [5137 9656 13545 32768 0]
      [2977 5774 8349 32768 0]
      [21207 27246 29640 32768 0]
      [19547 26578 29497 32768 0]
      [16169 23871 27690 32768 0]
      [12820 20458 25018 32768 0]
      [10224 17332 22214 32768 0]
      [8526 15048 19884 32768 0]
      [5037 9410 13118 32768 0]
    ]
    [
      [12162 18785 22648 32768 0]
      [12749 19697 23806 32768 0]
      [8580 15297 20346 32768 0]
      [6169 11749 16543 32768 0]
      [4836 9391 13448 32768 0]
      [3821 7711 11613 32768 0]
      [2228 4601 7070 32768 0]
      [16319 24725 28280 32768 0]
      [15698 23277 27168 32768 0]
      [12726 20368 25047 32768 0]
      [9912 17015 21976 32768 0]
      [7888 14220 19179 32768 0]
      [6777 12284 17018 32768 0]
      [4492 8590 12252 32768 0]
      [23249 28904 30947 32768 0]
      [21050 27908 30512 32768 0]
      [17440 25340 28949 32768 0]
      [14059 22018 26541 32768 0]
      [11288 18903 23898 32768 0]
      [9411 16342 21428 32768 0]
      [6278 11588 15944 32768 0]
    ]
  ])

;; ---------------------------------------------------------------------
;; ADST extension tables (ADR-2607122000 Migration step 9 continuation,
;; TX_4X4/luma ADST support -- see av1.decode-block namespace docstring's
;; ADST section). Same slicing discipline as the TX_32X32/luma tables
;; above (q-ctx-idx bucket x TX_4X4(=index 0 of the TX_SIZES dimension) x
;; luma(ptype=0) x ctx), extracted with the same brace-matching parser used
;; for every other table in this namespace (10.additional.tables.md,
;; fetched 2026-07-13) and spot-checked field-for-field against the raw
;; spec markdown at both the first and last row of each slice (to rule out
;; the parser having grabbed the wrong q-ctx-idx/tx-size/ptype block) --
;; see the commit introducing this section for the exact grep-based
;; cross-checks performed. Only TX_4X4 needed: this repo's ADST extension
;; supports exactly one new luma leaf shape, BLOCK_4X4/TX_4X4 (see
;; av1.decode-block).

;; Default_Txb_Skip_Cdf[q-ctx-idx][TX_4X4][ctx][3], ctx = TXB_SKIP_CONTEXTS (13).
(def Default-Txb-Skip-Cdf-4x4-Luma
  [
    [
      [31849 32768 0]
      [5892 32768 0]
      [12112 32768 0]
      [21935 32768 0]
      [20289 32768 0]
      [27473 32768 0]
      [32487 32768 0]
      [7654 32768 0]
      [19473 32768 0]
      [29984 32768 0]
      [9961 32768 0]
      [30242 32768 0]
      [32117 32768 0]
    ]
    [
      [30371 32768 0]
      [7570 32768 0]
      [13155 32768 0]
      [20751 32768 0]
      [20969 32768 0]
      [27067 32768 0]
      [32013 32768 0]
      [5495 32768 0]
      [17942 32768 0]
      [28280 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [29614 32768 0]
      [9068 32768 0]
      [12924 32768 0]
      [19538 32768 0]
      [17737 32768 0]
      [24619 32768 0]
      [30642 32768 0]
      [4119 32768 0]
      [16026 32768 0]
      [25657 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [26887 32768 0]
      [6729 32768 0]
      [10361 32768 0]
      [17442 32768 0]
      [15045 32768 0]
      [22478 32768 0]
      [29072 32768 0]
      [2713 32768 0]
      [11861 32768 0]
      [20773 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
  ])

;; Default_Eob_Pt_16_Cdf[q-ctx-idx][ptype=luma][class=TX_CLASS_2D][6] -- this
;; namespace's ADST TxTypes (ADST_DCT/DCT_ADST/ADST_ADST) are all
;; TX_CLASS_2D (get_tx_class only returns VERT/HORIZ for V_*/H_* types, which
;; av1.decode-block restricts away, see its docstring), so class index 0 is
;; the only row needed.
(def Default-Eob-Pt-16-Cdf-Luma
  [
    [840 1039 1980 4895 32768 0]
    [2125 2551 5165 8946 32768 0]
    [4016 4897 8881 14968 32768 0]
    [6708 8958 14746 22133 32768 0]
  ])

;; Default_Eob_Extra_Cdf[q-ctx-idx][TX_4X4][ptype=luma][ctx][3], ctx = EOB_COEF_CONTEXTS (9).
(def Default-Eob-Extra-Cdf-4x4-Luma
  [
    [
      [16961 32768 0]
      [17223 32768 0]
      [7621 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [17471 32768 0]
      [20223 32768 0]
      [11357 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [18983 32768 0]
      [20512 32768 0]
      [14885 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [20177 32768 0]
      [20789 32768 0]
      [20262 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
  ])

;; Default_Coeff_Base_Eob_Cdf[q-ctx-idx][TX_4X4][ptype=luma][ctx][4], ctx = SIG_COEF_CONTEXTS_EOB (4).
(def Default-Coeff-Base-Eob-Cdf-4x4-Luma
  [
    [
      [17837 29055 32768 0]
      [29600 31446 32768 0]
      [30844 31878 32768 0]
      [24926 28948 32768 0]
    ]
    [
      [17560 29888 32768 0]
      [29671 31549 32768 0]
      [31007 32056 32768 0]
      [27286 30006 32768 0]
    ]
    [
      [20092 30774 32768 0]
      [30695 32020 32768 0]
      [31131 32103 32768 0]
      [28666 30870 32768 0]
    ]
    [
      [22497 31198 32768 0]
      [31715 32495 32768 0]
      [31606 32337 32768 0]
      [30388 31990 32768 0]
    ]
  ])

;; Default_Coeff_Base_Cdf[q-ctx-idx][TX_4X4][ptype=luma][ctx][5], ctx = SIG_COEF_CONTEXTS (42).
;; Coeff_Base_Ctx_Offset[TX_4X4] is NOT re-transcribed: the reachable subset
;; (row/col in 0..3, since TX_4X4's bwl=2) is identical to
;; Coeff-Base-Ctx-Offset-32x32's first 4x4 sub-block (spot-checked against
;; the spec's own table -- only the unreachable row/col==4 padding entries
;; differ, never touched for TX_4X4's bwl=2), so that table is reused as-is.
(def Default-Coeff-Base-Cdf-4x4-Luma
  [
    [
      [4034 8930 12727 32768 0]
      [18082 29741 31877 32768 0]
      [12596 26124 30493 32768 0]
      [9446 21118 27005 32768 0]
      [6308 15141 21279 32768 0]
      [2463 6357 9783 32768 0]
      [20667 30546 31929 32768 0]
      [13043 26123 30134 32768 0]
      [8151 18757 24778 32768 0]
      [5255 12839 18632 32768 0]
      [2820 7206 11161 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [15736 27553 30604 32768 0]
      [11210 23794 28787 32768 0]
      [5947 13874 19701 32768 0]
      [4215 9323 13891 32768 0]
      [2833 6462 10059 32768 0]
      [19605 30393 31582 32768 0]
      [13523 26252 30248 32768 0]
      [8446 18622 24512 32768 0]
      [3818 10343 15974 32768 0]
      [1481 4117 6796 32768 0]
      [22649 31302 32190 32768 0]
      [14829 27127 30449 32768 0]
      [8313 17702 23304 32768 0]
      [3022 8301 12786 32768 0]
      [1536 4412 7184 32768 0]
      [22354 29774 31372 32768 0]
      [14723 25472 29214 32768 0]
      [6673 13745 18662 32768 0]
      [2068 5766 9322 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [6041 11854 15927 32768 0]
      [20326 30905 32251 32768 0]
      [14164 26831 30725 32768 0]
      [9760 20647 26585 32768 0]
      [6416 14953 21219 32768 0]
      [2966 7151 10891 32768 0]
      [23567 31374 32254 32768 0]
      [14978 27416 30946 32768 0]
      [9434 20225 26254 32768 0]
      [6658 14558 20535 32768 0]
      [3916 8677 12989 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [18088 29545 31587 32768 0]
      [13062 25843 30073 32768 0]
      [8940 16827 22251 32768 0]
      [7654 13220 17973 32768 0]
      [5733 10316 14456 32768 0]
      [22879 31388 32114 32768 0]
      [15215 27993 30955 32768 0]
      [9397 19445 24978 32768 0]
      [3442 9813 15344 32768 0]
      [1368 3936 6532 32768 0]
      [25494 32033 32406 32768 0]
      [16772 27963 30718 32768 0]
      [9419 18165 23260 32768 0]
      [2677 7501 11797 32768 0]
      [1516 4344 7170 32768 0]
      [26556 31454 32101 32768 0]
      [17128 27035 30108 32768 0]
      [8324 15344 20249 32768 0]
      [1903 5696 9469 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [8896 16227 20630 32768 0]
      [23629 31782 32527 32768 0]
      [15173 27755 31321 32768 0]
      [10158 21233 27382 32768 0]
      [6420 14857 21558 32768 0]
      [3269 8155 12646 32768 0]
      [24835 32009 32496 32768 0]
      [16509 28421 31579 32768 0]
      [10957 21514 27418 32768 0]
      [7881 15930 22096 32768 0]
      [5388 10960 15918 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [20745 30773 32093 32768 0]
      [15200 27221 30861 32768 0]
      [13032 20873 25667 32768 0]
      [12285 18663 23494 32768 0]
      [11563 17481 21489 32768 0]
      [26260 31982 32320 32768 0]
      [15397 28083 31100 32768 0]
      [9742 19217 24824 32768 0]
      [3261 9629 15362 32768 0]
      [1480 4322 7499 32768 0]
      [27599 32256 32460 32768 0]
      [16857 27659 30774 32768 0]
      [9551 18290 23748 32768 0]
      [3052 8933 14103 32768 0]
      [2021 5910 9787 32768 0]
      [29005 32015 32392 32768 0]
      [17677 27694 30863 32768 0]
      [9204 17356 23219 32768 0]
      [2403 7516 12814 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [7062 16472 22319 32768 0]
      [24538 32261 32674 32768 0]
      [13675 28041 31779 32768 0]
      [8590 20674 27631 32768 0]
      [5685 14675 22013 32768 0]
      [3655 9898 15731 32768 0]
      [26493 32418 32658 32768 0]
      [16376 29342 32090 32768 0]
      [10594 22649 28970 32768 0]
      [8176 17170 24303 32768 0]
      [5605 12694 19139 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
      [23888 31902 32542 32768 0]
      [18612 29687 31987 32768 0]
      [16245 24852 29249 32768 0]
      [15765 22608 27559 32768 0]
      [19895 24699 27510 32768 0]
      [28401 32212 32457 32768 0]
      [15274 27825 30980 32768 0]
      [9364 18128 24332 32768 0]
      [2283 8193 15082 32768 0]
      [1228 3972 7881 32768 0]
      [29455 32469 32620 32768 0]
      [17981 28245 31388 32768 0]
      [10921 20098 26240 32768 0]
      [3743 11829 18657 32768 0]
      [2374 9593 15715 32768 0]
      [31068 32466 32635 32768 0]
      [20321 29572 31971 32768 0]
      [10771 20255 27119 32768 0]
      [2795 10410 17361 32768 0]
      [8192 16384 24576 32768 0]
      [8192 16384 24576 32768 0]
    ]
  ])

;; Default_Coeff_Br_Cdf[q-ctx-idx][Min(TX_4X4,TX_32X32)=TX_4X4][ptype=luma][ctx][5], ctx = LEVEL_CONTEXTS (21).
(def Default-Coeff-Br-Cdf-4x4-Luma
  [
    [
      [14298 20718 24174 32768 0]
      [12536 19601 23789 32768 0]
      [8712 15051 19503 32768 0]
      [6170 11327 15434 32768 0]
      [4742 8926 12538 32768 0]
      [3803 7317 10546 32768 0]
      [1696 3317 4871 32768 0]
      [14392 19951 22756 32768 0]
      [15978 23218 26818 32768 0]
      [12187 19474 23889 32768 0]
      [9176 15640 20259 32768 0]
      [7068 12655 17028 32768 0]
      [5656 10442 14472 32768 0]
      [2580 4992 7244 32768 0]
      [12136 18049 21426 32768 0]
      [13784 20721 24481 32768 0]
      [10836 17621 21900 32768 0]
      [8372 14444 18847 32768 0]
      [6523 11779 16000 32768 0]
      [5337 9898 13760 32768 0]
      [3034 5860 8462 32768 0]
    ]
    [
      [14995 21341 24749 32768 0]
      [13158 20289 24601 32768 0]
      [8941 15326 19876 32768 0]
      [6297 11541 15807 32768 0]
      [4817 9029 12776 32768 0]
      [3731 7273 10627 32768 0]
      [1847 3617 5354 32768 0]
      [14472 19659 22343 32768 0]
      [16806 24162 27533 32768 0]
      [12900 20404 24713 32768 0]
      [9411 16112 20797 32768 0]
      [7056 12697 17148 32768 0]
      [5544 10339 14460 32768 0]
      [2954 5704 8319 32768 0]
      [12464 18071 21354 32768 0]
      [15482 22528 26034 32768 0]
      [12070 19269 23624 32768 0]
      [8953 15406 20106 32768 0]
      [7027 12730 17220 32768 0]
      [5887 10913 15140 32768 0]
      [3793 7278 10447 32768 0]
    ]
    [
      [16138 22223 25509 32768 0]
      [15347 22430 26332 32768 0]
      [9614 16736 21332 32768 0]
      [6600 12275 16907 32768 0]
      [4811 9424 13547 32768 0]
      [3748 7809 11420 32768 0]
      [2254 4587 6890 32768 0]
      [15196 20284 23177 32768 0]
      [18317 25469 28451 32768 0]
      [13918 21651 25842 32768 0]
      [10052 17150 21995 32768 0]
      [7499 13630 18587 32768 0]
      [6158 11417 16003 32768 0]
      [4014 7785 11252 32768 0]
      [15048 21067 24384 32768 0]
      [18202 25346 28553 32768 0]
      [14302 22019 26356 32768 0]
      [10839 18139 23166 32768 0]
      [8715 15744 20806 32768 0]
      [7536 13576 18544 32768 0]
      [5413 10335 14498 32768 0]
    ]
    [
      [18315 24289 27551 32768 0]
      [16854 24068 27835 32768 0]
      [10140 17927 23173 32768 0]
      [6722 12982 18267 32768 0]
      [4661 9826 14706 32768 0]
      [3832 8165 12294 32768 0]
      [2795 6098 9245 32768 0]
      [17145 23326 26672 32768 0]
      [20733 27680 30308 32768 0]
      [16032 24461 28546 32768 0]
      [11653 20093 25081 32768 0]
      [9290 16429 22086 32768 0]
      [7796 14598 19982 32768 0]
      [6502 12378 17441 32768 0]
      [21681 27732 30320 32768 0]
      [22389 29044 31261 32768 0]
      [19027 26731 30087 32768 0]
      [14739 23755 28624 32768 0]
      [11358 20778 25511 32768 0]
      [10995 18073 24190 32768 0]
      [9162 14990 20617 32768 0]
    ]
  ])

;; Default_Scan_4x4[16] (10.additional.tables.md).
(def Default-Scan-4x4
  [0 1 4 8 5 2 3 6 9 12 13 10 7 11 14 15])

;; transform_type()/get_tx_set() cdf selection (09.parsing.process.md
;; "intra_tx_type"): TileIntraTxTypeSet1Cdf[Tx_Size_Sqr[txSz]][intraDir],
;; intraDir = YMode (use_filter_intra is always 0 in this repo's scope).
;; Default_Intra_Tx_Type_Set1_Cdf[Tx_Size_Sqr=TX_4X4(index 0)][INTRA_MODES],
;; sliced to the 3 modes av1.decode-block/read-y-mode can ever produce
;; (DC_PRED=0, V_PRED=1, H_PRED=2 -- see Default-Intra-Frame-Y-Mode-Cdf-0-0
;; above for the same restriction pattern). This is the TX_SET_INTRA_1 cdf
;; (7-symbol alphabet, 8 cdf entries): used when get_tx_set() picks
;; TX_SET_INTRA_1 (reduced_tx_set==0 and Tx_Size_Sqr[txSz！=TX_16X16),
;; which always holds for this repo's TX_4X4-only ADST scope unless the
;; frame header's reduced_tx_set is 1.
(def Default-Intra-Tx-Type-Set1-Cdf-4x4-Dc-V-H
  [
    [1535 8035 9461 12751 23467 27825 32768 0]
    [564 3335 9709 10870 18143 28094 32768 0]
    [672 3247 3676 11982 19415 23127 32768 0]
  ])

;; Default_Intra_Tx_Type_Set2_Cdf[Tx_Size_Sqr][INTRA_MODES][6]: used when
;; get_tx_set() picks TX_SET_INTRA_2 (reduced_tx_set==1). Spot-checked
;; against the raw spec table: EVERY (Tx_Size_Sqr, mode) entry at
;; Tx_Size_Sqr==TX_4X4 (the only context this repo's ADST scope reaches) is
;; the identical uniform row below (5-symbol equiprobable cdf) -- so a
;; single constant row (not a per-mode table) is sufficient and exact, not
;; an approximation.
(def Default-Intra-Tx-Type-Set2-Cdf-Uniform
  [6554 13107 19661 26214 32768 0])

;; Tx_Type_Intra_Inv_Set1/Set2 (06.bitstream.syntax.md #Transform type
;; syntax): maps the decoded intra_tx_type symbol to the actual TxType.
;; Keyword-encoded (this repo has no need to match the spec's own internal
;; TxType integer values, only to dispatch consistently between
;; av1.decode-block and av1.transform). :IDTX/:V-DCT/:H-DCT are structurally
;; reachable symbol values but out of scope (av1.decode-block throws if
;; decoded) -- av1.transform has no identity-transform implementation.
(def Tx-Type-Intra-Inv-Set1 [:IDTX :DCT_DCT :V-DCT :H-DCT :ADST_ADST :ADST_DCT :DCT_ADST])
(def Tx-Type-Intra-Inv-Set2 [:IDTX :DCT_DCT :ADST_ADST :ADST_DCT :DCT_ADST])

(defn q-ctx-idx
  "09.parsing.process.md init_coeff_cdfs()'s COEFF_CDF_Q_CTXS bucket
   selection: base_q_idx <=20 -> 0, <=60 -> 1, <=120 -> 2, else -> 3."
  [base-q-idx]
  (cond (<= base-q-idx 20) 0 (<= base-q-idx 60) 1 (<= base-q-idx 120) 2 :else 3))

;; ---------------------------------------------------------------------
;; Chroma (Cb/Cr) extension tables (ADR-2607122000 Migration step 9
;; continuation -- chroma decode, fetched 2026-07-13 from the same
;; AOMediaCodec/av1-spec master snapshot as every other table above).
;; SCOPE: 4:2:0 only (subsampling_x=1,subsampling_y=1), and this repo's
;; only supported leaf shape (BLOCK_32X32 luma) subsamples to exactly
;; BLOCK_16X16/TX_16X16 chroma (Subsampled_Size[BLOCK_32X32][1][1] ==
;; BLOCK_16X16, Max_Tx_Size_Rect[BLOCK_16X16] == TX_16X16 -- both spot-
;; checked directly against 06.bitstream.syntax.md rather than adding a
;; redundant table, since this repo only ever needs this one entry) --
;; so only the TX_16X16/chroma (ptype=1) slices of the same COEFF_CDF_Q_CTXS
;; x TX_SIZES x PLANE_TYPES x ctx spec tables used for luma/TX_32X32 above
;; are needed here (extracted the same way: q-ctx-idx bucket x TX_16X16
;; index (2) x ptype=1 (chroma) slice, mechanically sliced from
;; 10.additional.tables.md's Default_Txb_Skip_Cdf / Default_Eob_Pt_256_Cdf
;; / Default_Eob_Extra_Cdf / Default_Dc_Sign_Cdf / Default_Coeff_Base_Eob_Cdf
;; / Default_Coeff_Base_Cdf / Default_Coeff_Br_Cdf with the same brace-
;; matching parser used for the luma tables, spot-checked by re-extracting
;; the TX_32X32/luma slice with the same script and diffing against the
;; existing Default-*-32x32-Luma tables above -- byte-identical, confirming
;; the slicing indices are correct). NOTE: unlike the luma-only tables
;; above, these chroma CDF tables are genuinely SHARED adaptation state
;; between the U and V planes (spec's ptype dimension is "luma vs chroma",
;; not "Y vs U vs V" -- see av1.decode-block's per-plane-spec comments for
;; how the shared-vs-per-plane state split is threaded through); only the
;; AboveDcContext/LeftDcContext/AboveLevelContext/LeftLevelContext cross-
;; block tracking is genuinely per-plane (U and V tracked independently).
;; Coeff_Base_Ctx_Offset[TX_16X16] is NOT re-transcribed here: spec's own
;; table (09.parsing.process.md) has IDENTICAL {0,1,6,6,21}/... rows for
;; TX_8X8/TX_16X16/TX_32X32/TX_64X64 (only TX_4X4's row differs, and this
;; repo never reaches TX_4X4), so `Coeff-Base-Ctx-Offset-32x32` above is
;; reused directly for TX_16X16 too (spot-checked field-for-field against
;; the spec, not assumed).

;; Default-Txb-Skip-Cdf-16x16-Chroma
(def Default-Txb-Skip-Cdf-16x16-Chroma
  [
    [
      [29957 32768 0]
      [5391 32768 0]
      [18039 32768 0]
      [23566 32768 0]
      [22431 32768 0]
      [25822 32768 0]
      [32197 32768 0]
      [3778 32768 0]
      [15336 32768 0]
      [28981 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [31901 32768 0]
      [10311 32768 0]
      [18047 32768 0]
      [24806 32768 0]
      [23288 32768 0]
      [27914 32768 0]
      [32296 32768 0]
      [4215 32768 0]
      [15756 32768 0]
      [28341 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [32363 32768 0]
      [10692 32768 0]
      [19090 32768 0]
      [24357 32768 0]
      [24442 32768 0]
      [28312 32768 0]
      [32169 32768 0]
      [3648 32768 0]
      [15690 32768 0]
      [26815 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [32510 32768 0]
      [8430 32768 0]
      [17318 32768 0]
      [24154 32768 0]
      [23674 32768 0]
      [28789 32768 0]
      [32139 32768 0]
      [3440 32768 0]
      [13117 32768 0]
      [22702 32768 0]
      [16384 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
  ])

;; Default-Eob-Pt-256-Cdf-Chroma
(def Default-Eob-Pt-256-Cdf-Chroma
  [
    [2520 3240 5952 8870 12577 17558 19954 24168 32768 0]
    [6402 8148 12623 15072 18728 22847 26447 29377 32768 0]
    [11514 13794 17480 20754 24361 27378 29492 31277 32768 0]
    [23110 24597 27140 28894 30167 30927 31392 32094 32768 0]
  ])

;; Default-Eob-Extra-Cdf-16x16-Chroma
(def Default-Eob-Extra-Cdf-16x16-Chroma
  [
    [
      [23959 32768 0]
      [20799 32768 0]
      [19021 32768 0]
      [16203 32768 0]
      [17886 32768 0]
      [14144 32768 0]
      [12010 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [24220 32768 0]
      [22480 32768 0]
      [17737 32768 0]
      [18916 32768 0]
      [19268 32768 0]
      [18412 32768 0]
      [18844 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [22041 32768 0]
      [23434 32768 0]
      [20001 32768 0]
      [20554 32768 0]
      [20951 32768 0]
      [20145 32768 0]
      [15562 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
    [
      [22752 32768 0]
      [25006 32768 0]
      [22075 32768 0]
      [21576 32768 0]
      [17740 32768 0]
      [21690 32768 0]
      [19211 32768 0]
      [16384 32768 0]
      [16384 32768 0]
    ]
  ])

;; Default-Dc-Sign-Cdf-Chroma
(def Default-Dc-Sign-Cdf-Chroma
  [
    [
      [15232 32768 0]
      [12928 32768 0]
      [17280 32768 0]
    ]
    [
      [15232 32768 0]
      [12928 32768 0]
      [17280 32768 0]
    ]
    [
      [15232 32768 0]
      [12928 32768 0]
      [17280 32768 0]
    ]
    [
      [15232 32768 0]
      [12928 32768 0]
      [17280 32768 0]
    ]
  ])

;; Default-Coeff-Base-Eob-Cdf-16x16-Chroma
(def Default-Coeff-Base-Eob-Cdf-16x16-Chroma
  [
    [
      [18857 23865 32768 0]
      [31428 32428 32768 0]
      [31744 32373 32768 0]
      [31775 32526 32768 0]
    ]
    [
      [17187 27668 32768 0]
      [31714 32550 32768 0]
      [32283 32678 32768 0]
      [31930 32563 32768 0]
    ]
    [
      [25476 30366 32768 0]
      [32169 32687 32768 0]
      [32479 32689 32768 0]
      [31673 32634 32768 0]
    ]
    [
      [26473 30507 32768 0]
      [32431 32723 32768 0]
      [32196 32611 32768 0]
      [31588 32528 32768 0]
    ]
  ])

;; Default-Coeff-Base-Cdf-16x16-Chroma
(def Default-Coeff-Base-Cdf-16x16-Chroma
  [
    [
      [5673 14302 19711 32768 0]
      [26251 30701 31834 32768 0]
      [12782 23783 27803 32768 0]
      [9127 20657 25808 32768 0]
      [6368 16208 21462 32768 0]
      [2465 7177 10822 32768 0]
      [29961 32563 32719 32768 0]
      [18318 29891 31949 32768 0]
      [11361 24514 29357 32768 0]
      [7900 19603 25607 32768 0]
      [4002 10590 15546 32768 0]
      [29637 32310 32595 32768 0]
      [18296 29913 31809 32768 0]
      [10144 21515 26871 32768 0]
      [5358 14322 20394 32768 0]
      [3067 8362 13346 32768 0]
      [28652 32470 32676 32768 0]
      [17538 30771 32209 32768 0]
      [13924 26882 30494 32768 0]
      [10496 22837 27869 32768 0]
      [7236 16396 21621 32768 0]
      [30743 32687 32746 32768 0]
      [23006 31676 32489 32768 0]
      [14494 27828 31120 32768 0]
      [10174 22801 28352 32768 0]
      [6242 15281 21043 32768 0]
      [25817 32243 32720 32768 0]
      [18618 31367 32325 32768 0]
      [13997 28318 31878 32768 0]
      [12255 26534 31383 32768 0]
      [9561 21588 28450 32768 0]
      [28188 32635 32724 32768 0]
      [22060 32365 32728 32768 0]
      [18102 30690 32528 32768 0]
      [14196 28864 31999 32768 0]
      [12262 25792 30865 32768 0]
      [24176 32109 32628 32768 0]
      [18280 29681 31963 32768 0]
      [10205 23703 29664 32768 0]
      [7889 20025 27676 32768 0]
      [6060 16743 23970 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [6465 16958 21688 32768 0]
      [25199 31514 32360 32768 0]
      [14774 27149 30607 32768 0]
      [9257 21438 26972 32768 0]
      [5723 15183 21882 32768 0]
      [3150 8879 13731 32768 0]
      [26989 32262 32682 32768 0]
      [17396 29937 32085 32768 0]
      [11387 24901 29784 32768 0]
      [7289 18821 25548 32768 0]
      [3734 10577 16086 32768 0]
      [29728 32501 32695 32768 0]
      [17431 29701 31903 32768 0]
      [9921 22826 28300 32768 0]
      [5896 15434 22068 32768 0]
      [3430 9646 14757 32768 0]
      [28614 32511 32705 32768 0]
      [19364 30638 32263 32768 0]
      [13129 26254 30402 32768 0]
      [8754 20484 26440 32768 0]
      [4378 11607 17110 32768 0]
      [30292 32671 32744 32768 0]
      [21780 31603 32501 32768 0]
      [14314 27829 31291 32768 0]
      [9611 22327 28263 32768 0]
      [4890 13087 19065 32768 0]
      [25862 32567 32733 32768 0]
      [20794 32050 32567 32768 0]
      [17243 30625 32254 32768 0]
      [13283 27628 31474 32768 0]
      [9669 22532 28918 32768 0]
      [27435 32697 32748 32768 0]
      [24922 32390 32714 32768 0]
      [21449 31504 32536 32768 0]
      [16392 29729 31832 32768 0]
      [11692 24884 29076 32768 0]
      [24193 32290 32735 32768 0]
      [18909 31104 32563 32768 0]
      [12236 26841 31403 32768 0]
      [8171 21840 29082 32768 0]
      [7224 17280 25275 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [9185 19694 24688 32768 0]
      [26081 31985 32621 32768 0]
      [16015 29000 31787 32768 0]
      [10542 23690 29206 32768 0]
      [6732 17945 24677 32768 0]
      [3916 11039 16722 32768 0]
      [28224 32566 32744 32768 0]
      [19100 31138 32485 32768 0]
      [12528 26620 30879 32768 0]
      [7741 20277 26885 32768 0]
      [4566 12845 18990 32768 0]
      [29933 32593 32718 32768 0]
      [17670 30333 32155 32768 0]
      [10385 23600 28909 32768 0]
      [6243 16236 22407 32768 0]
      [3976 10389 16017 32768 0]
      [28377 32561 32738 32768 0]
      [19366 31175 32482 32768 0]
      [13327 27175 31094 32768 0]
      [8258 20769 27143 32768 0]
      [4703 13198 19527 32768 0]
      [31086 32706 32748 32768 0]
      [22853 31902 32583 32768 0]
      [14759 28186 31419 32768 0]
      [9284 22382 28348 32768 0]
      [5585 15192 21868 32768 0]
      [28291 32652 32746 32768 0]
      [19849 32107 32571 32768 0]
      [14834 26818 29214 32768 0]
      [10306 22594 28672 32768 0]
      [6615 17384 23384 32768 0]
      [28947 32604 32745 32768 0]
      [25625 32289 32646 32768 0]
      [18758 28672 31403 32768 0]
      [10017 23430 28523 32768 0]
      [6862 15269 22131 32768 0]
      [23933 32509 32739 32768 0]
      [19927 31495 32631 32768 0]
      [11903 26023 30621 32768 0]
      [7026 20094 27252 32768 0]
      [5998 18106 24437 32768 0]
      [8192 16384 24576 32768 0]
    ]
    [
      [7833 18369 24095 32768 0]
      [26650 32273 32702 32768 0]
      [16371 29961 32191 32768 0]
      [11055 24082 29629 32768 0]
      [6892 18644 25400 32768 0]
      [5006 13057 19240 32768 0]
      [29834 32666 32748 32768 0]
      [19577 31335 32570 32768 0]
      [12253 26509 31122 32768 0]
      [7991 20772 27711 32768 0]
      [5677 15910 23059 32768 0]
      [30109 32532 32720 32768 0]
      [16747 30166 32252 32768 0]
      [10134 23542 29184 32768 0]
      [5791 16176 23556 32768 0]
      [4362 10414 17284 32768 0]
      [29492 32626 32748 32768 0]
      [19894 31402 32525 32768 0]
      [12942 27071 30869 32768 0]
      [8346 21216 27405 32768 0]
      [6572 17087 23859 32768 0]
      [32035 32735 32748 32768 0]
      [22957 31838 32618 32768 0]
      [14724 28572 31772 32768 0]
      [10364 23999 29553 32768 0]
      [7004 18433 25655 32768 0]
      [27528 32277 32681 32768 0]
      [16959 31171 32096 32768 0]
      [10486 23593 27962 32768 0]
      [8192 16384 23211 32768 0]
      [8937 17873 20852 32768 0]
      [27715 32002 32615 32768 0]
      [15073 29491 31676 32768 0]
      [11264 24576 28672 32768 0]
      [2341 18725 23406 32768 0]
      [7282 18204 25486 32768 0]
      [28547 32213 32657 32768 0]
      [20788 29773 32239 32768 0]
      [6780 21469 30508 32768 0]
      [5958 14895 23831 32768 0]
      [16384 21845 27307 32768 0]
      [8192 16384 24576 32768 0]
    ]
  ])

;; Default-Coeff-Br-Cdf-16x16-Chroma
(def Default-Coeff-Br-Cdf-16x16-Chroma
  [
    [
      [10870 16684 20949 32768 0]
      [9664 15230 18680 32768 0]
      [6886 12109 15408 32768 0]
      [4825 8900 12305 32768 0]
      [3630 7162 10314 32768 0]
      [3036 6429 9387 32768 0]
      [1671 3296 4940 32768 0]
      [13819 19159 23026 32768 0]
      [11984 19108 23120 32768 0]
      [10690 17210 21663 32768 0]
      [7984 14154 18333 32768 0]
      [6868 12294 16124 32768 0]
      [5274 8994 12868 32768 0]
      [2988 5771 8424 32768 0]
      [19736 26647 29141 32768 0]
      [18933 26070 28984 32768 0]
      [15779 23048 27200 32768 0]
      [12638 20061 24532 32768 0]
      [10692 17545 22220 32768 0]
      [9217 15251 20054 32768 0]
      [5078 9284 12594 32768 0]
    ]
    [
      [13960 19617 22829 32768 0]
      [11150 17341 21228 32768 0]
      [7150 12964 17190 32768 0]
      [5331 10002 13867 32768 0]
      [4167 7744 11057 32768 0]
      [3480 6629 9646 32768 0]
      [1883 3784 5686 32768 0]
      [18752 25660 28912 32768 0]
      [16968 24586 28030 32768 0]
      [13520 21055 25313 32768 0]
      [10453 17626 22280 32768 0]
      [8386 14505 19116 32768 0]
      [6742 12595 17008 32768 0]
      [4273 8140 11499 32768 0]
      [22120 27827 30233 32768 0]
      [20563 27358 29895 32768 0]
      [17076 24644 28153 32768 0]
      [13362 20942 25309 32768 0]
      [10794 17965 22695 32768 0]
      [9014 15652 20319 32768 0]
      [5708 10512 14497 32768 0]
    ]
    [
      [13569 19800 23206 32768 0]
      [13128 19924 23869 32768 0]
      [8329 14841 19403 32768 0]
      [6130 10976 15057 32768 0]
      [4682 8839 12518 32768 0]
      [3656 7409 10588 32768 0]
      [2577 5099 7412 32768 0]
      [22427 28684 30585 32768 0]
      [20913 27750 30139 32768 0]
      [15840 24109 27834 32768 0]
      [12308 20029 24569 32768 0]
      [10216 16785 21458 32768 0]
      [8309 14203 19113 32768 0]
      [6043 11168 15307 32768 0]
      [23166 28901 30998 32768 0]
      [21899 28405 30751 32768 0]
      [18413 26091 29443 32768 0]
      [15233 23114 27352 32768 0]
      [12683 20472 25288 32768 0]
      [10702 18259 23409 32768 0]
      [8125 14464 19226 32768 0]
    ]
    [
      [15820 22738 26488 32768 0]
      [13530 20885 25216 32768 0]
      [8395 15530 20452 32768 0]
      [6574 12321 16380 32768 0]
      [5353 10419 14568 32768 0]
      [4613 8446 12381 32768 0]
      [3440 7158 9903 32768 0]
      [24247 29051 31224 32768 0]
      [22118 28058 30369 32768 0]
      [16498 24768 28389 32768 0]
      [12920 21175 26137 32768 0]
      [10730 18619 25352 32768 0]
      [10187 16279 22791 32768 0]
      [9310 14631 22127 32768 0]
      [24970 30558 32057 32768 0]
      [24801 29942 31698 32768 0]
      [22432 28453 30855 32768 0]
      [19054 25680 29580 32768 0]
      [14392 23036 28109 32768 0]
      [12495 20947 26650 32768 0]
      [12442 20326 26214 32768 0]
    ]
  ])

;; Default-Scan-16x16
(def Default-Scan-16x16
  [0 1 16 32 17 2 3 18 33 48 64 49 34 19 4 5 20 35 50 65 80 96 81 66 51 36 21 6 7 22 37 52 67 82 97 112 128 113 98 83 68 53 38 23 8 9 24 39 54 69 84 99 114 129 144 160 145 130 115 100 85 70 55 40 25 10 11 26 41 56 71 86 101 116 131 146 161 176 192 177 162 147 132 117 102 87 72 57 42 27 12 13 28 43 58 73 88 103 118 133 148 163 178 193 208 224 209 194 179 164 149 134 119 104 89 74 59 44 29 14 15 30 45 60 75 90 105 120 135 150 165 180 195 210 225 240 241 226 211 196 181 166 151 136 121 106 91 76 61 46 31 47 62 77 92 107 122 137 152 167 182 197 212 227 242 243 228 213 198 183 168 153 138 123 108 93 78 63 79 94 109 124 139 154 169 184 199 214 229 244 245 230 215 200 185 170 155 140 125 110 95 111 126 141 156 171 186 201 216 231 246 247 232 217 202 187 172 157 142 127 143 158 173 188 203 218 233 248 249 234 219 204 189 174 159 175 190 205 220 235 250 251 236 221 206 191 207 222 237 252 253 238 223 239 254 255])

;; Default-Uv-Mode-Cfl-Allowed-Cdf-Dc-V-H
(def Default-Uv-Mode-Cfl-Allowed-Cdf-Dc-V-H
  [
    [10407 11208 12900 13181 13823 14175 14899 15656 15986 20086 20995 22455 24212 32768 0]
    [4532 19780 20057 20215 20428 21071 21199 21451 22099 24228 24693 27032 29472 32768 0]
    [5273 5379 20177 20270 20385 20439 20949 21695 21774 23138 24256 24703 26679 32768 0]
  ])

;; ---------------------------------------------------------------------
;; Inter zero-motion-baseline extension tables (ADR-2607122000 Migration
;; step 9 continuation, "first inter-frame support" -- see av1.decode-block/
;; av1.frame-header namespace docstrings). Transcribed field-for-field from
;; AOMediaCodec/av1-spec master, 10.additional.tables.md (fetched
;; 2026-07-13), the same source snapshot the rest of this namespace uses.
;; Every table below is used ONLY by this repo's narrow single-leaf/
;; no-neighbor/single-ref/GLOBALMV-or-NEWMV-zero-mv inter scope (see
;; av1.decode-block's "Find MV stack" section) -- none of these are general
;; enough (e.g. compound/comp_ref/interp_filter/motion_mode) to serve a
;; wider inter scope without further transcription.

;; Default_Is_Inter_Cdf[ IS_INTER_CONTEXTS=4 ][ 3 ]. This repo's only
;; reachable ctx (no avail neighbors) is 0.
(def Default-Is-Inter-Cdf
  [[806 32768 0]
   [16662 32768 0]
   [20186 32768 0]
   [26538 32768 0]])

;; Default_Single_Ref_Cdf[ REF_CONTEXTS=3 ][ SINGLE_REFS-1=6 ][ 3 ], indexed
;; [ctx][p-1] for single_ref_p1..p6 (p1=index 0 .. p6=index 5). This repo's
;; only reachable ctx (no avail neighbors -> count_refs always 0 ->
;; ref_count_ctx(0,0)=1) is row 1; rows 0/2 are transcribed for completeness
;; but never exercised by this repo's fixtures.
(def Default-Single-Ref-Cdf
  [[[4897 32768 0] [1555 32768 0] [4236 32768 0] [8650 32768 0] [904 32768 0] [1444 32768 0]]
   [[16973 32768 0] [16751 32768 0] [19647 32768 0] [24773 32768 0] [11014 32768 0] [15087 32768 0]]
   [[29744 32768 0] [30279 32768 0] [31194 32768 0] [31895 32768 0] [26875 32768 0] [30304 32768 0]]])

;; Default_New_Mv_Cdf[ NEW_MV_CONTEXTS=6 ][ 3 ]. This repo's only reachable
;; NewMvContext (find_mv_stack with NumMvFound=0/CloseMatches=0/
;; TotalMatches=0, see av1.decode-block) is 0.
(def Default-New-Mv-Cdf
  [[24035 32768 0] [16630 32768 0] [15339 32768 0] [8386 32768 0] [12222 32768 0] [4676 32768 0]])

;; Default_Zero_Mv_Cdf[ ZERO_MV_CONTEXTS=2 ][ 3 ]. This repo's only reachable
;; ZeroMvContext (use_ref_frame_mvs forced 0, see av1.frame-header) is 0.
(def Default-Zero-Mv-Cdf
  [[2175 32768 0] [1054 32768 0]])

;; Default_Ref_Mv_Cdf[ REF_MV_CONTEXTS=6 ][ 3 ]. This repo's only reachable
;; RefMvContext is 0 -- transcribed in full since ref_mv is read whenever
;; zero_mv==1 (NEARESTMV/NEARMV), which av1.decode-block guards against
;; (throws :unsupported-inter-y-mode) rather than silently mis-decoding, so
;; this table documents the cdf that guard's error path would have needed.
(def Default-Ref-Mv-Cdf
  [[23974 32768 0] [24188 32768 0] [17848 32768 0] [28622 32768 0] [24312 32768 0] [19923 32768 0]])

;; Default_Inter_Tx_Type_Set3_Cdf[ 4 ][ 3 ], indexed by Tx_Size_Sqr[txSz]
;; (09.parsing.process.md "inter_tx_type": TileInterTxTypeSet3Cdf[
;; Tx_Size_Sqr[txSz] ]) -- NOT by q_ctx_idx like the coefficient tables
;; above. This repo's only inter tx size is TX_32X32, Tx_Size_Sqr[TX_32X32]
;; == TX_32X32 == 3, so only row 3 is ever reached; rows 0..2 are
;; transcribed for completeness.
(def Default-Inter-Tx-Type-Set3-Cdf
  [[16384 32768 0] [4167 32768 0] [1998 32768 0] [748 32768 0]])

;; MV syntax CDF tables (spec #MV syntax / #MV component syntax,
;; 09.parsing.process.md "mv_joint"/"mv_sign"/"mv_class"/"mv_class0_bit"/
;; "mv_class0_fr"/"mv_class0_hp"/"mv_fr"/"mv_hp"/"mv_bit", 10.additional.
;; tables.md, fetched 2026-07-13). Spec indexes several of these by
;; `[MvCtx][comp]` (TileMvSignCdf[MvCtx][comp] etc.), but every one of the
;; spec's own Default_Mv_*_Cdf tables that HAS a comp-like leading
;; dimension (Default_Mv_Class_Cdf/Class0_Fr/Fr, all `[2][...]`) has
;; byte-for-byte IDENTICAL rows for both entries (spot-checked, not
;; assumed) -- so this repo stores the collapsed (comp-independent) shape
;; below; av1.decode-block still threads `comp` (0=row/1=col) into the
;; CDF-adaptation ctx-key it passes to read-cdf-symbol, so the two
;; components' adapted state stays genuinely separate even though they
;; start from the same default row.
(def Default-Mv-Joint-Cdf [4096 11264 19328 32768 0])
(def Default-Mv-Sign-Cdf [16384 32768 0])
(def Default-Mv-Class-Cdf [28672 30976 31858 32320 32551 32656 32740 32757 32762 32767 32768 0])
(def Default-Mv-Class0-Bit-Cdf [27648 32768 0])
;; Default-Mv-Class0-Fr-Cdf indexed by class0_bit (0/1).
(def Default-Mv-Class0-Fr-Cdf
  [[16384 24576 26624 32768 0]
   [12288 21248 24128 32768 0]])
(def Default-Mv-Class0-Hp-Cdf [20480 32768 0])
;; Default-Mv-Bit-Cdf indexed by the mv_bit loop position i (0..MV_OFFSET_BITS-1=9).
(def Default-Mv-Bit-Cdf
  [[17408 32768 0] [17920 32768 0] [18944 32768 0] [20480 32768 0] [22528 32768 0]
   [24576 32768 0] [28672 32768 0] [29952 32768 0] [29952 32768 0] [30720 32768 0]])
(def Default-Mv-Fr-Cdf [8192 17408 21248 32768 0])
(def Default-Mv-Hp-Cdf [16384 32768 0])

;; Tx_Type_Inter_Inv_Set3 (06.bitstream.syntax.md #Transform type syntax):
;; maps the decoded inter_tx_type symbol (0/1) to the actual TxType, for
;; TX_SET_INTER_3 (the only inter tx-type set this repo's TX_32X32-only
;; inter scope can structurally select, per get_tx_set()). :IDTX is
;; structurally reachable but out of scope (av1.transform has no
;; identity-transform implementation) -- av1.decode-block throws if decoded.
(def Tx-Type-Inter-Inv-Set3 [:IDTX :DCT_DCT])


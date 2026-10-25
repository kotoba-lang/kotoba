"""
Usage: python gen_golden.py > /tmp/out.json  (see scripts/regenerate-golden.md)
Generate SGP4 golden vectors from the python `sgp4` package (Vallado C++ port).

INDEPENDENT ORACLE. Nothing here is written from memory: the Vallado
verification cases are the ones whose modulo-10 check digits verified against
`sgp4.tle/checksum` (itself validated against 42 real CelesTrak lines), and the
operational cases were fetched from CelesTrak on 2026-08-26.
"""
import json, sys
from sgp4.api import Satrec, SGP4_ERRORS

CASES = [
    # --- Vallado sgp4-ver.tle, near-earth; check digits verified ---
    ("vallado-00005",
     "1 00005U 58002B   00179.78495062  .00000023  00000-0  28098-4 0  4753",
     "2 00005  34.2682 348.7242 1859667 331.7664  19.3264 10.82419157413667",
     [0.0, 360.0, 720.0, 1080.0, 1440.0]),
    ("vallado-06251",
     "1 06251U 62025E   06176.82412014  .00008885  00000-0  12808-3 0  3985",
     "2 06251  58.0579  54.0425 0030035 139.1568 221.1854 15.56387291  6774",
     [0.0, 120.0, 240.0, 360.0, 480.0, 600.0, 720.0, 1440.0, 2880.0]),
    ("vallado-28057",
     "1 28057U 03049A   06177.78615833  .00000060  00000-0  35940-4 0  1836",
     "2 28057  98.4283 247.6961 0000884  88.1964 271.9322 14.35478080140550",
     [0.0, 120.0, 240.0, 720.0, 1440.0, 2880.0]),
    ("vallado-29141",   # decaying: exercises the error path
     "1 29141U 85108AA  06170.26783845  .99999999  00000-0  13519-0 0   718",
     "2 29141  82.4288 273.4882 0015848 277.2124  83.9133 15.93343074  6828",
     [0.0, 5.0, 10.0, 60.0, 200.0]),
    # --- Vallado deep-space cases: this implementation must REFUSE these ---
    ("vallado-04632-deep",
     "1 04632U 70093B   04031.91070959 -.00000084  00000-0  10000-3 0  9955",
     "2 04632  11.4628 273.1101 1450506 207.6000 143.9350  1.20231981 44145",
     [0.0]),
    ("vallado-08195-deep",
     "1 08195U 75081A   06176.33215444  .00000099  00000-0  11873-3 0   813",
     "2 08195  64.1586 279.0717 6877146 264.7651  20.2257  2.00491383225656",
     [0.0]),
    # --- operational, fetched from CelesTrak 2026-08-26 ---
    ("celestrak-25544-iss",
     "1 25544U 98067A   26237.66055538  .00007716  00000+0  14485-3 0  9993",
     "2 25544  51.6329 316.2335 0007673  83.1052 277.0809 15.49625410582525",
     [0.0, 45.0, 90.0, 500.0, 1440.0, 4320.0]),
    ("celestrak-25994-terra",
     "1 25994U 99068A   26237.80543928  .00000296  00000+0  69197-4 0  9992",
     "2 25994  97.9403 284.5724 0002839  40.3429  49.8605 14.61149123419771",
     [0.0, 100.0, 720.0, 1440.0]),
    ("celestrak-41866-goes16-deep",
     "1 41866U 16071A   26237.66711072 -.00000094  00000+0  00000+0 0  9992",
     "2 41866   0.5042  84.9564 0001350 108.7145 275.7029  1.00273070 35807",
     [0.0]),
]

out = []
for label, l1, l2, mins in CASES:
    s = Satrec.twoline2rv(l1, l2)
    rec = {"label": label, "line1": l1, "line2": l2, "satnum": s.satnum,
           "no_kozai": s.no_kozai, "ecco": s.ecco, "inclo": s.inclo,
           "nodeo": s.nodeo, "argpo": s.argpo, "mo": s.mo, "bstar": s.bstar,
           "jdsatepoch": s.jdsatepoch, "jdsatepochF": s.jdsatepochF,
           "method": s.method, "samples": []}
    for m in mins:
        e, r, v = s.sgp4(s.jdsatepoch, s.jdsatepochF + m / 1440.0)
        rec["samples"].append({"minutes": m, "error": e,
                               "error_msg": SGP4_ERRORS.get(e) if e else None,
                               "r": list(r), "v": list(v)})
    out.append(rec)
json.dump(out, sys.stdout, indent=1)

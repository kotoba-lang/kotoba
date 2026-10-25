"""
Usage: python gen_frames_golden.py > /tmp/out.json  (see scripts/regenerate-golden.md)
Frame-conversion golden. Independent oracles:
   - GMST   : sgp4.propagation.gstime (Vallado port, same source as the propagator)
   - ECEF->geodetic : pyproj / PROJ 9.5 Transformer (EPSG:4978 -> EPSG:4979)
The .cljc implementation shares NO code with either.
"""
import json, sys
from sgp4.propagation import gstime
from pyproj import Transformer

# EPSG:4978 = WGS84 geocentric (ECEF, metres); EPSG:4979 = WGS84 geographic 3D
T = Transformer.from_crs("EPSG:4978", "EPSG:4979", always_xy=True)

GMST_JDS = [2451545.0, 2433281.5, 2460310.5, 2460310.75123, 2455197.31,
            2440587.5, 2470000.123456]

# ECEF points in km: surface, high orbit, poles, and the axis singularity.
ECEF_KM = [
    [6378.137, 0.0, 0.0],
    [0.0, 6378.137, 0.0],
    [0.0, 0.0, 6356.752314245],
    [0.0, 0.0, -6356.752314245],
    [4123.5006, -1003.2699, 5294.5219],
    [-2715.2823, -6619.2643, -0.0134],
    [3988.3102, 5498.9665, 0.9005],
    [1000.0, 1000.0, 6000.0],
    [-4000.0, 3000.0, -4500.0],
    [42164.0, 0.0, 0.0],
    [0.0, 0.0, 7000.0],          # on the spin axis, above the pole
    [1e-9, 1e-9, 6800.0],        # ~on the axis
]

out = {"gmst": [], "geodetic": []}
for jd in GMST_JDS:
    out["gmst"].append({"jd": jd, "rad": gstime(jd)})
for p in ECEF_KM:
    lon, lat, h = T.transform(p[0]*1000.0, p[1]*1000.0, p[2]*1000.0)
    out["geodetic"].append({"ecef_km": p, "lat_deg": lat, "lon_deg": lon,
                            "alt_km": h/1000.0})
json.dump(out, sys.stdout, indent=1)

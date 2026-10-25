(ns sgp4.time
  "Julian dates and Greenwich sidereal time, at the precision SGP4 needs.

  SGP4 is defined against a TLE epoch expressed as `(two-digit year,
  fractional day-of-year)`, and its output frame (TEME) is oriented by
  Greenwich Mean Sidereal Time. Both live here so that neither
  `sgp4.core` nor `sgp4.tle` has to carry a calendar.

  Everything is a pure function of doubles. No clock is read in this
  namespace -- `now` is an argument everywhere, never an ambient read.")

(def ^{:doc "Julian date of the J2000.0 epoch (2000-01-01 12:00 TT)."} j2000 2451545.0)

(def ^{:doc "Julian date of 1949-12-31 00:00 UT.

  Vallado's `gstime` is fed `epoch + 2433281.5`, where `epoch` counts days
  from this instant. Keeping the constant named stops it being read as a
  magic offset."}
  jd-1949-12-31 2433281.5)

(defn leap-year?
  [y]
  (and (zero? (mod y 4))
       (or (not (zero? (mod y 100)))
           (zero? (mod y 400)))))

(defn jd-jan1
  "Julian date of January 1.0 (00:00 UT) of `year`, on the Gregorian calendar.

  The exact Fliegel-Van Flandern conversion, specialised to January 1.

  Not Vallado's `jday`, which is what a first pass reaches for. That one
  reduces to `367*y - floor(7*y/4) + 31 + 1721013.5`, whose leap rule is
  the Julian one: it has no century exception, so it is a day early for
  every year before 1901. Inside a TLE's own range (1957-2056) the two
  agree exactly, which is precisely why the shortcut survives -- it is
  only wrong where a TLE cannot reach, and `jd-jan1` is public.

  Verified against known anchors: 1900-01-01 = 2415020.5,
  1970-01-01 = 2440587.5, 2000-01-01 = 2451544.5."
  [year]
  (let [y (+ year 4799)]
    (- (+ 1.0 306.0
          (* 365.0 y)
          (Math/floor (/ y 4.0))
          (Math/floor (/ y 400.0)))
       (Math/floor (/ y 100.0))
       32045.0
       0.5)))

(defn tle-epoch->jd
  "TLE epoch -> Julian date, split into `[jd frac]`.

  `yy` is the two-digit year exactly as the TLE carries it; the pivot is
  the one Spacetrack uses -- 57..99 means 19yy, 00..56 means 20yy. It is a
  property of the format, not a guess, and it is why a TLE cannot express
  an epoch before 1957 or after 2056.

  `day` is the fractional day-of-year with January 1.0 == 1.0.

  The split keeps the fraction away from the ~2.46e6 integer part: added
  into one double, a fractional day loses about five decimal digits of the
  sub-second field, and SGP4 is propagated in minutes from this instant."
  [yy day]
  (let [year (if (< yy 57) (+ 2000 yy) (+ 1900 yy))
        jd (jd-jan1 year)
        d (- day 1.0)
        whole (Math/floor d)]
    [(+ jd whole) (- d whole)]))

(defn gstime
  "Greenwich Mean Sidereal Time in radians, from a UT1 Julian date.

  IAU-82 polynomial, the same one `sgp4.core` uses to orient TEME. The
  result is wrapped into [0, 2pi)."
  [jdut1]
  (let [tut1 (/ (- jdut1 j2000) 36525.0)
        temp (+ (* -6.2e-6 tut1 tut1 tut1)
                (* 0.093104 tut1 tut1)
                (* (+ (* 876600.0 3600.0) 8640184.812866) tut1)
                67310.54841)
        two-pi (* 2.0 Math/PI)
        ;; degrees -> radians, and seconds-of-time -> degrees (1s == 1/240 deg)
        temp (mod (* temp (/ Math/PI 180.0 240.0)) two-pi)]
    (if (neg? temp) (+ temp two-pi) temp)))

(defn jd->unix-ms
  "Julian date (as `[jd frac]`) -> Unix epoch milliseconds.

  The two parts are converted separately for the same reason they are kept
  separate: 2440587.5 is subtracted from the large part before the small
  part is scaled."
  [jd frac]
  ;; The two terms are scaled separately. Summed first, a fractional day
  ;; sits beside a ~2.0e4-day magnitude and loses about 3e-7 ms -- which is
  ;; 2 micrometres of ISS motion, so it does not matter here, but the same
  ;; addition done in the other direction lost 18 microseconds (0.14 mm),
  ;; and the symmetric form is what makes the round trip closed.
  (+ (* 86400000.0 (- jd 2440587.5)) (* 86400000.0 frac)))

(defn unix-ms->jd
  "Unix epoch milliseconds -> `[jd frac]`."
  [ms]
  ;; `2440587.5 + d` before splitting would put the day fraction next to a
  ;; 2.46e6 magnitude and quantise it to ~1e-10 day (9 microseconds). The
  ;; epoch offset is added to the WHOLE part only, after the split.
  (let [d (/ (double ms) 86400000.0)
        whole (Math/floor d)]
    [(+ 2440587.5 whole) (- d whole)]))

(defn minutes-between
  "Minutes from `[jd0 f0]` to `[jd1 f1]`.

  This is the `tsince` SGP4 takes. The whole-day difference is taken first
  so the subtraction never happens between two ~2.46e6 magnitudes."
  [jd0 f0 jd1 f1]
  (+ (* 1440.0 (- jd1 jd0)) (* 1440.0 (- f1 f0))))

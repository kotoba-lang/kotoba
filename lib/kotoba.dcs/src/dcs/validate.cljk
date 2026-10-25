(ns dcs.validate
  "Structural validation for a dcs.model system: dangling tag references,
  wrong-kind tag references, out-of-range setpoints/limits, malformed
  tuning, and alarm-threshold ordering. `validate` never throws — it returns
  a (possibly empty) vector of problem maps."
  (:require [dcs.model :as m]))

(defn- in-range? [range v]
  (or (nil? range) (nil? v)
      (let [[lo hi] range] (<= lo v hi))))

(defn- check-loop [sys lp]
  (let [pv     (m/tag-by-id sys (:dcs/pv-tag lp))
        out    (m/tag-by-id sys (:dcs/output-tag lp))
        tuning (:dcs/tuning lp)]
    (cond-> []
      (nil? pv)
      (conj {:dcs/error :unknown-pv-tag :dcs/loop (:dcs/id lp) :dcs/tag (:dcs/pv-tag lp)})

      (and pv (not= :ai (:dcs/kind pv)))
      (conj {:dcs/error :wrong-pv-tag-kind :dcs/loop (:dcs/id lp)
             :dcs/tag (:dcs/pv-tag lp) :dcs/kind (:dcs/kind pv)})

      (nil? out)
      (conj {:dcs/error :unknown-output-tag :dcs/loop (:dcs/id lp) :dcs/tag (:dcs/output-tag lp)})

      (and out (not= :ao (:dcs/kind out)))
      (conj {:dcs/error :wrong-output-tag-kind :dcs/loop (:dcs/id lp)
             :dcs/tag (:dcs/output-tag lp) :dcs/kind (:dcs/kind out)})

      (and pv (:dcs/setpoint lp) (not (in-range? (:dcs/range pv) (:dcs/setpoint lp))))
      (conj {:dcs/error :setpoint-out-of-range :dcs/loop (:dcs/id lp)
             :dcs/setpoint (:dcs/setpoint lp) :dcs/range (:dcs/range pv)})

      (and out (:dcs/output-limits lp) (:dcs/range out)
           (let [[lo hi] (:dcs/output-limits lp)
                 [rlo rhi] (:dcs/range out)]
             (or (< lo rlo) (> hi rhi))))
      (conj {:dcs/error :output-limits-out-of-range :dcs/loop (:dcs/id lp)
             :dcs/output-limits (:dcs/output-limits lp) :dcs/range (:dcs/range out)})

      (and tuning (some neg? (vals (select-keys tuning [:kp :ki :kd]))))
      (conj {:dcs/error :negative-tuning :dcs/loop (:dcs/id lp) :dcs/tuning tuning}))))

(defn- check-alarm [sys al]
  (let [tg (m/tag-by-id sys (:dcs/tag al))]
    (cond-> []
      (nil? tg)
      (conj {:dcs/error :unknown-alarm-tag :dcs/alarm (:dcs/id al) :dcs/tag (:dcs/tag al)})

      (and tg (:dcs/setpoint al) (not (in-range? (:dcs/range tg) (:dcs/setpoint al))))
      (conj {:dcs/error :alarm-setpoint-out-of-range :dcs/alarm (:dcs/id al)
             :dcs/setpoint (:dcs/setpoint al) :dcs/range (:dcs/range tg)})

      (neg? (get al :dcs/deadband 0.0))
      (conj {:dcs/error :negative-deadband :dcs/alarm (:dcs/id al) :dcs/deadband (:dcs/deadband al)}))))

(defn- check-alarm-ordering
  "hi-hi must trip further from normal than hi; lo-lo further than lo (for
  alarms sharing the same tag)."
  [sys]
  (mapcat
   (fn [t]
     (let [by-type (group-by :dcs/type (m/alarms-for-tag sys (:dcs/id t)))
           hi       (first (:hi by-type))
           hi-hi    (first (:hi-hi by-type))
           lo       (first (:lo by-type))
           lo-lo    (first (:lo-lo by-type))]
       (cond-> []
         (and hi hi-hi (>= (:dcs/setpoint hi) (:dcs/setpoint hi-hi)))
         (conj {:dcs/error :alarm-ordering :dcs/tag (:dcs/id t)
                :dcs/hi (:dcs/id hi) :dcs/hi-hi (:dcs/id hi-hi)})

         (and lo lo-lo (<= (:dcs/setpoint lo) (:dcs/setpoint lo-lo)))
         (conj {:dcs/error :alarm-ordering :dcs/tag (:dcs/id t)
                :dcs/lo (:dcs/id lo) :dcs/lo-lo (:dcs/id lo-lo)}))))
   (m/tags sys)))

(defn validate
  "All structural problems in `sys`, as a vector (empty if none)."
  [sys]
  (vec (concat (mapcat #(check-loop sys %) (m/loops sys))
               (mapcat #(check-alarm sys %) (m/alarms sys))
               (check-alarm-ordering sys))))

(defn valid?
  [sys]
  (empty? (validate sys)))

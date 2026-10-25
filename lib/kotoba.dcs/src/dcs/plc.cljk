(ns dcs.plc
  "A persistent, background scan-cycle SERVICE — literally `dcs.execute/scan`
  (the pure scan-cycle engine that already IS the core of what a PLC does:
  execute control logic against I/O on a fixed cycle) run continuously on a
  fixed period against a real `dcs.ports/IFieldIO`, instead of the single
  offline pass `dcs.runner` does. JVM only (.clj), like `dcs.runner` and
  `dcs.modbus` — a background thread is host-side infrastructure, not
  portable domain logic.

  This is what makes `dcs.gpio`/`dcs.modbus`/`dcs.opcua` a simulated *PLC*
  and not just a static data server sitting in front of a snapshot: a real
  external client (a Modbus master, an OPC-UA client, ...) polling the SAME
  tag registry this service is scanning sees values that are actually
  changing, cycle over cycle, because the PID/alarm logic is actually
  executing — not a frozen fixture. As with the rest of this
  protocol-simulation layer, this is entirely software: no real fieldbus,
  no real scan-cycle hardware watchdog, nothing beyond a JVM
  ScheduledExecutorService ticking `dcs.execute/scan`."
  (:require [dcs.execute :as execute])
  (:import
   (java.util.concurrent Executors ScheduledExecutorService TimeUnit ThreadFactory)))

(defn- daemon-thread-factory ^ThreadFactory [name-prefix]
  (let [counter (atom 0)]
    (reify ThreadFactory
      (newThread [_this r]
        (doto (Thread. r (str name-prefix "-" (swap! counter inc)))
          (.setDaemon true))))))

(defn start!
  "Start a persistent scan-cycle service: `dcs.execute/scan` re-run every
  `dt` seconds against `system`/`io`, forever, until `stop!` is called.

  opts:
    :dt        cycle period in seconds (default 1.0) — also passed to
               `scan` as the elapsed-time argument, so the PID's integral
               term and derivative term track real wall-clock cadence.
    :on-cycle  optional (fn [{:dcs/keys [cycle state events]}]) called
               after every scan cycle (e.g. to log alarm events, or drive a
               test assertion) — exceptions from this callback are caught
               and swallowed so a bad callback never kills the scan thread.
    :on-error  optional (fn [ex]) called if `dcs.execute/scan` itself
               throws; the service keeps running on the next tick either
               way (a real PLC scan cycle does not permanently die because
               one cycle faulted).

  Returns a handle map: {:dcs/state (atom, current dcs.execute scan-loop
  state) :dcs/cycle-count (atom, long) :dcs/executor ...}. Pass the handle
  to `stop!`. `(:dcs/state handle)` / `(:dcs/cycle-count handle)` are safe
  to `deref` from any thread while the service is running — this is how an
  external protocol server (e.g. `dcs.modbus`) proves it is reading a live,
  moving state rather than a static snapshot."
  ([system io] (start! system io {}))
  ([system io {:keys [dt on-cycle on-error] :or {dt 1.0}}]
   (let [state-atom (atom (execute/init-state))
         cycle-count (atom 0)
         ^ScheduledExecutorService executor
         (Executors/newSingleThreadScheduledExecutor (daemon-thread-factory "dcs-plc-scan"))
         tick (fn []
                (try
                  (let [{:dcs/keys [state' events]} (execute/scan system @state-atom io dt)]
                    (reset! state-atom state')
                    (swap! cycle-count inc)
                    (when on-cycle
                      (try
                        (on-cycle {:dcs/cycle @cycle-count :dcs/state state' :dcs/events events})
                        (catch Throwable _ignored nil))))
                  (catch Throwable ex
                    (when on-error
                      (try (on-error ex) (catch Throwable _ignored nil))))))]
     (.scheduleAtFixedRate executor tick 0 (long (* dt 1000)) TimeUnit/MILLISECONDS)
     {:dcs/system system
      :dcs/io io
      :dcs/dt dt
      :dcs/state state-atom
      :dcs/cycle-count cycle-count
      :dcs/executor executor})))

(defn stop!
  "Stop a scan service started by `start!`. Waits up to `timeout-ms`
  (default 2000) for the in-flight cycle (if any) to finish before
  returning; does not interrupt a running scan mid-cycle."
  ([handle] (stop! handle 2000))
  ([{:dcs/keys [^ScheduledExecutorService executor]} timeout-ms]
   (.shutdown executor)
   (.awaitTermination executor (long timeout-ms) TimeUnit/MILLISECONDS)
   nil))

(defn running?
  [{:dcs/keys [^ScheduledExecutorService executor]}]
  (not (.isShutdown executor)))

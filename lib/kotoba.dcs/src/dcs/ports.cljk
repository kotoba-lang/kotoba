(ns dcs.ports
  "Host-injected field I/O for running a DCS scan cycle. dcs-clj defines the
  protocol only; the host supplies concrete implementations (a real fieldbus
  driver, an OPC UA client, a process simulator, a test double). The scan
  engine in `dcs.execute` is pure over this protocol — no I/O of its own.")

(defprotocol IFieldIO
  "Read/write process I/O tags by id."
  (read-tag [this tag-id]
    "Return the current value of tag-id, or nil if unavailable.")
  (write-tag! [this tag-id value]
    "Write value to tag-id. Return value is ignored."))

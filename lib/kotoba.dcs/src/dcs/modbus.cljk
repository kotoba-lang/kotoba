(ns dcs.modbus
  "A SIMULATED Modbus TCP server over `dcs.ports/IFieldIO`. JVM only (.clj,
  like `dcs.runner`) — this is a host-side transport, not portable domain
  logic.

  ** SIMULATOR ONLY — loopback (127.0.0.1) by default, and this namespace
  refuses to bind anything else. There is no real serial line, no real
  field device, and nothing here is intended to ever reach real equipment.
  See the README's \"Protocol-simulation layer\" section. **

  Unlike `dcs.gpio` (a thin in-process addressing model with no real
  transport), this IS a real Modbus TCP wire server: MBAP framing, function
  codes 03 (read holding registers) / 04 (read input registers) / 06 (write
  single register) / 16 (write multiple registers). A genuine, unmodified
  Modbus TCP client — any language, any tool — can connect to it over a real
  TCP socket and it behaves indistinguishably, at the protocol level, from
  talking to real equipment.

  The wire protocol itself (MBAP header parsing/framing, PDU
  encode/decode, TCP transport) is NOT reimplemented here — it is supplied
  by `com.digitalpetri.modbus` (Kevin Herron, github.com/digitalpetri/modbus,
  EPL-2.0), a real, independently-authored, actively-maintained Modbus-for-
  Java library (the same author as Eclipse Milo). dcs.modbus supplies only
  the `ModbusServices` callback that maps a register address to a
  `dcs.ports/IFieldIO` tag — i.e. the domain-specific part, not the wire
  format. This is the deliberate 'use the real library, don't reinvent the
  wheel' path (see also the OPC-UA feasibility note in dcs.opcua).

  ## Register map

  A register map is plain data, address-keyed for O(1) lookup, in the same
  style as `dcs.model` / `dcs.gpio`:

    {:dcs/holding {0 {:dcs/register 0 :dcs/tag \"FAN.SP\"
                       :dcs/encoding {:dcs/kind :scaled-int16 :dcs/scale 1.0 :dcs/signed? false}
                       :dcs/access :read-write}}
     :dcs/input   {0 {:dcs/register 0 :dcs/tag \"COV.PV\"
                       :dcs/encoding {:dcs/kind :scaled-int16 :dcs/scale 1000 :dcs/signed? false}}}}

  `:dcs/holding` registers are readable via function code 03 and (only when
  `:dcs/access :read-write`) writable via 06/16; a `:read-only` holding
  register still answers reads but rejects writes with the real Modbus
  ILLEGAL_FUNCTION exception. `:dcs/input` registers are readable via
  function code 04 and are read-only by construction — real Modbus has no
  'write input register' function code, so this simulator enforces nothing
  extra there; the protocol itself is the enforcement.

  Real Modbus registers are 16-bit words, but this library's domain values
  (`dcs.model` tags) are floats/percentages/engineering units — every
  register needs an explicit `:dcs/encoding` documenting the scaling. The
  one encoding this namespace ships is `:scaled-int16`: `word = round(value
  * scale)`, clamped to the representable 16-bit range (signed
  -32768..32767, or unsigned 0..65535 per `:dcs/signed?`), and the inverse on
  read/decode. e.g. a CoV (coefficient of variation, a small fraction like
  0.032) at `:dcs/scale 1000 :dcs/signed? false` reads back as the integer
  register value 32 — the exact 'CoV x 1000' convention real-world Modbus
  integrations use for sub-unity process values on 16-bit registers.
  `:bool16` (word 0 or 1) is provided for digital/alarm-style registers."
  (:require [dcs.ports :as ports])
  (:import
   (com.digitalpetri.modbus ExceptionCode FunctionCode)
   (com.digitalpetri.modbus.exceptions ModbusResponseException)
   (com.digitalpetri.modbus.pdu
    ReadHoldingRegistersResponse
    ReadInputRegistersResponse
    WriteSingleRegisterResponse
    WriteMultipleRegistersResponse)
   (com.digitalpetri.modbus.server ModbusServices ModbusTcpServer)
   (com.digitalpetri.modbus.tcp.server NettyTcpServerTransport)
   (java.nio ByteBuffer)
   (java.util.function Consumer)))

(def default-port
  "Default bind port. Deliberately NOT the real Modbus default 502 — this
  makes 'this is a simulator, not production infrastructure' obvious and
  avoids any accidental collision with a genuine local Modbus service."
  15020)

(def ^:private allowed-hosts
  "Loopback-only allowlist. dcs.modbus refuses to bind anything else."
  #{"127.0.0.1" "localhost" "::1"})

;; --- register map builder (threadable, mirrors dcs.model / dcs.gpio) ---

(defn register-map
  "A fresh, empty register map."
  []
  {:dcs/holding {} :dcs/input {}})

(defn scaled-int16
  "A :scaled-int16 encoding: word = round(value * scale), signed 16-bit by
  default (`signed?` false for a word meant to be read as 0..65535)."
  ([scale] (scaled-int16 scale true))
  ([scale signed?] {:dcs/kind :scaled-int16 :dcs/scale scale :dcs/signed? signed?}))

(def bool16
  "A :bool16 encoding: word 0 (false) or 1 (true)."
  {:dcs/kind :bool16})

(defn holding-register
  "A bare holding-register map (to be attached via `add-holding`). `access`
  is :read-only or :read-write."
  [addr tag-id encoding access]
  {:dcs/register addr :dcs/tag tag-id :dcs/encoding encoding :dcs/access access})

(defn input-register
  "A bare input-register map (to be attached via `add-input`). Always
  read-only — real Modbus has no write-input-register function code."
  [addr tag-id encoding]
  {:dcs/register addr :dcs/tag tag-id :dcs/encoding encoding})

(defn add-holding [rm reg] (assoc-in rm [:dcs/holding (:dcs/register reg)] reg))
(defn add-input   [rm reg] (assoc-in rm [:dcs/input (:dcs/register reg)] reg))

;; --- encode/decode: domain value <-> 16-bit register word ---

(defn- clamp-word [signed? v]
  (let [[lo hi] (if signed? [-32768 32767] [0 65535])]
    (long (max lo (min hi v)))))

(defn encode-register
  "Domain value -> unsigned 16-bit register word (0..65535, ready for
  `.putShort` via `unchecked-short`)."
  [{:dcs/keys [kind scale signed?] :or {scale 1 signed? true}} value]
  (case kind
    :bool16 (if value 1 0)
    :scaled-int16
    (let [raw (Math/round (* (double (or value 0.0)) (double scale)))]
      (bit-and (clamp-word signed? raw) 0xFFFF))
    (throw (ex-info "unknown dcs.modbus register encoding" {:dcs/kind kind}))))

(defn decode-register
  "Unsigned 16-bit register word (0..65535, as read off the wire) -> domain
  value."
  [{:dcs/keys [kind scale signed?] :or {scale 1 signed? true}} word]
  (case kind
    :bool16 (not (zero? word))
    :scaled-int16
    (let [signed-word (if (and signed? (>= word 32768)) (- word 65536) word)]
      (/ signed-word (double scale)))
    (throw (ex-info "unknown dcs.modbus register encoding" {:dcs/kind kind}))))

;; --- ModbusServices: the domain-specific part (register <-> tag) ---

(defn- illegal-address [function-code]
  (ModbusResponseException. ^FunctionCode function-code ExceptionCode/ILLEGAL_DATA_ADDRESS))

(defn- illegal-function [function-code]
  (ModbusResponseException. ^FunctionCode function-code ExceptionCode/ILLEGAL_FUNCTION))

(defn- read-registers [io section address quantity function-code]
  (let [bb (ByteBuffer/allocate (* 2 quantity))]
    (dotimes [i quantity]
      (let [reg (get section (+ address i))]
        (when (nil? reg) (throw (illegal-address function-code)))
        (.putShort bb (unchecked-short (encode-register (:dcs/encoding reg)
                                                          (ports/read-tag io (:dcs/tag reg)))))))
    (.array bb)))

(defn- resolve-writable [section function-code address quantity]
  (mapv (fn [i]
          (let [reg (get section (+ address i))]
            (when (nil? reg) (throw (illegal-address function-code)))
            (when (not= :read-write (:dcs/access reg)) (throw (illegal-function function-code)))
            reg))
        (range quantity)))

(defn modbus-services
  "A ModbusServices implementation (com.digitalpetri.modbus) backed by
  `io` (a dcs.ports/IFieldIO) and `rm` (a register map, see namespace
  docstring). Only readHoldingRegisters / readInputRegisters /
  writeSingleRegister / writeMultipleRegisters are overridden — every other
  Modbus function code (coils, mask-write, read/write-multiple,
  diagnostics, ...) falls through to the library's own interface defaults,
  which correctly return a real ILLEGAL_FUNCTION exception response, exactly
  as an unsupported function code on a real device would. Unit id is
  ignored (this simulates one device)."
  [io rm]
  (reify ModbusServices
    (readHoldingRegisters [_this _ctx _unit-id req]
      (ReadHoldingRegistersResponse.
       (read-registers io (:dcs/holding rm) (.address req) (.quantity req)
                        FunctionCode/READ_HOLDING_REGISTERS)))

    (readInputRegisters [_this _ctx _unit-id req]
      (ReadInputRegistersResponse.
       (read-registers io (:dcs/input rm) (.address req) (.quantity req)
                        FunctionCode/READ_INPUT_REGISTERS)))

    (writeSingleRegister [_this _ctx _unit-id req]
      (let [[reg] (resolve-writable (:dcs/holding rm) FunctionCode/WRITE_SINGLE_REGISTER
                                     (.address req) 1)]
        (ports/write-tag! io (:dcs/tag reg) (decode-register (:dcs/encoding reg) (.value req)))
        (WriteSingleRegisterResponse. (.address req) (.value req))))

    (writeMultipleRegisters [_this _ctx _unit-id req]
      (let [address (.address req)
            quantity (.quantity req)
            regs (resolve-writable (:dcs/holding rm) FunctionCode/WRITE_MULTIPLE_REGISTERS
                                    address quantity)
            bb (ByteBuffer/wrap (.values req))]
        (doseq [reg regs]
          (let [word (bit-and (int (.getShort bb)) 0xFFFF)]
            (ports/write-tag! io (:dcs/tag reg) (decode-register (:dcs/encoding reg) word))))
        (WriteMultipleRegistersResponse. address quantity)))))

;; --- server lifecycle ---

(defn start-server!
  "Start a simulated Modbus TCP server serving `rm` (a register map) over
  `io` (a dcs.ports/IFieldIO). opts: {:host (default \"127.0.0.1\") :port
  (default `default-port`, 15020)}. `:host` MUST be loopback — anything else
  throws (this simulator never binds a real network interface by default,
  and this namespace does not offer a way around that). Returns a handle
  for `stop-server!`."
  ([io rm] (start-server! io rm {}))
  ([io rm {:keys [host port] :or {host "127.0.0.1" port default-port}}]
   (when-not (contains? allowed-hosts host)
     (throw (ex-info "dcs.modbus is a loopback-only simulator; refusing to bind a non-loopback host"
                      {:dcs/host host :dcs/allowed allowed-hosts})))
   (let [transport (NettyTcpServerTransport/create
                     (reify Consumer
                       (accept [_this b]
                         (set! (.bindAddress b) host)
                         (set! (.port b) (int port)))))
         services (modbus-services io rm)
         server (ModbusTcpServer/create transport services)]
     (.start server)
     {:dcs/server server :dcs/transport transport :dcs/host host :dcs/port port})))

(defn stop-server!
  "Stop a server started by `start-server!`."
  [{:dcs/keys [^ModbusTcpServer server]}]
  (.stop server)
  nil)

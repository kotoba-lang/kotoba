(ns kotobase.sftp.transport.sftp-subsystem
  "SFTP-the-subsystem-protocol (draft-ietf-secsh-filexfer, version 3 shape —
  see kotobase.sftp.transport.ssh's docstring for why version 3, and this
  whole repo's README for the 'IETF WG draft, never ratified to an RFC'
  framing): SSH_FXP_* packet encode/decode, and the ONLY namespace that
  translates those opcodes into calls on the pure Phase-1 core,
  `kotobase.sftp.fs`. This namespace knows about SFTP opcodes and
  request-ids; it does NOT know about SSH transport framing, channels, or
  encryption — `kotobase.sftp.transport.ssh` hands it already-decoded SFTP
  packet bytes (the payload of an SSH_MSG_CHANNEL_DATA once the
  'subsystem sftp' request has been accepted) and gets back already-encoded
  SFTP response packet bytes to wrap in the next SSH_MSG_CHANNEL_DATA.

  Implements the packet types the task scope names as 'the most common':
  SSH_FXP_INIT/VERSION (handshake), OPEN/CLOSE/READ/WRITE, OPENDIR/READDIR,
  STAT, REMOVE, RENAME, MKDIR/RMDIR — plus the four response types every
  one of those needs: STATUS/HANDLE/DATA/NAME. Not implemented (out of
  scope, v0.1): LSTAT/FSTAT/FSETSTAT/SETSTAT/READLINK/SYMLINK/EXTENDED, and
  none of SFTPv4+'s ACL/extended-attribute machinery.

  UINT64 NARROWING (documented, not an oversight): SFTP's wire format uses
  uint64 for READ/WRITE `offset` and ATTRS `size`. This namespace only
  reads/writes the LOW 32 bits of those fields (always writing 0 for the
  high 32 bits) — correct for every value this repo's own v0.1 string-body
  files will ever produce, wrong (silently truncating) for a value whose
  true magnitude needs the high bits. This is a real, self-imposed limit,
  not a general-purpose 64-bit SFTP implementation.

  ATTRS NARROWING: only the SSH_FILEXFER_ATTR_SIZE bit (0x00000001) is ever
  produced or consulted; permissions/uid-gid/times are never encoded,
  matching kotobase.sftp.fs's own explicit 'no POSIX permission bits, no
  chmod/chown, no timestamps beyond :mtime' carve-out.

  MULTI-CHUNK WRITE: a WRITE handle accumulates every (offset, bytes) piece
  it receives across possibly-many SSH_FXP_WRITE requests, and only calls
  `kotobase.sftp.fs/write` once — at CLOSE time — with all pieces
  concatenated IN OFFSET-SORTED ORDER. This supports the common real-world
  pattern (a client uploading a file via a sequence of WRITEs at
  increasing offsets) correctly. It does NOT gap-fill (a client that
  writes non-contiguous ranges gets a file that's the naive concatenation
  of what arrived, not a sparse file) — a disclosed v0.1 limitation, not
  silently swept under the rug."
  (:require [kotoba.lang.text :as str]
            [kotobase.sftp.fs :as fs]
            [kotobase.sftp.transport.wire :as w]))

;; ---------------------------------------------------------------------------
;; SFTP opcodes (draft-ietf-secsh-filexfer-02, version 3 — the version every
;; widely-deployed real-world SFTP server/client still actually speaks)
;; ---------------------------------------------------------------------------

(def fxp-init 1)
(def fxp-version 2)
(def fxp-open 3)
(def fxp-close 4)
(def fxp-read 5)
(def fxp-write 6)
(def fxp-opendir 11)
(def fxp-readdir 12)
(def fxp-remove 13)
(def fxp-mkdir 14)
(def fxp-rmdir 15)
(def fxp-stat 17)
(def fxp-rename 18)
(def fxp-status 101)
(def fxp-handle 102)
(def fxp-data 103)
(def fxp-name 104)
(def fxp-attrs 105)

(def sftp-protocol-version 3)

(def fx-ok 0)
(def fx-eof 1)
(def fx-no-such-file 2)
(def fx-permission-denied 3)
(def fx-failure 4)
(def fx-file-already-exists 11)

(def attr-size-flag 0x00000001)

;; ---------------------------------------------------------------------------
;; uint64 (narrowed — see ns docstring)
;; ---------------------------------------------------------------------------

(defn- write-uint64-narrow [n]
  (js/Buffer.concat #js [(w/uint32 0) (w/uint32 (or n 0))]))

(defn- read-uint64-narrow [buf offset]
  ;; skip the (assumed-zero) high 4 bytes, return the low 32 bits + the new offset
  [(w/read-uint32 buf (+ offset 4)) (+ offset 8)])

;; ---------------------------------------------------------------------------
;; SFTP packet framing: uint32 length + type byte + type-specific body.
;; Distinct from (and nested inside) the SSH channel-data framing — see ns
;; docstring.
;; ---------------------------------------------------------------------------

(defn build-sftp-packet [type-byte body-buf]
  (let [inner (js/Buffer.concat #js [(w/ssh-byte type-byte) body-buf])]
    (js/Buffer.concat #js [(w/uint32 (.-length inner)) inner])))

(defn parse-sftp-packet
  "sftp-bytes -> {:type :body} where :body is everything after the type
  byte (request-id onward, or the raw version uint32 for INIT/VERSION).
  Assumes `sftp-bytes` is exactly one complete SFTP packet (this repo
  never splits/coalesces multiple SFTP packets within one
  SSH_MSG_CHANNEL_DATA — see ssh.cljs)."
  [^js sftp-bytes]
  (let [_len (w/read-uint32 sftp-bytes 0)
        type-byte (aget sftp-bytes 4)]
    {:type type-byte :body (.subarray sftp-bytes 5)}))

;; ---------------------------------------------------------------------------
;; Response builders
;; ---------------------------------------------------------------------------

(def ^:private status-messages
  {:kotobase.sftp/no-such-file "No such file"
   :kotobase.sftp/permission-denied "Permission denied"
   :kotobase.sftp/is-a-directory "Is a directory"
   :kotobase.sftp/not-a-directory "Not a directory"
   :kotobase.sftp/file-already-exists "File already exists"
   :kotobase.sftp/directory-not-empty "Directory not empty"
   :kotobase.sftp/invalid-path "Invalid path"})

(def ^:private status-codes
  {:kotobase.sftp/no-such-file fx-no-such-file
   :kotobase.sftp/permission-denied fx-permission-denied
   :kotobase.sftp/is-a-directory fx-failure
   :kotobase.sftp/not-a-directory fx-failure
   :kotobase.sftp/file-already-exists fx-file-already-exists
   :kotobase.sftp/directory-not-empty fx-failure
   :kotobase.sftp/invalid-path fx-failure})

(defn- status-packet
  ([request-id code] (status-packet request-id code "OK"))
  ([request-id code msg]
   (build-sftp-packet fxp-status
                       (js/Buffer.concat #js [(w/uint32 request-id) (w/uint32 code)
                                               (w/ssh-string msg) (w/ssh-string "")]))))

(defn- error-status-packet [request-id error-kw]
  (status-packet request-id
                  (get status-codes error-kw fx-failure)
                  (get status-messages error-kw "Failure")))

(defn- handle-packet [request-id ^js handle-bytes]
  (build-sftp-packet fxp-handle
                      (js/Buffer.concat #js [(w/uint32 request-id) (w/ssh-string handle-bytes)])))

(defn- data-packet [request-id data-str]
  (build-sftp-packet fxp-data
                      (js/Buffer.concat #js [(w/uint32 request-id) (w/ssh-string data-str)])))

(defn- empty-attrs []
  (w/uint32 0))

(defn- size-attrs [size]
  (js/Buffer.concat #js [(w/uint32 attr-size-flag) (write-uint64-narrow size)]))

(defn- attrs-packet [request-id {:keys [type size]}]
  (build-sftp-packet fxp-attrs
                      (js/Buffer.concat #js [(w/uint32 request-id)
                                              (if (= type :file) (size-attrs (or size 0)) (empty-attrs))])))

(defn- name-packet [request-id entries]
  ;; entries: [{:name :longname}], ATTRS always empty (flags=0) — see ns
  ;; docstring's ATTRS NARROWING note.
  (build-sftp-packet
   fxp-name
   (js/Buffer.concat
    (into-array
     (concat [(w/uint32 request-id) (w/uint32 (count entries))]
             (mapcat (fn [{:keys [name longname]}]
                       [(w/ssh-string name) (w/ssh-string (or longname name)) (empty-attrs)])
                     entries))))))

;; ---------------------------------------------------------------------------
;; Session state: the open-handle table. A "handle" here is an opaque byte
;; string (this repo mints simple ASCII counters) mapped server-side to
;; either a read/stat handle ({:kind :file :path}), a write-accumulator
;; handle ({:kind :write :path :pieces (atom [{:offset :bytes} ...])}), or
;; a directory-listing handle ({:kind :dir :entries [...] :sent? bool}).
;; ---------------------------------------------------------------------------

(defn new-session [] (atom {:handles {} :next-id 0}))

(defn- mint-handle! [session-atom state-map]
  (let [id (:next-id @session-atom)
        handle-str (str "h" id)]
    (swap! session-atom (fn [s] (-> s (assoc-in [:handles handle-str] state-map)
                                     (update :next-id inc))))
    handle-str))

;; ---------------------------------------------------------------------------
;; Request dispatch
;; ---------------------------------------------------------------------------

(defn- handle-open [fs-ctx share session-atom request-id body]
  (let [[path-buf off] (w/read-ssh-string body 0)
        path (.toString path-buf "utf8")
        pflags (w/read-uint32 body off)
        write? (pos? (bit-and pflags 0x02)) ;; SSH_FXF_WRITE
        read-only? (not write?)]
    (if read-only?
      (let [{:keys [ok? error]} (fs/open fs-ctx share path)]
        (if ok?
          (handle-packet request-id (js/Buffer.from (mint-handle! session-atom {:kind :file :path path})))
          (error-status-packet request-id error)))
      ;; Write handle: allocated optimistically; the real fs/write
      ;; validation (parent dir must exist, etc.) happens at CLOSE time —
      ;; see ns docstring's MULTI-CHUNK WRITE note for why.
      (handle-packet request-id
                      (js/Buffer.from
                       (mint-handle! session-atom {:kind :write :path path :pieces (atom [])}))))))

(defn- handle-close [fs-ctx share session-atom request-id body]
  (let [[handle-buf _off] (w/read-ssh-string body 0)
        handle-str (.toString handle-buf "utf8")
        state (get-in @session-atom [:handles handle-str])]
    (swap! session-atom update :handles dissoc handle-str)
    (cond
      (nil? state)
      (error-status-packet request-id :kotobase.sftp/no-such-file)

      (= :write (:kind state))
      (let [pieces (sort-by :offset @(:pieces state))
            content (str/join "" (map (fn [{:keys [bytes]}] bytes) pieces))
            {:keys [ok? error]} (fs/write fs-ctx share (:path state) content)]
        (if ok? (status-packet request-id fx-ok) (error-status-packet request-id error)))

      :else
      (status-packet request-id fx-ok))))

(defn- handle-read [fs-ctx share session-atom request-id body]
  (let [[handle-buf off] (w/read-ssh-string body 0)
        handle-str (.toString handle-buf "utf8")
        [offset off] (read-uint64-narrow body off)
        length (w/read-uint32 body off)
        state (get-in @session-atom [:handles handle-str])]
    (if (not= :file (:kind state))
      (error-status-packet request-id :kotobase.sftp/no-such-file)
      (let [{:keys [ok? bytes eof? error]}
            (fs/read-file fs-ctx {:share share :path (:path state)} :offset offset :length length)]
        (cond
          (not ok?) (error-status-packet request-id error)
          (and eof? (zero? (count bytes))) (status-packet request-id fx-eof "EOF")
          :else (data-packet request-id bytes))))))

(defn- handle-write [session-atom request-id body]
  (let [[handle-buf off] (w/read-ssh-string body 0)
        handle-str (.toString handle-buf "utf8")
        [offset off] (read-uint64-narrow body off)
        [data-buf _off] (w/read-ssh-string body off)
        state (get-in @session-atom [:handles handle-str])]
    (if (not= :write (:kind state))
      (error-status-packet request-id :kotobase.sftp/permission-denied)
      (do (swap! (:pieces state) conj {:offset offset :bytes (.toString data-buf "utf8")})
          (status-packet request-id fx-ok)))))

(defn- handle-opendir [fs-ctx share session-atom request-id body]
  (let [[path-buf _off] (w/read-ssh-string body 0)
        path (.toString path-buf "utf8")
        {:keys [ok? entries error]} (fs/readdir fs-ctx share path)]
    (if ok?
      (handle-packet request-id
                      (js/Buffer.from (mint-handle! session-atom {:kind :dir :entries entries :sent? false})))
      (error-status-packet request-id error))))

(defn- handle-readdir [session-atom request-id body]
  (let [[handle-buf _off] (w/read-ssh-string body 0)
        handle-str (.toString handle-buf "utf8")
        state (get-in @session-atom [:handles handle-str])]
    (cond
      (not= :dir (:kind state))
      (error-status-packet request-id :kotobase.sftp/no-such-file)

      (:sent? state)
      (status-packet request-id fx-eof "EOF")

      :else
      (do (swap! session-atom assoc-in [:handles handle-str :sent?] true)
          (if (empty? (:entries state))
            (status-packet request-id fx-eof "EOF")
            (name-packet request-id
                         (map (fn [{:keys [name type]}]
                                {:name name :longname (str name (when (= type :dir) "/"))})
                              (:entries state))))))))

(defn- handle-stat [fs-ctx share request-id body]
  (let [[path-buf _off] (w/read-ssh-string body 0)
        path (.toString path-buf "utf8")
        {:keys [ok? type size error]} (fs/stat fs-ctx share path)]
    (if ok?
      (attrs-packet request-id {:type type :size size})
      (error-status-packet request-id error))))

(defn- handle-remove [fs-ctx share request-id body]
  (let [[path-buf _off] (w/read-ssh-string body 0)
        {:keys [ok? error]} (fs/remove-file fs-ctx share (.toString path-buf "utf8"))]
    (if ok? (status-packet request-id fx-ok) (error-status-packet request-id error))))

(defn- handle-mkdir [fs-ctx share request-id body]
  (let [[path-buf _off] (w/read-ssh-string body 0)
        {:keys [ok? error]} (fs/mkdir fs-ctx share (.toString path-buf "utf8"))]
    (if ok? (status-packet request-id fx-ok) (error-status-packet request-id error))))

(defn- handle-rmdir [fs-ctx share request-id body]
  (let [[path-buf _off] (w/read-ssh-string body 0)
        {:keys [ok? error]} (fs/rmdir fs-ctx share (.toString path-buf "utf8"))]
    (if ok? (status-packet request-id fx-ok) (error-status-packet request-id error))))

(defn- handle-rename [fs-ctx share request-id body]
  (let [[old-buf off] (w/read-ssh-string body 0)
        [new-buf _off] (w/read-ssh-string body off)
        {:keys [ok? error]} (fs/rename fs-ctx share (.toString old-buf "utf8") (.toString new-buf "utf8"))]
    (if ok? (status-packet request-id fx-ok) (error-status-packet request-id error))))

(defn handle-packet-bytes
  "The single entry point ssh.cljs calls with one complete SFTP packet's
  raw bytes (already unwrapped from its SSH_MSG_CHANNEL_DATA envelope).
  `fs-ctx` is `{:store :now}` (kotobase.sftp.fs's ctx shape). Returns the
  raw bytes of the response SFTP packet to send back inside the next
  SSH_MSG_CHANNEL_DATA, or nil for SSH_FXP_INIT's reply special-case
  (handled inline, also returns bytes — nil is never actually returned;
  documented for clarity that every request gets exactly one response,
  matching SFTPv3's synchronous-per-request-id contract this repo relies
  on — it never pipelines multiple in-flight requests differently from
  how they were issued)."
  [fs-ctx share session-atom ^js sftp-bytes]
  (let [{:keys [type body]} (parse-sftp-packet sftp-bytes)]
    (if (= type fxp-init)
      (build-sftp-packet fxp-version (w/uint32 sftp-protocol-version))
      (let [request-id (w/read-uint32 body 0)
            body (.subarray body 4)]
        (cond
          (= type fxp-open) (handle-open fs-ctx share session-atom request-id body)
          (= type fxp-close) (handle-close fs-ctx share session-atom request-id body)
          (= type fxp-read) (handle-read fs-ctx share session-atom request-id body)
          (= type fxp-write) (handle-write session-atom request-id body)
          (= type fxp-opendir) (handle-opendir fs-ctx share session-atom request-id body)
          (= type fxp-readdir) (handle-readdir session-atom request-id body)
          (= type fxp-stat) (handle-stat fs-ctx share request-id body)
          (= type fxp-remove) (handle-remove fs-ctx share request-id body)
          (= type fxp-mkdir) (handle-mkdir fs-ctx share request-id body)
          (= type fxp-rmdir) (handle-rmdir fs-ctx share request-id body)
          (= type fxp-rename) (handle-rename fs-ctx share request-id body)
          :else (status-packet request-id fx-failure "Unsupported SFTP request type (v0.1 subset)"))))))

(ns aiueos.vfio
  "Real raw MMIO/DMA/PCI/IRQ access to a virtio-pci device, via Linux VFIO
  (`vfio-pci`), from ordinary JVM userspace -- ADR-0011's Phase-0 tender-side
  hardware boundary. Same technique DPDK/SPDK/QEMU's own vfio-pci passthrough
  use: bind the target device to `vfio-pci`, open `/dev/vfio/<group>` +
  `/dev/vfio/vfio` (the IOMMU container), get a device fd via
  `VFIO_GROUP_GET_DEVICE_FD`, `mmap` its BAR via `VFIO_DEVICE_GET_REGION_INFO`,
  program DMA via `VFIO_IOMMU_MAP_DMA`, and receive interrupts via
  `VFIO_DEVICE_SET_IRQS` + an eventfd. No native module of our own -- every
  syscall (`open`/`close`/`ioctl`/`mmap`/`munmap`/`eventfd`) goes through
  `java.lang.foreign` (the FFM API, stable since JDK 22 -- this namespace
  needs `JAVA_HOME` pointed at a JDK 22+ toolchain; JDK 21's FFM is preview-only
  and NOT what this targets).

  This produces a `regs` map (`{:read32 (fn [offset]) :write32 (fn [offset
  value])}`) matching the seam `aiueos.virtio`'s MMIO transport functions
  already expect (`aiueos.virtio/mmio-transport`,
  `aiueos.virtio/initialize-mmio-transport`, etc.) -- so the ~85% ported
  protocol logic in `aiueos.virtio` drives REAL hardware through this
  namespace with no change to that logic.

  The DMA side has the same seam and it is worth naming, because only the
  MMIO one was. `iommu-map-dma!` below is the ioctl and nothing else: it
  marshals a `vfio_iommu_type1_dma_map` and hands it to the kernel. What
  decides whether a mapping is ALLOWED is `aiueos.virtio`'s pure model --
  `make-checked-iommu`, `iommu-map-dma`, `iommu-unmap-dma` -- which enforces
  the aperture, rejects overlapping mappings, and requires an exact match to
  unmap. `iova` here is the same guest-physical address that model tracks.
  Whoever wires this to real hardware should route through that model and
  keep this function a mechanism, rather than growing a second set of checks
  here. Neither side has a caller today.

  This is written down because the failure has already happened once in this
  repo: `aiueos.hvt` hand-rolled a descriptor-chain walk instead of using
  `aiueos.virtio/validate-descriptor-chain-with-features`, and the copy was
  missing the index bound, the exact cycle detection, the zero-length check
  and the indirect-flag check. Two implementations of one structure diverge
  in the direction of fewer checks.

  Honesty about what's verified: the ioctl-number encoding and struct-layout
  offset math (the `ioc-*`/`*-layout` functions below) are pure and unit
  tested. The actual `open`/`ioctl`/`mmap` sequence against a live
  `vfio-pci`-bound device is NOT exercised by any test in this repo -- it
  needs a Linux host/guest with IOMMU enabled and a device bound to
  `vfio-pci`, which this sandbox does not have. Treat it as unverified
  systems code until run against real hardware, per ADR-0011's own caveat.

  NOT implemented in this pass: PCI config-space capability walking (VFIO's
  `VFIO_DEVICE_GET_REGION_INFO` gives BAR info directly without needing to
  parse the config-space capability list aiueos.virtio's retired-Rust
  ancestor once had to; `pci-config-read`/`write` below cover the
  `VFIO_PCI_CONFIG_REGION_INDEX` pseudo-BAR only, not full capability
  scanning).")

;; ---------------------------------------------------------------------------
;; ioctl number encoding (Linux `_IO`/_IOR`/`_IOW`/`_IOWR` macros) -- pure,
;; unit-tested without hardware.

(def ^:private ioc-nrbits 8)
(def ^:private ioc-typebits 8)
(def ^:private ioc-sizebits 14)

(def ^:private ioc-nrshift 0)
(def ^:private ioc-typeshift (+ ioc-nrshift ioc-nrbits))
(def ^:private ioc-sizeshift (+ ioc-typeshift ioc-typebits))
(def ^:private ioc-dirshift (+ ioc-sizeshift ioc-sizebits))

(def ^:private ioc-none 0)
(def ^:private ioc-write 1)
(def ^:private ioc-read 2)

(defn ioc
  "Encode a Linux ioctl request number: `_IOC(dir, type, nr, size)`."
  [dir type nr size]
  (bit-or (bit-shift-left dir ioc-dirshift)
          (bit-shift-left type ioc-typeshift)
          (bit-shift-left nr ioc-nrshift)
          (bit-shift-left size ioc-sizeshift)))

(defn io- [type nr] (ioc ioc-none type nr 0))
(defn ior [type nr size] (ioc ioc-read type nr size))
(defn iow [type nr size] (ioc ioc-write type nr size))
(defn iowr [type nr size] (ioc (bit-or ioc-read ioc-write) type nr size))

(def vfio-type
  "`VFIO_TYPE` from linux/vfio.h: the ASCII code of `;`, 59.

  Written as a reader conditional rather than `(int \\;)` because that
  expression is not portable and does not fail when it stops working. On the
  JVM `\\;` is a Character and `int` widens it to 59; on ClojureScript `\\;`
  reads as the one-character STRING \";\" and `int` coerces it to 0 -- so
  every ioctl number below silently lost its type field and became its bare
  `nr`, e.g. `VFIO_GET_API_VERSION` came out 100 instead of 15204. Nothing
  threw: the constants were simply wrong, and only a second runtime showed it."
  #?(:clj (int \;) :cljs (.charCodeAt ";" 0)))

(def vfio-base 100)

(def ioctl-get-api-version (io- vfio-type (+ vfio-base 0)))
(def ioctl-check-extension (io- vfio-type (+ vfio-base 1)))
(def ioctl-set-iommu (io- vfio-type (+ vfio-base 2)))
(def ioctl-group-get-status (io- vfio-type (+ vfio-base 3)))
(def ioctl-group-set-container (io- vfio-type (+ vfio-base 4)))
(def ioctl-group-get-device-fd (io- vfio-type (+ vfio-base 6)))
(def ioctl-device-get-info (io- vfio-type (+ vfio-base 7)))
(def ioctl-device-get-region-info (io- vfio-type (+ vfio-base 8)))
(def ioctl-device-set-irqs-base (io- vfio-type (+ vfio-base 10)))
(def ioctl-iommu-map-dma (io- vfio-type (+ vfio-base 13)))
(def ioctl-iommu-unmap-dma (io- vfio-type (+ vfio-base 14)))

(def vfio-type1-iommu 1)
(def vfio-pci-config-region-index 7)

(def region-info-flag {:read 1 :write 2 :mmap 4 :caps 8})
(def dma-map-flag {:read 1 :write 2})
(def irq-set-flag {:data-eventfd (bit-shift-left 1 2) :action-trigger (bit-shift-left 1 5)})
(def group-status-flag {:viable 1 :container-set 2})

;; ---------------------------------------------------------------------------
;; Struct layouts (byte offsets into the fixed-size prefix of each vfio.h
;; struct this namespace uses) -- pure, unit-tested without hardware.
;; `argsz`/`flags` are always the first two `__u32`s (offsets 0/4) in every
;; vfio.h struct; each layout map below adds the struct-specific fields.

(def group-status-layout {:argsz 0 :flags 4 :size 8})
(def region-info-layout {:argsz 0 :flags 4 :index 8 :cap-offset 12 :size 16 :offset 24 :struct-size 32})
(def dma-map-layout {:argsz 0 :flags 4 :vaddr 8 :iova 16 :size 24 :struct-size 32})
(def dma-unmap-layout {:argsz 0 :flags 4 :iova 8 :size 16 :struct-size 24})
(def irq-set-header-layout {:argsz 0 :flags 4 :index 8 :start 12 :count 16 :header-size 20})

;; ---------------------------------------------------------------------------
;; FFM (java.lang.foreign) libc bindings -- JVM-only, unverified without live
;; VFIO hardware (see namespace docstring).

#?(:clj
   (do

     (import '[java.lang.foreign Arena Linker Linker$Option FunctionDescriptor
               ValueLayout MemoryLayout MemorySegment])

     (def ^:private linker (Linker/nativeLinker))
     (def ^:private lookup (.defaultLookup linker))

     (defn- fdesc
       "`FunctionDescriptor/of` via an explicit `MemoryLayout[]` -- Clojure's
       static-method interop resolution doesn't reliably match the varargs
       overload directly."
       ^FunctionDescriptor [result args]
       (FunctionDescriptor/of result (into-array MemoryLayout args)))

     (def ^:private no-linker-options (make-array Linker$Option 0))

     (defn- lib-fn
       "A `delay` binding libc `name` with the given
       `java.lang.foreign.FunctionDescriptor` -- lazy so merely `require`-ing
       this namespace (e.g. to reach the pure `ioc-*`/`*-layout` functions from
       a JVM that isn't Linux, such as running this repo's test suite on
       macOS) doesn't eagerly fail resolving a Linux-only symbol like
       `eventfd`. Only actually calling a function that needs `name` forces
       the lookup."
       [name ^FunctionDescriptor descriptor]
       (delay
        (.downcallHandle linker
                         (.orElseThrow (.find lookup name)
                                       #(ex-info (str "libc symbol not found: " name) {:name name}))
                         descriptor
                         no-linker-options)))

     (def ^:private c-open
       (lib-fn "open" (fdesc ValueLayout/JAVA_INT [ValueLayout/ADDRESS ValueLayout/JAVA_INT])))
     (def ^:private c-close
       (lib-fn "close" (fdesc ValueLayout/JAVA_INT [ValueLayout/JAVA_INT])))
     (def ^:private c-ioctl-ptr
       (lib-fn "ioctl" (fdesc ValueLayout/JAVA_INT [ValueLayout/JAVA_INT ValueLayout/JAVA_LONG ValueLayout/ADDRESS])))
     (def ^:private c-ioctl-value
       (lib-fn "ioctl" (fdesc ValueLayout/JAVA_INT [ValueLayout/JAVA_INT ValueLayout/JAVA_LONG ValueLayout/JAVA_LONG])))
     (def ^:private c-mmap
       (lib-fn "mmap" (fdesc ValueLayout/ADDRESS [ValueLayout/ADDRESS ValueLayout/JAVA_LONG
                                                   ValueLayout/JAVA_INT ValueLayout/JAVA_INT ValueLayout/JAVA_INT ValueLayout/JAVA_LONG])))
     (def ^:private c-munmap
       (lib-fn "munmap" (fdesc ValueLayout/JAVA_INT [ValueLayout/ADDRESS ValueLayout/JAVA_LONG])))
     (def ^:private c-eventfd
       (lib-fn "eventfd" (fdesc ValueLayout/JAVA_INT [ValueLayout/JAVA_INT ValueLayout/JAVA_INT])))

     (def o-rdwr 2)
     (def prot-read 1)
     (def prot-write 2)
     (def map-shared 1)

     (defn- c-str [^Arena arena s] (.allocateFrom arena ^String s))

     (defn- invoke-h
       "Call a `lib-fn`-produced delay's `MethodHandle` with boxed `args`, via
       `invokeWithArguments` (NOT `invokeExact` -- `invokeExact`'s
       signature-polymorphic dispatch is a javac special case that doesn't
       apply to Clojure's reflective method calls; `invokeWithArguments` is
       the ordinary, reflection-safe entry point and does the same
       boxing/coercion `invokeExact` would via the descriptor)."
       [handle-delay & args]
       (.invokeWithArguments ^java.lang.invoke.MethodHandle @handle-delay
                             ^"[Ljava.lang.Object;" (into-array Object args)))

     (defn vfio-open
       "Open a VFIO node (`\"/dev/vfio/vfio\"` the container, or
       `\"/dev/vfio/<group>\"` a group) O_RDWR. Returns the raw fd (throws on
       failure, matching this namespace's `Result`-as-`ex-info` convention)."
       [^Arena arena path]
       (let [fd (int (invoke-h c-open (c-str arena path) (int o-rdwr)))]
         (when (neg? fd)
           (throw (ex-info (str "open(" path ") failed") {:path path})))
         fd))

     (defn vfio-close [fd] (invoke-h c-close (int fd)) nil)

     (defn- ioctl-int
       "`ioctl(fd, request, &value)` where the argument is a single `__s32`."
       [^Arena arena fd request value]
       (let [seg (.allocate arena ValueLayout/JAVA_INT)]
         (.set ^MemorySegment seg ValueLayout/JAVA_INT 0 (int value))
         (let [rc (int (invoke-h c-ioctl-ptr (int fd) (long request) seg))]
           (when (neg? rc)
             (throw (ex-info "ioctl (int arg) failed" {:fd fd :request request :value value})))
           rc)))

     (defn- ioctl-value
       "Invoke a VFIO ioctl whose third argument is an integer value."
       [fd request value]
       (let [rc (int (invoke-h c-ioctl-value (int fd) (long request) (long value)))]
         (when (neg? rc)
           (throw (ex-info "ioctl (value arg) failed"
                           {:fd fd :request request :value value})))
         rc))

     (defn- ioctl-struct
       "`ioctl(fd, request, buf)` where `buf` is `size` bytes, pre-populated by
       `init!` (a `(fn [seg])`, may be a no-op); returns the raw `MemorySegment`
       so the caller can read result fields back out."
       [^Arena arena fd request size init!]
       (let [seg (.allocate arena (long size))]
         (when init! (init! seg))
         (let [rc (int (invoke-h c-ioctl-ptr (int fd) (long request) seg))]
           (when (neg? rc)
             (throw (ex-info "ioctl (struct arg) failed" {:fd fd :request request})))
           seg)))

     (defn- ioctl-str-arg
       "`ioctl(fd, request, name)` where the arg is a NUL-terminated string
       pointer (only `VFIO_GROUP_GET_DEVICE_FD` uses this shape)."
       [^Arena arena fd request name]
       (let [rc (int (invoke-h c-ioctl-ptr (int fd) (long request) (c-str arena name)))]
         (when (neg? rc)
           (throw (ex-info (str "ioctl(GET_DEVICE_FD, " name ") failed") {:name name})))
         rc))

     (defn- seg-get-i32 [seg offset] (.get ^MemorySegment seg ValueLayout/JAVA_INT (long offset)))
     (defn- seg-set-i32 [seg offset v] (.set ^MemorySegment seg ValueLayout/JAVA_INT (long offset) (int v)))
     (defn- seg-get-i64 [seg offset] (.get ^MemorySegment seg ValueLayout/JAVA_LONG (long offset)))
     (defn- seg-set-i64 [seg offset v] (.set ^MemorySegment seg ValueLayout/JAVA_LONG (long offset) (long v)))

     (defn open-container
       "Open `/dev/vfio/vfio`, verify the API version and TYPE1 IOMMU
       extension. Returns the container fd."
       [^Arena arena]
       (let [fd (vfio-open arena "/dev/vfio/vfio")
             version (int (invoke-h c-ioctl-ptr (int fd) (long ioctl-get-api-version) MemorySegment/NULL))]
         (when (neg? version)
           (throw (ex-info "VFIO_GET_API_VERSION failed" {})))
         (when (zero? (ioctl-value fd ioctl-check-extension vfio-type1-iommu))
           (vfio-close fd)
           (throw (ex-info "VFIO TYPE1 IOMMU extension is unavailable" {})))
         fd))

     (defn open-group
       "Open `/dev/vfio/<group-id>`, verify it's VIABLE (every device in the
       group is bound to `vfio-pci` -- VFIO refuses to hand out access
       otherwise, since an unbound sibling device could still be driven by
       the host kernel), join it to `container-fd`, and set the TYPE1 IOMMU.
       Returns the group fd."
       [^Arena arena group-id container-fd]
       (let [fd (vfio-open arena (str "/dev/vfio/" group-id))
             status-seg (ioctl-struct arena fd ioctl-group-get-status (:size group-status-layout) nil)
             flags (seg-get-i32 status-seg (:flags group-status-layout))]
         (when (zero? (bit-and flags (:viable group-status-flag)))
           (throw (ex-info (str "VFIO group " group-id " is not viable -- not every device in it is bound to vfio-pci")
                            {:group-id group-id :flags flags})))
         (ioctl-int arena fd ioctl-group-set-container container-fd)
         (ioctl-value container-fd ioctl-set-iommu vfio-type1-iommu)
         fd))

     (defn get-device-fd
       "`device-name` is the PCI BDF vfio-pci was bound under (e.g.
       `\"0000:00:04.0\"`)."
       [^Arena arena group-fd device-name]
       (ioctl-str-arg arena group-fd ioctl-group-get-device-fd device-name))

     (defn region-info
       "Query `VFIO_DEVICE_GET_REGION_INFO` for BAR `index` (0-5, or
       `vfio-pci-config-region-index` for config space). Returns
       `{:size :offset :flags}` -- `:offset` is the byte offset into
       `device-fd` to `mmap` for this region."
       [^Arena arena device-fd index]
       (let [seg (ioctl-struct arena device-fd ioctl-device-get-region-info (:struct-size region-info-layout)
                               (fn [s]
                                 (seg-set-i32 s (:argsz region-info-layout) (:struct-size region-info-layout))
                                 (seg-set-i32 s (:index region-info-layout) index)))]
         {:size (seg-get-i64 seg (:size region-info-layout))
          :offset (seg-get-i64 seg (:offset region-info-layout))
          :flags (seg-get-i32 seg (:flags region-info-layout))}))

     (defn mmap-region
       "`mmap` `size` bytes of `device-fd` at `mmap-offset` (from `region-info`).
       Returns a `MemorySegment` over the mapped window (lifetime = `arena`)."
       [^Arena arena device-fd size mmap-offset]
       (let [addr (invoke-h c-mmap MemorySegment/NULL (long size)
                            (int (bit-or prot-read prot-write)) (int map-shared)
                            (int device-fd) (long mmap-offset))]
         (when (= -1 (.address ^MemorySegment addr))
           (throw (ex-info "mmap VFIO region failed"
                           {:device-fd device-fd :size size :offset mmap-offset})))
         (.reinterpret ^MemorySegment addr arena size)))

     (defn unmap-region!
       "`munmap` a window previously returned by `mmap-region` (component
       teardown -- ADR-0011's tender is expected to unmap on capability
       revocation/component exit, not leave BARs mapped for the process
       lifetime)."
       [^MemorySegment seg size]
       (let [rc (int (invoke-h c-munmap seg (long size)))]
         (when (neg? rc)
           (throw (ex-info "munmap failed" {:size size})))
         nil))

     (defn mmio-regs
       "Build the `{:read32 :write32}` map `aiueos.virtio`'s MMIO transport
       functions expect, backed by a real `mmap`-ed BAR window `seg`."
       [^MemorySegment seg]
       {:read32 (fn [offset] (bit-and (long (seg-get-i32 seg offset)) 0xffffffff))
        :write32 (fn [offset value] (seg-set-i32 seg offset value))})

     (defn iommu-map-dma!
       "`VFIO_IOMMU_MAP_DMA`: map process-virtual `vaddr`..`vaddr+size` (host
       memory, typically obtained from a separate anonymous `mmap` the tender
       owns) into the device's IOVA space at `iova` (== the guest-physical
       address `aiueos.virtio`'s DMA model tracks)."
       [^Arena arena container-fd vaddr iova size perms]
       (ioctl-struct arena container-fd ioctl-iommu-map-dma (:struct-size dma-map-layout)
                     (fn [s]
                       (seg-set-i32 s (:argsz dma-map-layout) (:struct-size dma-map-layout))
                       (seg-set-i32 s (:flags dma-map-layout) perms)
                       (seg-set-i64 s (:vaddr dma-map-layout) vaddr)
                       (seg-set-i64 s (:iova dma-map-layout) iova)
                       (seg-set-i64 s (:size dma-map-layout) size)))
       nil)

     (defn iommu-unmap-dma!
       [^Arena arena container-fd iova size]
       (ioctl-struct arena container-fd ioctl-iommu-unmap-dma (:struct-size dma-unmap-layout)
                     (fn [s]
                       (seg-set-i32 s (:argsz dma-unmap-layout) (:struct-size dma-unmap-layout))
                       (seg-set-i64 s (:iova dma-unmap-layout) iova)
                       (seg-set-i64 s (:size dma-unmap-layout) size)))
       nil)

     (defn make-irq-eventfd
       "`eventfd(0, 0)` -- the fd the kernel will `write()` a counter to on
       each virtio interrupt once wired via `subscribe-irq!`."
       []
       (let [fd (int (invoke-h c-eventfd (int 0) (int 0)))]
         (when (neg? fd)
           (throw (ex-info "eventfd(2) failed" {})))
         fd))

     (defn subscribe-irq!
       "`VFIO_DEVICE_SET_IRQS`: wire `eventfd-fd` to fire on device IRQ `index`
       (single-vector, `start=0 count=1`, `DATA_EVENTFD | ACTION_TRIGGER`)."
       [^Arena arena device-fd index eventfd-fd]
       (let [header (:header-size irq-set-header-layout)
             total (+ header 4)
             request ioctl-device-set-irqs-base]
         (ioctl-struct arena device-fd request total
                       (fn [s]
                         (seg-set-i32 s (:argsz irq-set-header-layout) total)
                         (seg-set-i32 s (:flags irq-set-header-layout)
                                      (bit-or (:data-eventfd irq-set-flag) (:action-trigger irq-set-flag)))
                         (seg-set-i32 s (:index irq-set-header-layout) index)
                         (seg-set-i32 s (:start irq-set-header-layout) 0)
                         (seg-set-i32 s (:count irq-set-header-layout) 1)
                         (seg-set-i32 s header eventfd-fd))))
       nil)

     (defn pci-config-region-info
       "`region-info` for the `VFIO_PCI_CONFIG_REGION_INDEX` pseudo-BAR -- read
       via ordinary `pread`-style offsetted `mmap`/reads, not the live
       register semantics `mmio-regs` models (config space doesn't need
       volatile access; a plain byte read/write through the mapped segment is
       enough, matching how the OS itself treats PCI config space)."
       [^Arena arena device-fd]
       (region-info arena device-fd vfio-pci-config-region-index))))

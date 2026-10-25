(ns dicom.dictionary
  "A tag -> VR lookup, for decoding Implicit VR Little Endian
  (`1.2.840.10008.1.2`) data elements.

  This is the trap in Implicit VR that Explicit VR doesn't have: an
  implicit-VR element carries **no VR on the wire at all** — just
  `tag(4) + length(4) + value`. The only way to know whether a given
  element's bytes are an `SQ` (recurse into items), a `US` (an unsigned
  short), or a `PN` (a padded text name) is to already know the standard
  data dictionary's answer for that tag (PS3.6). A decoder that guesses
  from the byte pattern instead of the dictionary will occasionally guess
  right and occasionally silently corrupt data — which is worse than
  refusing.

  **This module ships a small, hand-picked subset of PS3.6** — the tags
  this library's own file-meta/dataset logic and test fixtures need,
  spanning enough different VRs (string, numeric, sequence, binary) to
  exercise every code path. It is not, and does not attempt to be, the
  full PS3.6 registry (thousands of entries). The full registry is
  published as part of the freely-available DICOM standard and a licensee
  is welcome to build a larger table from it; this library's contract is
  the *lookup protocol* — `resolve-vr` takes an overridable dictionary map
  and falls back to `:UN` exactly the way PS3.5 §6.2.2 specifies for an
  unrecognised tag — not the exhaustiveness of the shipped table.

  > \"If the VR of a data element is not known, ... Unknown (UN) ...
  > shall be used.\" — PS3.5 §6.2.2, on VR-less transfer syntaxes and
  > private/unrecognised tags.")

(def base-dictionary
  "tag-map -> VR keyword, for the tags this library itself needs to
  recognise. group/element are decimal here for readability; compare
  against a DICOM data dictionary reference (PS3.6 Table 6-1) by
  converting to hex, e.g. group 8 = 0x0008."
  {{:group 0x0008 :element 0x0005} :CS    ; Specific Character Set
   {:group 0x0008 :element 0x0008} :CS    ; Image Type
   {:group 0x0008 :element 0x0016} :UI    ; SOP Class UID
   {:group 0x0008 :element 0x0018} :UI    ; SOP Instance UID
   {:group 0x0008 :element 0x0020} :DA    ; Study Date
   {:group 0x0008 :element 0x0030} :TM    ; Study Time
   {:group 0x0008 :element 0x0050} :SH    ; Accession Number
   {:group 0x0008 :element 0x0060} :CS    ; Modality
   {:group 0x0008 :element 0x0090} :PN    ; Referring Physician's Name
   {:group 0x0008 :element 0x1030} :LO    ; Study Description
   {:group 0x0008 :element 0x1090} :LO    ; Manufacturer's Model Name
   {:group 0x0010 :element 0x0010} :PN    ; Patient's Name
   {:group 0x0010 :element 0x0020} :LO    ; Patient ID
   {:group 0x0010 :element 0x0030} :DA    ; Patient's Birth Date
   {:group 0x0010 :element 0x0040} :CS    ; Patient's Sex
   {:group 0x0010 :element 0x1010} :AS    ; Patient's Age
   {:group 0x0010 :element 0x1030} :DS    ; Patient's Weight
   {:group 0x0018 :element 0x0050} :DS    ; Slice Thickness
   {:group 0x0018 :element 0x0060} :DS    ; KVP
   {:group 0x0018 :element 0x1000} :LO    ; Device Serial Number
   {:group 0x0018 :element 0x1020} :LO    ; Software Versions
   {:group 0x0020 :element 0x000D} :UI    ; Study Instance UID
   {:group 0x0020 :element 0x000E} :UI    ; Series Instance UID
   {:group 0x0020 :element 0x0010} :SH    ; Study ID
   {:group 0x0020 :element 0x0011} :IS    ; Series Number
   {:group 0x0020 :element 0x0013} :IS    ; Instance Number
   {:group 0x0020 :element 0x0032} :DS    ; Image Position (Patient)
   {:group 0x0020 :element 0x0037} :DS    ; Image Orientation (Patient)
   {:group 0x0020 :element 0x1041} :DS    ; Slice Location
   {:group 0x0028 :element 0x0002} :US    ; Samples per Pixel
   {:group 0x0028 :element 0x0004} :CS    ; Photometric Interpretation
   {:group 0x0028 :element 0x0010} :US    ; Rows
   {:group 0x0028 :element 0x0011} :US    ; Columns
   {:group 0x0028 :element 0x0030} :DS    ; Pixel Spacing
   {:group 0x0028 :element 0x0100} :US    ; Bits Allocated
   {:group 0x0028 :element 0x0101} :US    ; Bits Stored
   {:group 0x0028 :element 0x0102} :US    ; High Bit
   {:group 0x0028 :element 0x0103} :US    ; Pixel Representation
   {:group 0x0028 :element 0x1050} :DS    ; Window Center
   {:group 0x0028 :element 0x1051} :DS    ; Window Width
   {:group 0x0028 :element 0x1052} :DS    ; Rescale Intercept
   {:group 0x0028 :element 0x1053} :DS    ; Rescale Slope
   {:group 0x0032 :element 0x1064} :SQ    ; Requested Procedure Code Sequence
   {:group 0x0040 :element 0x0100} :SQ    ; Scheduled Procedure Step Sequence
   {:group 0x0040 :element 0xA170} :SQ    ; Purpose of Reference Code Sequence
   {:group 0x0054 :element 0x0016} :SQ    ; Radiopharmaceutical Information Sequence
   {:group 0x0070 :element 0x0001} :SQ    ; Graphic Annotation Sequence
   {:group 0x300A :element 0x00B0} :SQ    ; Beam Sequence
   {:group 0x7FE0 :element 0x0010} :OB})  ; Pixel Data (OB or OW; PS3.5 §A.4
                                            ;  says the actual VR depends on
                                            ;  Bits Allocated — a real
                                            ;  decoder must special-case this
                                            ;  tag rather than trust a static
                                            ;  table; :OB here is only the
                                            ;  dictionary's *default guess*)

(defn resolve-vr
  "VR for `tag` per `dictionary` (defaults to `base-dictionary`), falling
  back to `:UN` for anything not present — the behaviour PS3.5 §6.2.2
  mandates for an unrecognised implicit-VR tag, not a guess this library
  invents. `dictionary` is a caller-suppliable tag-map -> VR map so a
  licensee with the full PS3.6 table can plug it in without forking this
  namespace."
  ([tag] (resolve-vr tag base-dictionary))
  ([tag dictionary] (get dictionary tag :UN)))

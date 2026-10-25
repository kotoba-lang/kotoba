"""Business Application Header (head.001) + CBPR+ business-message envelope.

The BAH is **mandatory for every CBPR+ message** on the SWIFT network — a
bare ``pacs.008`` Document is not a valid business message without it. This
module is the cleanroom head.001 codec plus an envelope that pairs an
``AppHdr`` with its business ``Document`` (the logical "ISO 20022 business
message").

Cleanroom from the open standard: the ``AppHdr`` element grammar
(``Fr`` / ``To`` / ``BizMsgIdr`` / ``MsgDefIdr`` / ``BizSvc`` / ``CreDt``)
and the official namespace ``urn:iso:std:iso:20022:tech:xsd:head.001.001.02``
(the version CBPR+ uses). No proprietary SWIFT SDK.

CBPR+ conformance rule enforced here: ``MsgDefIdr`` in the header MUST equal
the wrapped Document's message definition — :func:`parse_business_message`
raises :class:`~kotoba_iso20022.codec.Iso20022CodecError` on mismatch.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .codec import Iso20022CodecError, urn_for
from .model import BusinessApplicationHeader
from .validate import validate_bic

__all__ = (
    "DEFAULT_BAH_VERSION",
    "build_bah",
    "parse_bah",
    "build_business_message",
    "parse_business_message",
)

DEFAULT_BAH_VERSION = "head.001.001.02"

# Pull the "<msgtype>.<variant>.<version>" id out of an ISO 20022 namespace.
_URN_MSGDEF_RE = re.compile(r"urn:iso:std:iso:20022:tech:xsd:([a-z]+\.\d{3}\.\d{3}\.\d{2})$")


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _sub(parent: ET.Element, ns: str, tag: str, text: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, _q(ns, tag))
    if text is not None:
        el.text = text
    return el


def _text(parent: ET.Element | None, ns: str, path: str) -> str | None:
    if parent is None:
        return None
    el = parent.find("/".join(_q(ns, t) for t in path.split("/")))
    return el.text if el is not None else None


def _strip_decl(xml: str) -> str:
    """Drop a leading ``<?xml …?>`` declaration and surrounding whitespace."""
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml).strip()


def _indent_block(xml: str, prefix: str = "  ") -> str:
    """Indent every line of an XML fragment by ``prefix``."""
    return "\n".join(prefix + line for line in xml.splitlines())


def build_bah(bah: BusinessApplicationHeader, version: str | None = None) -> str:
    """Serialize a standalone ``AppHdr`` (head.001)."""
    ns = urn_for(version or DEFAULT_BAH_VERSION)
    ET.register_namespace("", ns)
    root = _build_apphdr_element(bah, ns)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _build_apphdr_element(bah: BusinessApplicationHeader, ns: str) -> ET.Element:
    root = ET.Element(_q(ns, "AppHdr"))
    fr = _sub(root, ns, "Fr")
    fr_fi = _sub(_sub(fr, ns, "FIId"), ns, "FinInstnId")
    _sub(fr_fi, ns, "BICFI", validate_bic(bah.from_bic))
    to = _sub(root, ns, "To")
    to_fi = _sub(_sub(to, ns, "FIId"), ns, "FinInstnId")
    _sub(to_fi, ns, "BICFI", validate_bic(bah.to_bic))
    _sub(root, ns, "BizMsgIdr", bah.business_message_id)
    _sub(root, ns, "MsgDefIdr", bah.message_definition)
    if bah.business_service:
        _sub(root, ns, "BizSvc", bah.business_service)
    _sub(root, ns, "CreDt", bah.creation_datetime)
    return root


def _parse_apphdr_element(root: ET.Element, ns: str) -> BusinessApplicationHeader:
    from_bic = _text(root, ns, "Fr/FIId/FinInstnId/BICFI")
    to_bic = _text(root, ns, "To/FIId/FinInstnId/BICFI")
    if not from_bic or not to_bic:
        raise Iso20022CodecError("AppHdr missing Fr/To BICFI")
    return BusinessApplicationHeader(
        from_bic=from_bic,
        to_bic=to_bic,
        business_message_id=_text(root, ns, "BizMsgIdr") or "",
        message_definition=_text(root, ns, "MsgDefIdr") or "",
        creation_datetime=_text(root, ns, "CreDt") or "",
        business_service=_text(root, ns, "BizSvc"),
    )


def parse_bah(xml: str, version: str | None = None) -> BusinessApplicationHeader:
    """Parse a standalone ``AppHdr`` (head.001)."""
    ns = urn_for(version or DEFAULT_BAH_VERSION)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise Iso20022CodecError(f"not well-formed XML: {exc}") from exc
    if root.tag != _q(ns, "AppHdr"):
        raise Iso20022CodecError("root is not AppHdr (wrong namespace/version?)")
    return _parse_apphdr_element(root, ns)


def _msgdef_of_document(document_xml: str) -> str:
    """Extract the message definition id from a Document's namespace."""
    try:
        doc = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise Iso20022CodecError(f"document not well-formed XML: {exc}") from exc
    m = re.match(r"\{(.+?)\}Document$", doc.tag)
    if not m:
        raise Iso20022CodecError("payload root is not a namespaced <Document>")
    nm = _URN_MSGDEF_RE.match(m.group(1))
    if not nm:
        raise Iso20022CodecError(f"document namespace is not an ISO 20022 URN: {m.group(1)}")
    return nm.group(1)


def build_business_message(
    bah: BusinessApplicationHeader,
    document_xml: str,
    *,
    version: str | None = None,
    enforce_msgdef_match: bool = True,
) -> str:
    """Pair an ``AppHdr`` with a business ``Document`` into one envelope.

    The two are siblings under an ``<Envelope>`` root (the common transport
    representation of an ISO 20022 business message). With
    ``enforce_msgdef_match`` (default), the BAH ``MsgDefIdr`` must equal the
    Document's actual message definition — the CBPR+ rule.
    """
    if enforce_msgdef_match:
        actual = _msgdef_of_document(document_xml)
        if bah.message_definition != actual:
            raise Iso20022CodecError(
                f"BAH MsgDefIdr {bah.message_definition!r} != document {actual!r} (CBPR+)"
            )
    # Compose from each child's independently-serialized form. Building one
    # mixed-namespace ElementTree would let ElementTree's global default-
    # namespace registration leak the payload namespace onto the bare
    # <Envelope>; string composition keeps each child's xmlns self-contained.
    apphdr_body = _strip_decl(build_bah(bah, version=version))
    doc_body = _strip_decl(document_xml)
    inner = _indent_block(apphdr_body) + "\n" + _indent_block(doc_body)
    return f"<?xml version='1.0' encoding='utf-8'?>\n<Envelope>\n{inner}\n</Envelope>"


def parse_business_message(
    xml: str,
    *,
    version: str | None = None,
    enforce_msgdef_match: bool = True,
) -> tuple[BusinessApplicationHeader, str]:
    """Split an envelope back into (header, document_xml).

    Validates the CBPR+ ``MsgDefIdr`` ↔ Document match unless disabled.
    """
    bah_ns = urn_for(version or DEFAULT_BAH_VERSION)
    try:
        envelope = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise Iso20022CodecError(f"not well-formed XML: {exc}") from exc
    apphdr = envelope.find(_q(bah_ns, "AppHdr"))
    document = next((c for c in envelope if c.tag.endswith("}Document")), None)
    if apphdr is None or document is None:
        raise Iso20022CodecError("envelope must contain AppHdr + Document siblings")
    header = _parse_apphdr_element(apphdr, bah_ns)
    document_xml = ET.tostring(document, encoding="unicode")
    if enforce_msgdef_match:
        actual = _msgdef_of_document(document_xml)
        if header.message_definition != actual:
            raise Iso20022CodecError(
                f"BAH MsgDefIdr {header.message_definition!r} != document {actual!r} (CBPR+)"
            )
    return header, document_xml

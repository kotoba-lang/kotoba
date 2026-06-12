"""OpenPGP E2EE helpers for cross-provider email encryption (RFC 4880).

Supports Gmail, Outlook, Thunderbird, and any RFC-4880-compliant client.
Key storage uses kotoba Datom log; WKD discovery is NOT attempted —
callers must register keys explicitly via register_public_key().
"""

from __future__ import annotations

import time
from typing import Any
from kotodama.kotoba_datomic import get_kotoba_client

import pgpy
from pgpy.constants import (
    CompressionAlgorithm,
    SymmetricKeyAlgorithm,
)


def encrypt(plaintext: str, recipient_pubkey_armored: str) -> str:
    """Encrypt plaintext with recipient's PGP public key.

    Returns ASCII-armored PGP message (inline format, compatible with
    Thunderbird Enigmail, GPG Tools, Kleopatra, and ProtonMail Bridge).
    """
    key, _ = pgpy.PGPKey.from_blob(recipient_pubkey_armored)
    msg = pgpy.PGPMessage.new(plaintext, compression=CompressionAlgorithm.ZIP)
    encrypted = key.encrypt(
        msg,
        cipher=SymmetricKeyAlgorithm.AES256,
    )
    return str(encrypted)


def decrypt(
    ciphertext_armored: str,
    private_key_armored: str,
    passphrase: str | None = None,
) -> str:
    """Decrypt PGP-armored ciphertext with private key. Returns plaintext."""
    privkey, _ = pgpy.PGPKey.from_blob(private_key_armored)
    msg = pgpy.PGPMessage.from_blob(ciphertext_armored)
    if passphrase:
        with privkey.unlock(passphrase):
            decrypted = privkey.decrypt(msg)
    else:
        decrypted = privkey.decrypt(msg)
    return str(decrypted.message)


def lookup_public_key(email: str) -> str | None:
    """Return armored public key for email, or None if not registered."""
    client = get_kotoba_client()
    # R0: Multi-predicate WHERE (revoked = FALSE), ORDER BY, and LIMIT 1 are handled in Python.
    rows = client.select_where(
        "vertex_mailer_pgp_key",
        "email",
        email.lower().strip(),
        columns=["public_key_armored", "revoked", "created_at_ms"]
    )
    if rows:
        # Filter for revoked = FALSE
        active_keys = [row for row in rows if not row.get("revoked")]
        if active_keys:
            # Order by created_at_ms DESC and take the first
            active_keys.sort(key=lambda x: x.get("created_at_ms", 0), reverse=True)
            return str(active_keys[0].get("public_key_armored"))
    return None


def register_public_key(email: str, public_key_armored: str) -> dict[str, Any]:
    """Register (or refresh) a PGP public key for an email address.

    Upserts on (email, fingerprint). Existing revoked keys are un-revoked
    when the same fingerprint is re-registered.
    """
    key, _ = pgpy.PGPKey.from_blob(public_key_armored)
    fingerprint = str(key.fingerprint)
    now_ms = int(time.time() * 1000)
    client = get_kotoba_client()
    client.insert_row(
        "vertex_mailer_pgp_key",
        {
            "email": email.lower().strip(),
            "fingerprint": fingerprint,
            "public_key_armored": public_key_armored,
            "revoked": False,
            "created_at_ms": now_ms,
        },
    )
    return {"email": email, "fingerprint": fingerprint}


def revoke_public_key(email: str, fingerprint: str) -> dict[str, Any]:
    """Mark a registered key as revoked (soft-delete)."""
    client = get_kotoba_client()
    # R0: UPDATE operation is handled by fetching, modifying in Python, and re-inserting.
    # The 'select_where' only supports a single column for the WHERE clause.
    # Therefore, we fetch by email and then filter by fingerprint in Python.
    rows = client.select_where(
        "vertex_mailer_pgp_key",
        "email",
        email.lower().strip(),
        columns=["email", "fingerprint", "public_key_armored", "revoked", "created_at_ms"]
    )
    affected = 0
    for row in rows:
        if row.get("fingerprint") == fingerprint:
            row["revoked"] = True
            client.insert_row("vertex_mailer_pgp_key", row) # Upsert the modified row
            affected += 1
            break # Assuming fingerprint is unique per email, only one row to update

    return {"email": email, "fingerprint": fingerprint, "revoked": affected > 0}


def build_pgp_mime_raw(
    *,
    sender: str,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str | None,
    recipient_pubkey_armored: str,
    reply_to: str = "",
    message_id: str = "",
    extra_headers: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Build a PGP/MIME (RFC 3156) email as a raw RFC 2822 string.

    Returns (raw_mime, message_id).

    Subject is placed only inside the encrypted payload (Protected Headers,
    draft-autocrypt-lamps-protected-headers). Outer Subject is '[Encrypted]',
    matching ProtonMail's external-recipient behaviour. Clients without Protected
    Headers support (Mailvelope, most Outlook plugins) will show '[Encrypted]'
    permanently; Thunderbird/Enigmail and FlowCrypt recover the real subject.
    """
    import email.mime.application
    import email.mime.multipart
    import email.mime.text
    import email.policy
    from email.utils import formatdate, make_msgid

    # Inner MIME entity — will be encrypted
    if html_body:
        inner: Any = email.mime.multipart.MIMEMultipart("alternative")
        inner.attach(email.mime.text.MIMEText(text_body, "plain", "utf-8"))
        inner.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))
    else:
        inner = email.mime.text.MIMEText(text_body, "plain", "utf-8")
    inner["Subject"] = subject  # protected header (recovered by PGP-aware clients)

    # Serialize inner MIME with CRLF before encrypting (RFC 2822 §2.1)
    inner_bytes = inner.as_bytes(policy=email.policy.SMTP)
    encrypted_str = encrypt(inner_bytes.decode("utf-8"), recipient_pubkey_armored)

    msg_id = message_id or make_msgid(
        domain=sender.split("@")[-1] if "@" in sender else "etzhayyim.com"
    )

    # Outer PGP/MIME envelope (RFC 3156 §4)
    outer = email.mime.multipart.MIMEMultipart(
        "encrypted",
        protocol="application/pgp-encrypted",
    )
    outer["From"] = sender
    outer["To"] = to_address
    outer["Subject"] = "[Encrypted]"
    outer["Date"] = formatdate(localtime=False)
    outer["Message-ID"] = msg_id
    if reply_to:
        outer["Reply-To"] = reply_to
    for k, v in (extra_headers or {}).items():
        outer[k] = v

    # RFC 3156 Part 1: version identification
    ver_part = email.mime.application.MIMEApplication(b"Version: 1\n", "pgp-encrypted")
    ver_part.add_header("Content-Disposition", "attachment", filename="version.asc")
    outer.attach(ver_part)

    # RFC 3156 Part 2: encrypted data (ASCII armor)
    enc_part = email.mime.application.MIMEApplication(
        encrypted_str.encode("ascii"), "octet-stream"
    )
    enc_part.add_header("Content-Disposition", "attachment", filename="encrypted.asc")
    outer.attach(enc_part)

    return outer.as_bytes(policy=email.policy.SMTP).decode("ascii"), msg_id

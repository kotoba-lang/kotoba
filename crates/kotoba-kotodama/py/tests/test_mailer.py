from kotodama.ingest import mailer


def test_secret_falls_back_to_keychain(monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("SS_RESEND_API_KEY", raising=False)

    calls: list[tuple[str, str]] = []

    def fake_load_keychain_secret(*, service: str, account: str) -> str:
        calls.append((service, account))
        return "re_keychain"

    monkeypatch.setattr(mailer, "load_keychain_secret", fake_load_keychain_secret)

    assert mailer._secret("RESEND_API_KEY", "SS_RESEND_API_KEY") == "re_keychain"
    assert calls == [("etzhayyim.resend", "API_KEY")]


def test_secret_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_env")

    def fail_load_keychain_secret(*, service: str, account: str) -> str:  # pragma: no cover
        raise AssertionError("env secret must win")

    monkeypatch.setattr(mailer, "load_keychain_secret", fail_load_keychain_secret)

    assert mailer._secret("RESEND_API_KEY") == "re_env"

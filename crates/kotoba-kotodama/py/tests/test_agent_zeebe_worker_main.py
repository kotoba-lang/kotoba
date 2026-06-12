from __future__ import annotations

import asyncio

from kotodama import agent_zeebe_worker_main


def test_task_mailer_send_email_delegates_to_mailer(monkeypatch) -> None:
    def fake_send_email(**kwargs):
        return {"messageId": "msg_test", "provider": "fake", **kwargs}

    monkeypatch.setattr("kotodama.ingest.mailer.send_email", fake_send_email)

    result = asyncio.run(
        agent_zeebe_worker_main.task_mailer_send_email(
            to="ops@example.com",
            subject="Ping",
            text="hello",
            fromAddress="agent@etzhayyim.com",
        )
    )

    assert result["messageId"] == "msg_test"
    assert result["to"] == "ops@example.com"
    assert result["fromAddress"] == "agent@etzhayyim.com"

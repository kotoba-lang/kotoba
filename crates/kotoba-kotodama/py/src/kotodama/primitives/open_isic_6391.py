from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6391_classify(**kwargs: Any) -> dict[str, Any]:
    """News agency activities.

    This class includes the activities of news agencies that provide news and feature articles to newspapers, periodicals, radio and television broadcasters.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6391":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6391."}
    return await task_open_isic_classify_entity(**kwargs)

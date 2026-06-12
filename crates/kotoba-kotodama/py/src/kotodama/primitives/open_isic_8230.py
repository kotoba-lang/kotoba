from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8230_classify(**kwargs: Any) -> dict[str, Any]:
    """Organization of conventions and trade shows

    This class includes the organization, promotion and/or management of events such as business and trade shows, conventions, conferences and meetings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8230":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8230."}
    return await task_open_isic_classify_entity(**kwargs)

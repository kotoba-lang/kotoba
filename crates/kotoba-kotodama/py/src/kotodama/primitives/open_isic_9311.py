from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9311_classify(**kwargs: Any) -> dict[str, Any]:
    """Operation of sports facilities

    This class includes the operation and management of indoor or outdoor sports facilities for water sports, winter sports or other sports activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9311":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9311."}
    return await task_open_isic_classify_entity(**kwargs)

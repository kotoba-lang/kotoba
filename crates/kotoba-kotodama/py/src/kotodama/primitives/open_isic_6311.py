from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6311_classify(**kwargs: Any) -> dict[str, Any]:
    """Data processing, hosting and related activities.

    This class includes the provision of infrastructure for hosting, data processing services and related activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6311":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6311."}
    return await task_open_isic_classify_entity(**kwargs)

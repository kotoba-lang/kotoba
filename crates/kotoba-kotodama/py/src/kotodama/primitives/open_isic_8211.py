from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8211_classify(**kwargs: Any) -> dict[str, Any]:
    """Combined office administrative service activities

    This class includes the provision of a combination of administrative services, such as reception, financial planning, billing and record-keeping, personnel and physical distribution and logistics.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8211":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8211."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8421_classify(**kwargs: Any) -> dict[str, Any]:
    """Foreign affairs

    This class includes activities of the provision of services and administration of foreign affairs.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8421":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8421."}
    return await task_open_isic_classify_entity(**kwargs)

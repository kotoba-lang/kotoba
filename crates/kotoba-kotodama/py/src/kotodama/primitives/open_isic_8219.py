from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8219_classify(**kwargs: Any) -> dict[str, Any]:
    """Photocopying, document preparation and other specialized office support activities

    This class includes photocopying, duplicating, mailing, addressing, mailing list compilation and other specialized office support activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8219":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8219."}
    return await task_open_isic_classify_entity(**kwargs)

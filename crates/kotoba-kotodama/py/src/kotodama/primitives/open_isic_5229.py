from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5229_classify(**kwargs: Any) -> dict[str, Any]:
    """Other transportation support activities

    This class includes transport support activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5229":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5229."}
    return await task_open_isic_classify_entity(**kwargs)

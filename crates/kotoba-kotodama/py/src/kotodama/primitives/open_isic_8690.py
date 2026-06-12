from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8690_classify(**kwargs: Any) -> dict[str, Any]:
    """Other human health activities

    This class includes the provision of health care services not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8690":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8690."}
    return await task_open_isic_classify_entity(**kwargs)

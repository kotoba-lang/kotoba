from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7500_classify(**kwargs: Any) -> dict[str, Any]:
    """Veterinary activities

    This class includes the provision of animal health care and control services for farm animals or pet animals.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7500":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7500."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5914_classify(**kwargs: Any) -> dict[str, Any]:
    """Motion picture projection activities

    This class includes the projection of motion pictures in cinemas.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5914":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5914."}
    return await task_open_isic_classify_entity(**kwargs)

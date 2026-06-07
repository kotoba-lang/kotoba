from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8541_classify(**kwargs: Any) -> dict[str, Any]:
    """Sports and recreation education

    This class includes the provision of instruction in athletic activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8541":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8541."}
    return await task_open_isic_classify_entity(**kwargs)

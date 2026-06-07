from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9321_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of amusement parks and theme parks

    This class includes the operation of amusement parks and theme parks including the operation of a variety of attractions.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9321":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9321."}
    return await task_open_isic_classify_entity(**kwargs)

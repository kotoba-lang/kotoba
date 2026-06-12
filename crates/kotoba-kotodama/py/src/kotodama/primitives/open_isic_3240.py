from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3240_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of games and toys.

    This class includes the manufacture of dolls, toys and games (including electronic games), scale models and children's vehicles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3240":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3240."}
    return await task_open_isic_classify_entity(**kwargs)

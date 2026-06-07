from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4100_classify(**kwargs: Any) -> dict[str, Any]:
    """Construction of buildings.

    This class includes the general construction of all kinds of buildings and structures.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4100":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4100."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7729_classify(**kwargs: Any) -> dict[str, Any]:
    """Renting and leasing of other personal and household goods

    This class includes the renting of personal and household goods n.e.c.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7729":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7729."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2394_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of cement, lime and plaster

    This class includes the manufacture of cement, lime and plaster.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2394":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2394."}
    return await task_open_isic_classify_entity(**kwargs)

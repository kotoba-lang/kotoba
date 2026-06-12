from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0124_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of pome fruits and stone fruits

    This class includes the growing of pome fruits and stone fruits.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0124":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0124."}
    return await task_open_isic_classify_entity(**kwargs)

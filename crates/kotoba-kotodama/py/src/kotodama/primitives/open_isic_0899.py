from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0899_classify(**kwargs: Any) -> dict[str, Any]:
    """Other mining and quarrying n.e.c.

    This class includes mining and quarrying of various minerals and materials not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0899":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0899."}
    return await task_open_isic_classify_entity(**kwargs)

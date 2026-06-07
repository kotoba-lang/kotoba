from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4669_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of other products n.e.c.

    This class includes the wholesale of other products not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4669":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4669."}
    return await task_open_isic_classify_entity(**kwargs)

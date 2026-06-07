from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6399_classify(**kwargs: Any) -> dict[str, Any]:
    """Other information service activities n.e.c..

    This class includes all remaining information service activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6399":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6399."}
    return await task_open_isic_classify_entity(**kwargs)

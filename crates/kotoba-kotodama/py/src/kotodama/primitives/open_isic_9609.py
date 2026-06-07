from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9609_classify(**kwargs: Any) -> dict[str, Any]:
    """Other personal service activities n.e.c.

    This class includes other personal service activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9609":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9609."}
    return await task_open_isic_classify_entity(**kwargs)

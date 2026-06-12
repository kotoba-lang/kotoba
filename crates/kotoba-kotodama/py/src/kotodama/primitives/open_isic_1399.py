from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1399_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other textiles n.e.c.

    This class includes the manufacture of a variety of textile products not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1399":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1399."}
    return await task_open_isic_classify_entity(**kwargs)

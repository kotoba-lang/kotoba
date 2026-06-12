from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2029_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other chemical products n.e.c.

    This class includes the manufacture of a variety of chemical products not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2029":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2029."}
    return await task_open_isic_classify_entity(**kwargs)

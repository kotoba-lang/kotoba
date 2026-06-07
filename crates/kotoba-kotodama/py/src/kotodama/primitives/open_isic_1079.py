from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1079_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other food products n.e.c.

    This class includes the manufacture of a variety of food products not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1079":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1079."}
    return await task_open_isic_classify_entity(**kwargs)

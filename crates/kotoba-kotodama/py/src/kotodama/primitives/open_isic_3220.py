from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3220_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of musical instruments.

    This class includes the manufacture of musical instruments of all kinds.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3220":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3220."}
    return await task_open_isic_classify_entity(**kwargs)

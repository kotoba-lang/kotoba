from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2630_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of communication equipment.

    This class includes the manufacture of telephone and data communications equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2630":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2630."}
    return await task_open_isic_classify_entity(**kwargs)

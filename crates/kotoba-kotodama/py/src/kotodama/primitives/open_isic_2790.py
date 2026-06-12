from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2790_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other electrical equipment.

    This class includes the manufacture of electrical equipment not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2790":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2790."}
    return await task_open_isic_classify_entity(**kwargs)

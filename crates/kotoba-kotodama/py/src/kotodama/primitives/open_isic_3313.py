from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3313_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of electronic and optical equipment.

    This class includes the repair and maintenance of electronic and optical equipment used in industry.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3313":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3313."}
    return await task_open_isic_classify_entity(**kwargs)

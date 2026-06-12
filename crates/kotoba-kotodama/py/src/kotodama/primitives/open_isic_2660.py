from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2660_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of irradiation, electromedical and electrotherapeutic equipment.

    This class includes the manufacture of irradiation, electromedical and electrotherapeutic apparatus and equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2660":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2660."}
    return await task_open_isic_classify_entity(**kwargs)

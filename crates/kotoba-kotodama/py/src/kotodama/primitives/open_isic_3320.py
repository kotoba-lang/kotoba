from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3320_classify(**kwargs: Any) -> dict[str, Any]:
    """Installation of industrial machinery and equipment.

    This class includes the specialised installation of industrial machinery and equipment in industrial plants.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3320":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3320."}
    return await task_open_isic_classify_entity(**kwargs)

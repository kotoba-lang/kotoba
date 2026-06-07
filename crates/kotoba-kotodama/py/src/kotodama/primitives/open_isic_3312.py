from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3312_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of machinery.

    This class includes the repair and maintenance of industrial machinery and equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3312":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3312."}
    return await task_open_isic_classify_entity(**kwargs)

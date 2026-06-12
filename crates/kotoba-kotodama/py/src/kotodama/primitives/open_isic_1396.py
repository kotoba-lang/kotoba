from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1396_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of technical and industrial textiles

    This class includes the manufacture of textile fabrics and articles intended for technical and industrial use.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1396":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1396."}
    return await task_open_isic_classify_entity(**kwargs)

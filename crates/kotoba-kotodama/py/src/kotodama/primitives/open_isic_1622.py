from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1622_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of builders' carpentry and joinery

    This class includes the manufacture of builders' carpentry and joinery products of wood.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1622":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1622."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1621_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of veneer sheets and wood-based panels

    This class includes the manufacture of veneer sheets and wood-based panels such as plywood, particle board, oriented strand board and fibreboard.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1621":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1621."}
    return await task_open_isic_classify_entity(**kwargs)

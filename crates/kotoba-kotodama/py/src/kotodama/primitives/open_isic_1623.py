from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1623_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of wooden containers

    This class includes the manufacture of wooden containers such as boxes, crates, drums, barrels and pallets.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1623":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1623."}
    return await task_open_isic_classify_entity(**kwargs)

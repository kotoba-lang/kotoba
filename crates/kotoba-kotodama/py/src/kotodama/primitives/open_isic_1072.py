from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1072_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of sugar

    This class includes the manufacture of raw sugar, refined sugar, powdered sugar, syrup and molasses from sugar cane, sugar beets, maple sap and other sources.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1072":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1072."}
    return await task_open_isic_classify_entity(**kwargs)

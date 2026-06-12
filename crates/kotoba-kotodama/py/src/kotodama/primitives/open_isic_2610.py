from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2610_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of electronic components and boards.

    This class includes the manufacture of electronic components and printed circuit boards.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2610":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2610."}
    return await task_open_isic_classify_entity(**kwargs)

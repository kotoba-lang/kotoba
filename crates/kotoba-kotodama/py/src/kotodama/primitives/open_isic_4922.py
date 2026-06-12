from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4922_classify(**kwargs: Any) -> dict[str, Any]:
    """Other passenger land transport.

    This class includes passenger transport by road not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4922":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4922."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5590_classify(**kwargs: Any) -> dict[str, Any]:
    """Other accommodation

    This class includes the provision of temporary or longer-term accommodation not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5590":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5590."}
    return await task_open_isic_classify_entity(**kwargs)

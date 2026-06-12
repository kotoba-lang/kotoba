from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1420_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of articles of fur

    This class includes the manufacture of articles made of fur skins.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1420":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1420."}
    return await task_open_isic_classify_entity(**kwargs)

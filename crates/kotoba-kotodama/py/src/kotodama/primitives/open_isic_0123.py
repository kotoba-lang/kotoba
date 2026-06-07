from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0123_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of citrus fruits

    This class includes the growing of citrus fruits.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0123":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0123."}
    return await task_open_isic_classify_entity(**kwargs)

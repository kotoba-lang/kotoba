from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0114_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of sugar cane.

    This class includes the growing of sugar cane.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0114":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0114."}
    return await task_open_isic_classify_entity(**kwargs)

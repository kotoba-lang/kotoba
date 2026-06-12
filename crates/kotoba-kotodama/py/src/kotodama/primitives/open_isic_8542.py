from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8542_classify(**kwargs: Any) -> dict[str, Any]:
    """Cultural education

    This class includes the provision of instruction in the arts, drama and music.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8542":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8542."}
    return await task_open_isic_classify_entity(**kwargs)

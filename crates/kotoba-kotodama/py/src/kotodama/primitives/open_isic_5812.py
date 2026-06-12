from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5812_classify(**kwargs: Any) -> dict[str, Any]:
    """Publishing of directories and mailing lists

    This class includes the publishing of mailing lists and directories of all kinds.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5812":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5812."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9492_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of political organizations

    This class includes the activities of political organizations and auxiliary organizations such as young people's leagues.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9492":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9492."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6492_classify(**kwargs: Any) -> dict[str, Any]:
    """Other credit granting.

    This class includes other financial service activities primarily concerned with making loans by institutions not involved in monetary intermediation.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6492":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6492."}
    return await task_open_isic_classify_entity(**kwargs)

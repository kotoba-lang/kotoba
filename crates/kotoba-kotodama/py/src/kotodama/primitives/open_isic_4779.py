from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4779_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale of second-hand goods.

    This class includes the retail sale of second-hand goods.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4779":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4779."}
    return await task_open_isic_classify_entity(**kwargs)

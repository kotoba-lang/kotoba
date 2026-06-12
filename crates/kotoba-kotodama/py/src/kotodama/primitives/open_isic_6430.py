from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6430_classify(**kwargs: Any) -> dict[str, Any]:
    """Trusts, funds and similar financial entities.

    This class includes legal entities organized to pool securities or other financial assets without managing them on a day-to-day basis.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6430":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6430."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0520_classify(**kwargs: Any) -> dict[str, Any]:
    """Mining of lignite.

    This class includes mining of lignite (brown coal): underground or open-cast mining, cleaning, dewatering, pulverizing, compressing (e.g. briquetting) and other non-agglomeration processes to improve quality or facilitate transport or storage of lignite.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0520":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0520."}
    return await task_open_isic_classify_entity(**kwargs)

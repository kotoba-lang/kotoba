from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7740_classify(**kwargs: Any) -> dict[str, Any]:
    """Leasing of intellectual property and similar products, except copyrighted works

    This class includes the activities of establishing the right to use intellectual property assets such as patents, trademarks, brand names, and franchise agreements.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7740":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7740."}
    return await task_open_isic_classify_entity(**kwargs)

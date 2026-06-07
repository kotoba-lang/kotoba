from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1074_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of macaroni, noodles, couscous and similar farinaceous products

    This class includes the manufacture of pasta products such as macaroni, noodles, couscous and similar farinaceous products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1074":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1074."}
    return await task_open_isic_classify_entity(**kwargs)

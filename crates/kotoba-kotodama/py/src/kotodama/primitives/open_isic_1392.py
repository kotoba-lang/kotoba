from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1392_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of made-up textile articles, except apparel

    This class includes the manufacture of made-up textile articles of any textile material, except apparel.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1392":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1392."}
    return await task_open_isic_classify_entity(**kwargs)

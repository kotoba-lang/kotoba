from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2680_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of magnetic and optical media.

    This class includes the manufacture of magnetic and optical recording media.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2680":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2680."}
    return await task_open_isic_classify_entity(**kwargs)

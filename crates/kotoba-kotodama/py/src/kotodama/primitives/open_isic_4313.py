from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4313_classify(**kwargs: Any) -> dict[str, Any]:
    """Test drilling and boring.

    This class includes test drilling and boring for construction, geophysical, geological or similar purposes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4313":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4313."}
    return await task_open_isic_classify_entity(**kwargs)

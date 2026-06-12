from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9523_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of footwear and leather goods

    This class includes the repair of footwear and leather goods.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9523":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9523."}
    return await task_open_isic_classify_entity(**kwargs)

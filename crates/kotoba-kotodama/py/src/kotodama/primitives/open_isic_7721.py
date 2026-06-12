from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7721_classify(**kwargs: Any) -> dict[str, Any]:
    """Renting and leasing of recreational and sports goods

    This class includes the renting of recreational and sports goods.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7721":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7721."}
    return await task_open_isic_classify_entity(**kwargs)

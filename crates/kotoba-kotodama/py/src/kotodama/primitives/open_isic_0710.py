from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0710_classify(**kwargs: Any) -> dict[str, Any]:
    """Mining of iron ores

    This class includes the extraction and beneficiation of iron ores. Beneficiation includes activities such as dressing, roasting, sintering, and pelletizing of iron ore.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0710":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0710."}
    return await task_open_isic_classify_entity(**kwargs)

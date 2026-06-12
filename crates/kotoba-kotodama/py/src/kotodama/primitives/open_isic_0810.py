from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0810_classify(**kwargs: Any) -> dict[str, Any]:
    """Quarrying of stone, sand and clay

    This class includes the extraction and processing of stone, sand, gravel, clay, and other similar materials used in construction and other industries. It includes quarrying operations and associated beneficiation activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0810":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0810."}
    return await task_open_isic_classify_entity(**kwargs)

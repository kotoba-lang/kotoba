from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6810_classify(**kwargs: Any) -> dict[str, Any]:
    """Real estate activities with own or leased property.

    This class includes buying, selling and renting of own or leased real estate.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6810":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6810."}
    return await task_open_isic_classify_entity(**kwargs)

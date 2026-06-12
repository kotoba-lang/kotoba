from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0210_classify(**kwargs: Any) -> dict[str, Any]:
    """Silviculture and other forestry activities.

    This class includes the growing of standing timber: afforestation, reforestation, planting, replanting, transplanting, thinning and conserving of forests and timber tracts. It also includes the growing of coppice, pulpwood and fuel wood, and the operation of forest tree nurseries.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0210":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0210."}
    return await task_open_isic_classify_entity(**kwargs)

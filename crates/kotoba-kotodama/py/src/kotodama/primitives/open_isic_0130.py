from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0130_classify(**kwargs: Any) -> dict[str, Any]:
    """Plant propagation.

    This class includes the production of all vegetative planting materials including cuttings, suckers and seedlings for direct plant propagation or to create plant grafting stock into which selected scion is grafted for eventual planting to produce crops.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0130":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0130."}
    return await task_open_isic_classify_entity(**kwargs)

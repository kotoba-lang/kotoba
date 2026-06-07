from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0910_classify(**kwargs: Any) -> dict[str, Any]:
    """Support activities for petroleum and natural gas extraction

    This class includes oil and gas field services performed on a fee or contract basis: directional drilling and redrilling; derrick building, repair and dismantling; cementing oil and gas well casings; pumping of oil and gas wells; plugging and abandoning wells; liquid mud preparation for drilling; chemical treatment of oil and gas wells; oil and gas well testing.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0910":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0910."}
    return await task_open_isic_classify_entity(**kwargs)

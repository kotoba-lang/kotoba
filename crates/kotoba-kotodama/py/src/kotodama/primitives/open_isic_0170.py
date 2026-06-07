from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0170_classify(**kwargs: Any) -> dict[str, Any]:
    """Hunting, trapping and related service activities.

    This class includes hunting and trapping on a commercial basis; taking of animals (dead or alive) for food, fur, skin, or for use in research, in zoos or as pets; producing fur skins, reptile or bird skins from hunting or trapping activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0170":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0170."}
    return await task_open_isic_classify_entity(**kwargs)

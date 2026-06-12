from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0164_classify(**kwargs: Any) -> dict[str, Any]:
    """Seed processing for propagation.

    This class includes all post-harvest activities aimed at upgrading seed quality through the removal of non-seed material, undersized, mechanically or insect-damaged and immature seeds, as well as removal of seed moisture to a safe level for seed storage.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0164":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0164."}
    return await task_open_isic_classify_entity(**kwargs)

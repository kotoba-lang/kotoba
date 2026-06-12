from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0311_classify(**kwargs: Any) -> dict[str, Any]:
    """Marine fishing.

    This class includes fishing on a commercial basis in ocean and coastal waters, including the taking of marine crustaceans and molluscs, whales, other aquatic animals and plants.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0311":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0311."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0321_classify(**kwargs: Any) -> dict[str, Any]:
    """Marine aquaculture.

    This class includes aquaculture (including mariculture) producing fish, crustaceans, molluscs, other aquatic animals and plants in seawater, including operation of hatcheries and fish farms in salt-water-filled tanks or reservoirs, in enclosed sections of the sea, or in saltwater ponds.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0321":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0321."}
    return await task_open_isic_classify_entity(**kwargs)

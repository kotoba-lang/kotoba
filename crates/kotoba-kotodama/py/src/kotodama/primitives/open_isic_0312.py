from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0312_classify(**kwargs: Any) -> dict[str, Any]:
    """Freshwater fishing.

    This class includes fishing on a commercial basis in inland waters, including the taking of freshwater crustaceans and molluscs, other freshwater aquatic animals and plants.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0312":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0312."}
    return await task_open_isic_classify_entity(**kwargs)

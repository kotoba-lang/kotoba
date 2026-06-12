from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1020_classify(**kwargs: Any) -> dict[str, Any]:
    """Processing and preserving of fish, crustaceans and molluscs

    This class includes preparation and preservation of fish, crustaceans and molluscs: freezing, deep freezing, drying, cooking, smoking, salting, immersing in brine, canning etc.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1020":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1020."}
    return await task_open_isic_classify_entity(**kwargs)

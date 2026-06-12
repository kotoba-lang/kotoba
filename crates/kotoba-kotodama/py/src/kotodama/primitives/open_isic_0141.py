from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0141_classify(**kwargs: Any) -> dict[str, Any]:
    """Raising of cattle and buffaloes.

    This class includes raising and breeding of cattle and buffaloes for the production of meat, milk, hides, skins, and for draught power or breeding stock. Also includes production of raw milk from cows and buffaloes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0141":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0141."}
    return await task_open_isic_classify_entity(**kwargs)

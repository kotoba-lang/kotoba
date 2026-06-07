from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0146_classify(**kwargs: Any) -> dict[str, Any]:
    """Raising of poultry.

    This class includes raising and breeding of poultry (chickens, turkeys, ducks, geese and guinea fowl), and production of eggs and operation of poultry hatcheries.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0146":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0146."}
    return await task_open_isic_classify_entity(**kwargs)

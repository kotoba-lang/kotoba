from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0729_classify(**kwargs: Any) -> dict[str, Any]:
    """Mining of other non-ferrous metal ores

    This class includes mining of non-ferrous metal ores, except uranium and thorium ores.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0729":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0729."}
    return await task_open_isic_classify_entity(**kwargs)

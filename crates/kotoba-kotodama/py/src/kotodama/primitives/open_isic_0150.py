from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0150_classify(**kwargs: Any) -> dict[str, Any]:
    """Mixed farming.

    This class includes operation of units engaged in both crop and animal production in combination, without either having a specialization ratio of 66 percent or more for either crop or animal production. A specialization ratio of 66 percent or more disqualifies the unit from being classified here and it would instead be classified to 011, 012, 013 or 014.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0150":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0150."}
    return await task_open_isic_classify_entity(**kwargs)

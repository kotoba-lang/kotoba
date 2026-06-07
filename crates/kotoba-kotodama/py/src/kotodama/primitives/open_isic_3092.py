from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3092_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of bicycles and invalid carriages.

    This class includes the manufacture of non-motorised bicycles and invalid carriages.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3092":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3092."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4799_classify(**kwargs: Any) -> dict[str, Any]:
    """Other retail sale not in stores, stalls or markets.

    This class includes other retail sale not in stores, stalls or markets.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4799":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4799."}
    return await task_open_isic_classify_entity(**kwargs)

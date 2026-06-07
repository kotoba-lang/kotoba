from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1030_classify(**kwargs: Any) -> dict[str, Any]:
    """Processing and preserving of fruit and vegetables

    This class includes the processing and preserving of fruit and vegetables, including frozen, canned, pickled, dried or dehydrated forms. It includes production of fruit and vegetable juices, fruit pastes and jellies, and other preserved fruit and vegetable products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1030":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1030."}
    return await task_open_isic_classify_entity(**kwargs)

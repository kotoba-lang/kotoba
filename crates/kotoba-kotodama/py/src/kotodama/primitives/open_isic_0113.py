from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0113_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of vegetables and melons, roots and tubers.

    This class includes the growing of vegetables, melons, roots and tubers, including organic farming and growing of genetically modified vegetables.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0113":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0113."}
    return await task_open_isic_classify_entity(**kwargs)

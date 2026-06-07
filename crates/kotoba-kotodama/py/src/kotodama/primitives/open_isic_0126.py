from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0126_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of oleaginous fruits

    This class includes the growing of oleaginous fruits.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0126":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0126."}
    return await task_open_isic_classify_entity(**kwargs)

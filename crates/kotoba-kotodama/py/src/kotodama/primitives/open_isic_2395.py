from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2395_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of articles of concrete, cement and plaster

    This class includes the manufacture of articles of concrete, cement and plaster for use in construction and other purposes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2395":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2395."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2219_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other rubber products

    This class includes the manufacture of other products of natural or synthetic rubber, unvulcanised, vulcanised or hardened.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2219":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2219."}
    return await task_open_isic_classify_entity(**kwargs)

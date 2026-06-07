from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2513_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of steam generators, except central heating hot water boilers.

    This class includes the manufacture of steam or other vapour generating boilers and nuclear reactors.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2513":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2513."}
    return await task_open_isic_classify_entity(**kwargs)

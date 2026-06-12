from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1200_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of tobacco products

    This class includes the manufacture of tobacco products such as cigarettes, cigars, pipe tobacco, chewing tobacco and snuff.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1200":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1200."}
    return await task_open_isic_classify_entity(**kwargs)

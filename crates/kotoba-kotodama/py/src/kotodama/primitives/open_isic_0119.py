from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0119_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of other non-perennial crops.

    This class includes the growing of non-perennial crops not elsewhere classified, including forage crops, cut flowers, sugar beet seeds and other crop seeds.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0119":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0119."}
    return await task_open_isic_classify_entity(**kwargs)

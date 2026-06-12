from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1512_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of luggage, handbags and the like, saddlery and harness

    This class includes the manufacture of luggage, handbags and similar articles of leather, composition leather, plastic sheeting, textile materials, vulcanized fibre or paperboard, and the manufacture of saddlery and harness.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1512":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1512."}
    return await task_open_isic_classify_entity(**kwargs)

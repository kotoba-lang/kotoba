from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2100_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of pharmaceuticals, medicinal chemical and botanical products

    This class includes the manufacture of pharmaceuticals, medicinal chemical and botanical products for human or veterinary use.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2100":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2100."}
    return await task_open_isic_classify_entity(**kwargs)

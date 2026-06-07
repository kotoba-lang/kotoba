from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1920_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of refined petroleum products

    This class includes the manufacture of liquid or gaseous fuels and other products from crude petroleum, bituminous minerals or their fractionation products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1920":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1920."}
    return await task_open_isic_classify_entity(**kwargs)

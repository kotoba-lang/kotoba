from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1050_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of dairy products

    This class includes the manufacture of dairy products such as fresh liquid milk, butter, cheese, ice cream, and other dairy-based products from raw milk.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1050":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1050."}
    return await task_open_isic_classify_entity(**kwargs)

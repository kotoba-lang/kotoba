from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7320_classify(**kwargs: Any) -> dict[str, Any]:
    """Market research and public opinion polling

    This class includes the investigation into market potential, acceptance of products, customer habits and purchasing patterns for the purpose of sales promotion and development of new products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7320":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7320."}
    return await task_open_isic_classify_entity(**kwargs)

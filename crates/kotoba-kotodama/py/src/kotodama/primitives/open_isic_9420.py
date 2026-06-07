from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9420_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of trade unions

    This class includes promoting the interests of employees through activities of labour unions and other labour organizations.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9420":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9420."}
    return await task_open_isic_classify_entity(**kwargs)

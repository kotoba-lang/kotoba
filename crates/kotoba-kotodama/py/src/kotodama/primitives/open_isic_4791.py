from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4791_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale via mail order houses or via Internet.

    This class includes the retail sale of any kind of product by mail order or over the Internet.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4791":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4791."}
    return await task_open_isic_classify_entity(**kwargs)

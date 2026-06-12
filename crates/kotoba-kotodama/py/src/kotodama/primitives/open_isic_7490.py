from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7490_classify(**kwargs: Any) -> dict[str, Any]:
    """Other professional, scientific and technical activities n.e.c.

    This class includes a variety of service activities of a professional, scientific or technical nature which are not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7490":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7490."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8530_classify(**kwargs: Any) -> dict[str, Any]:
    """Higher education

    This class includes the provision of post-secondary and higher education leading to academic or professional degrees.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8530":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8530."}
    return await task_open_isic_classify_entity(**kwargs)

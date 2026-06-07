from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0112_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of rice.

    This class includes the growing of rice, including organic farming of rice and growing of genetically modified rice.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0112":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0112."}
    return await task_open_isic_classify_entity(**kwargs)

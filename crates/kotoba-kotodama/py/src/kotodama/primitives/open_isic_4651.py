from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4651_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of computers, computer peripheral equipment and software

    This class includes the wholesale of computers, computer peripheral equipment and software.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4651":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4651."}
    return await task_open_isic_classify_entity(**kwargs)

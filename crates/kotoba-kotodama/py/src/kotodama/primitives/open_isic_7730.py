from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7730_classify(**kwargs: Any) -> dict[str, Any]:
    """Renting and leasing of other machinery, equipment and tangible goods

    This class includes the renting and leasing of machinery, equipment and tangible goods not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7730":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7730."}
    return await task_open_isic_classify_entity(**kwargs)

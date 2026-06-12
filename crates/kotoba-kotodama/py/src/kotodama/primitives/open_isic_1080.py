from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1080_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of prepared animal feeds

    This class includes the manufacture of prepared feeds for animals, including pets.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1080":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1080."}
    return await task_open_isic_classify_entity(**kwargs)

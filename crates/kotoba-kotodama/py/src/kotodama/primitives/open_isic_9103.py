from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9103_classify(**kwargs: Any) -> dict[str, Any]:
    """Botanical and zoological gardens and nature reserves activities

    This class includes the operation of botanical and zoological gardens and nature reserves, including wildlife preserves.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9103":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9103."}
    return await task_open_isic_classify_entity(**kwargs)

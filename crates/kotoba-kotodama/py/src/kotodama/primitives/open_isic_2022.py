from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2022_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of paints, varnishes and similar coatings, printing ink and mastics

    This class includes the manufacture of paints, varnishes and similar coatings, printing ink and mastics.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2022":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2022."}
    return await task_open_isic_classify_entity(**kwargs)

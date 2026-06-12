from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7020_classify(**kwargs: Any) -> dict[str, Any]:
    """Management consultancy activities

    This class includes the provision of advice, guidance or operational assistance to businesses and other organizations on management issues.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7020":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7020."}
    return await task_open_isic_classify_entity(**kwargs)

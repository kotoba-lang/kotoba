from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2211_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of rubber tyres and tubes; retreading and rebuilding of rubber tyres

    This class includes the manufacture of rubber tyres and tubes for all types of vehicles and aircraft, and the retreading and rebuilding of rubber tyres.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2211":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2211."}
    return await task_open_isic_classify_entity(**kwargs)

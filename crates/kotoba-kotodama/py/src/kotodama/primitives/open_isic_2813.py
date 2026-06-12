from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2813_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other pumps, compressors, taps and valves.

    This class includes the manufacture of pumps for liquids, gas compressors, and industrial taps and valves.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2813":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2813."}
    return await task_open_isic_classify_entity(**kwargs)

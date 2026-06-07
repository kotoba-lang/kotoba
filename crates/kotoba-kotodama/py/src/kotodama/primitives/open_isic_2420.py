from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2420_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of basic precious and other non-ferrous metals.

    This class includes the manufacture of basic precious and other non-ferrous metals from ore, pig or scrap.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2420":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2420."}
    return await task_open_isic_classify_entity(**kwargs)

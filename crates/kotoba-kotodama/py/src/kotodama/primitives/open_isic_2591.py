from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2591_classify(**kwargs: Any) -> dict[str, Any]:
    """Forging, pressing, stamping and roll-forming of metal; powder metallurgy.

    This class includes the forging, pressing, stamping and roll-forming of metal and manufacture of sintered metal articles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2591":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2591."}
    return await task_open_isic_classify_entity(**kwargs)

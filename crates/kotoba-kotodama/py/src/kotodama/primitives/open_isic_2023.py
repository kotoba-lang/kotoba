from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2023_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of soap and detergents, cleaning and polishing preparations, perfumes and toilet preparations

    This class includes the manufacture of soap and detergents, cleaning and polishing preparations, perfumes and toilet preparations.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2023":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2023."}
    return await task_open_isic_classify_entity(**kwargs)

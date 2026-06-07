from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2826_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of machinery for textile, apparel and leather production.

    This class includes the manufacture of machinery used in the production of textiles, apparel and leather goods.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2826":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2826."}
    return await task_open_isic_classify_entity(**kwargs)

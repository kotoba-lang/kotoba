from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2012_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of fertilizers and nitrogen compounds

    This class includes the manufacture of fertilizers and nitrogen compounds.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2012":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2012."}
    return await task_open_isic_classify_entity(**kwargs)

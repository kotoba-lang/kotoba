from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0128_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of spices, aromatic, drug and pharmaceutical crops

    This class includes the growing of spices, aromatic, narcotic and pharmaceutical crops.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0128":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0128."}
    return await task_open_isic_classify_entity(**kwargs)

from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0893_classify(**kwargs: Any) -> dict[str, Any]:
    """Extraction of salt

    This class includes extraction of salt from underground including by dissolving and pumping, salt production by evaporation of sea water or other saline waters, crushing, purification and refining of salt by the producer.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0893":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0893."}
    return await task_open_isic_classify_entity(**kwargs)

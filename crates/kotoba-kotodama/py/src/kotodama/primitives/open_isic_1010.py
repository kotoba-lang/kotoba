from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1010_classify(**kwargs: Any) -> dict[str, Any]:
    """Processing and preserving of meat and meat products

    This class includes the processing and preserving of meat and meat products. It includes slaughtering and dressing of animals, processing of meat, production of canned meat products, and other meat processing activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1010":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1010."}
    return await task_open_isic_classify_entity(**kwargs)

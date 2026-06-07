from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2220_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of plastics products

    This class includes the processing of new or spent (recycled) plastics materials into intermediate or final products, using such processes as compression moulding; extrusion moulding; injection moulding; blow moulding; casting.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2220":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2220."}
    return await task_open_isic_classify_entity(**kwargs)

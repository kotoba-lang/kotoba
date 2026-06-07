from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1410_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of wearing apparel, except fur apparel

    This class includes the manufacture of all types of wearing apparel (suits, coats, dresses, blouses, shirts, etc.) of any material (woven fabrics, knitted and crocheted fabrics, non-wovens, leather, etc.) and for all uses (men's, women's and children's apparel, work wear, outdoor clothing, etc.).
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1410":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1410."}
    return await task_open_isic_classify_entity(**kwargs)

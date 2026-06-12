from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1394_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of cordage, rope, twine and netting

    This class includes the manufacture of cordage, rope, twine and netting from any textile material including jute, hemp, sisal, cotton and man-made fibres.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1394":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1394."}
    return await task_open_isic_classify_entity(**kwargs)

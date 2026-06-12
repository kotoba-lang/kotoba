from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2670_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of optical instruments and photographic equipment.

    This class includes the manufacture of optical instruments and lenses, such as binoculars, microscopes, telescopes, prisms and lenses, and photographic equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2670":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2670."}
    return await task_open_isic_classify_entity(**kwargs)

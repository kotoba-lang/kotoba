from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4610_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale on a fee or contract basis

    This class includes the activities of commission agents, commodity brokers and all other wholesalers who trade on behalf of others.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4610":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4610."}
    return await task_open_isic_classify_entity(**kwargs)

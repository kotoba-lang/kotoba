from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6622_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of insurance agents and brokers.

    This class includes activities of insurance agents and brokers (insurance intermediaries) in selling, negotiating or soliciting of annuities and insurance and reinsurance policies.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6622":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6622."}
    return await task_open_isic_classify_entity(**kwargs)

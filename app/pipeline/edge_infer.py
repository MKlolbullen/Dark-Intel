from ..llm import get_relation_client

_OPTIONS = (
    "acquired_by, partner_of, competitor_of, supplies, "
    "fired_by, hires, announced_layoffs, no_relation"
)
_VALID = {opt.strip() for opt in _OPTIONS.split(",")}
_SYSTEM = (
    "You classify the relationship between two entities mentioned in a news article. "
    f"Respond with exactly one of these labels and no other text: {_OPTIONS}."
)


async def infer_relation_async(text: str, entity1: str, entity2: str) -> str:
    user = (
        f"Entity 1: {entity1}\n"
        f"Entity 2: {entity2}\n\n"
        f"Article excerpt:\n{text[:2000]}"
    )
    try:
        label = await get_relation_client().acomplete(
            system=_SYSTEM,
            user=user,
            max_tokens=32,
        )
    except Exception:
        return "mentions"
    label = label.strip().lower()
    return label if label in _VALID else "mentions"

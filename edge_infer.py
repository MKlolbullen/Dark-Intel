import openai

def infer_relation(text: str, entity1: str, entity2: str) -> str:
    prompt = (
        f"In the text below, what is the most likely relation between '{entity1}' and '{entity2}'?\n"
        f"Options: acquired_by, partner_of, competitor_of, supplies, fired_by, hires, announced_layoffs, no_relation\n\n"
        f"TEXT:\n{text[:2000]}"
    )
    try:
        r = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return r.choices[0].message.content.strip()
    except Exception:
        return "mentions"

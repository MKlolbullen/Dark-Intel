import spacy, re
from rapidfuzz import fuzz
_nlp = spacy.load("en_core_web_sm")

def _clean(t): return re.sub(r"https?://\S+", "", t)

def extract_entities(text, thr=85):
    doc = _nlp(_clean(text)[:20000])
    ents = [(e.text.strip(), e.label_) for e in doc.ents
            if e.label_ in ("ORG", "PERSON", "GPE", "PRODUCT")]
    uniq = []
    for t,l in ents:
        if not any(fuzz.ratio(t,u[0])>thr for u in uniq):
            uniq.append((t,l))
    return uniq

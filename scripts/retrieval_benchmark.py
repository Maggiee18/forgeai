"""Hand-written retrieval sanity benchmark: does the right passage reach the top 4?
Queries are split into ones using the documents' own words and paraphrases a real user would type.
Run: python scripts/retrieval_benchmark.py"""
from forgeai.docs import load_folder
from forgeai.retrieval import build_index

hr, sp = load_folder("demos/hr_policy/docs"), load_folder("demos/ship_spares/docs")
QUERIES = [
    (hr, "How many days of annual leave do I get?", "21 days of annual leave", "doc words"),
    (hr, "how much vacation time per year", "21 days of annual leave", "paraphrase"),
    (hr, "what's the per diem when I travel as a manager", "INR 1,800 per day", "paraphrase"),
    (hr, "hotel cap in Tier 1 cities for G3", "INR 7,000", "doc words"),
    (hr, "can I take PTO while serving my resignation notice", "notice period", "paraphrase"),
    (hr, "my boss isn't fixing my complaint, what next", "Head of Department", "paraphrase"),
    (hr, "is a present from a vendor ok", "INR 2,000", "paraphrase"),
    (hr, "petrol reimbursement for using my own car", "INR 12 per kilometre", "paraphrase"),
    (hr, "how many days of leave does a new dad get", "paternity", "paraphrase"),
    (sp, "who approves an order of USD 30,000", "Fleet Manager", "doc words"),
    (sp, "sign-off needed for a 30k dollar purchase", "Fleet Manager", "paraphrase"),
    (sp, "price of ME-FI-1021", "412.50", "doc words"),
    (sp, "how long do I have to send back unused Harbourline parts", "14 days", "paraphrase"),
    (sp, "rush order fee at Poseidon", "15 percent", "paraphrase"),
]
CONFIGS = {
    "bm25": {"strategy": "bm25"},
    "dense": {"strategy": "dense", "embedding": {"provider": "wordllama"}},
    "hybrid": {"strategy": "hybrid", "embedding": {"provider": "wordllama"}},
}


def run():
    out = {}
    for name, extra in CONFIGS.items():
        cfg = {"chunk_size": 160, "chunk_overlap": 30, **extra}
        idx = {id(hr): build_index(hr, cfg), id(sp): build_index(sp, cfg)}
        score = {"doc words": [0, 0], "paraphrase": [0, 0]}
        for docs, q, expect, kind in QUERIES:
            hit = any(expect.lower() in c.text.lower() for c, _ in idx[id(docs)].search(q, 4))
            score[kind][0] += hit
            score[kind][1] += 1
        out[name] = score
    return out


if __name__ == "__main__":
    for name, s in run().items():
        print(f"{name:<7} doc words {s['doc words'][0]}/{s['doc words'][1]}   paraphrase {s['paraphrase'][0]}/{s['paraphrase'][1]}")

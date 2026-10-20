"""Local Loom-style matching: tags + FashionCLIP, without hosted services.
This is an adaptation of the approach, not the upstream Loom application.
Outfits are sampled, not ranked; all returned cards have equal status.
"""
import hashlib
import itertools
import json
import math
import random
from datetime import date

OCCASIONS = {
    "Everyday": "a casual everyday outfit",
    "Class / campus": "a comfortable college campus outfit",
    "Smart casual": "a smart casual outfit",
    "Evening out": "an evening dinner outfit",
}
TOPS = {"T-shirt", "Shirt", "Sweater", "Hoodie"}
BOTTOMS = {"Jeans", "Trousers", "Shorts", "Skirt"}
LAYERS = {"Jacket", "Coat"}
NEUTRALS = {"Black", "White", "Gray", "Navy", "Beige", "Khaki", "Brown"}

def signature(outfit):
    return tuple(sorted(item["id"] for item in outfit))

def recommend(items, scores, include_layer=False, day=None, variant=0, exclude=()):
    attrs = {i["id"]: json.loads(i["attributes_json"]) for i in items}
    def group(categories):
        return [i for i in items if attrs[i["id"]].get("Category") in categories]
    tops, bottoms = group(TOPS), group(BOTTOMS)
    dresses, shoes, layers = group({"Dress"}), group({"Shoes"}), group(LAYERS)
    base_count = len(tops) * len(bottoms) + len(dresses)
    if not base_count:
        return [], ["Add a top and bottom, or a dress, in the supported categories."]
    notes = []
    if not shoes:
        notes.append("No shoes available; showing clothing-only combinations.")
    if include_layer and not layers:
        notes.append("No jacket or coat available; showing outfits without a layer.")
    footwear = shoes or [None]
    outerwear = (layers or [None]) if include_layer else [None]
    total = base_count * len(footwear) * len(outerwear)
    seed = f"{day or date.today().isoformat()}:{variant}:" + ",".join(str(i["id"]) for i in items)
    rng = random.Random(hashlib.sha256(seed.encode()).digest())
    blocked = {tuple(sorted(s)) for s in exclude}
    # Decode product indices without allocating every possible outfit.
    def outfit_at(index):
        index, layer_index = divmod(index, len(outerwear))
        base_index, shoe_index = divmod(index, len(footwear))
        pairs = len(tops) * len(bottoms)
        if base_index < pairs:
            ti, bi = divmod(base_index, len(bottoms))
            outfit = [tops[ti], bottoms[bi]]
        else:
            outfit = [dresses[base_index - pairs]]
        return outfit + [i for i in (footwear[shoe_index], outerwear[layer_index]) if i is not None]

    # Cap work for very large closets. Small/normal closets are fully covered.
    indices = range(total) if total <= 100000 else rng.sample(range(total), 100000)
    fresh, repeats = [], []
    fresh_count = 0
    for index in indices:
        outfit = outfit_at(index)
        colors = [attrs[i["id"]].get("Color") for i in outfit]
        pairs = list(itertools.combinations(colors, 2))
        harmony = sum(a == b or a in NEUTRALS or b in NEUTRALS for a, b in pairs) / max(1, len(pairs))
        patterns = sum(attrs[i["id"]].get("Base pattern", "Solid") != "Solid" for i in outfit)
        relevance = sum(scores.get(i["id"], 0.0) for i in outfit) / len(outfit)
        weight = math.exp(max(-8, min(8, 4 * relevance + harmony - .35 * max(0, patterns - 1))))
        # Weighted reservoir sampling: matching influences chance, not a ranking of outfits.
        priority = math.log(max(rng.random(), 1e-15)) / weight
        is_repeat = signature(outfit) in blocked
        pool = repeats if is_repeat else fresh
        fresh_count += not is_repeat
        pool.append((priority, index, outfit))
        pool.sort(key=lambda entry: entry[0], reverse=True)
        del pool[3:]
    picked = fresh[:3]
    if len(picked) < 3:
        picked += repeats[:3-len(picked)]
        if repeats and blocked:
            notes.append("Not enough unseen combinations; some previous outfits are shown again.")
    if total > 100000:
        notes.append("Suggestions were sampled from a large number of possible combinations.")
    if total < 3:
        notes.append(f"Your closet currently supports only {total} distinct combination(s) for these settings.")
    rng.shuffle(picked)
    return [entry[2] for entry in picked], notes


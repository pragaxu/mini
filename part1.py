# %% [markdown]
# # Part 1 - Python Foundations (run cell by cell in Colab, or as a script)

# %% Setup
import pandas as pd
from datetime import datetime
from collections import defaultdict

DATA_DIR = "data"
COUNTRIES = ["US", "GB", "IN"]
REQUIRED = ["video_id", "trending_date", "title", "channel_title", "category_id",
            "publish_time", "views", "likes", "dislikes", "comment_count",
            "comments_disabled", "ratings_disabled"]
# classification thresholds
VIRAL_VIEWS, VIRAL_RATIO = 5_000_000, 0.90
STEADY_VIEWS, DIVISIVE_RATIO = 100_000, 0.70

print("=" * 40)
print(f"TrendPulse run started {datetime.now():%Y-%m-%d %H:%M}")
print(f"Countries: {', '.join(COUNTRIES)}")
print("=" * 40)

# %% Loading
def load_country(path, country, max_rows=None):
    try:
        df = pd.read_csv(path, nrows=max_rows)
    except UnicodeDecodeError:
        df = pd.read_csv(path, nrows=max_rows, encoding="latin-1")
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{country}: missing columns {missing}")
    df["country"] = country
    return df.to_dict("records")

records = []
for c in COUNTRIES:
    rows = load_country(f"{DATA_DIR}/{c}videos.csv", c)
    print(f"{c}: {len(rows):,} records")
    records.extend(rows)
print(f"Total: {len(records):,}")

cat_df = pd.read_csv(f"{DATA_DIR}/categories.csv")
print(cat_df.columns.tolist())          # check names; adjust below if needed
category_names = dict(zip(cat_df["category_id"], cat_df["category_name"]))

# %% Cleaning (core Python)
def to_int(v):
    return int(float(v))

def to_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() == "true"

def parse_trending(s):                   # "17.14.11" -> 2017-11-14 (yy.dd.mm)
    return datetime.strptime(str(s).strip(), "%y.%d.%m").date()

def parse_publish(s):
    return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S")

fails = defaultdict(int)
clean = []
for r in records:
    ok = True
    # Rule: bad numeric -> substitute 0 (record still useful); bad date -> drop
    for f in ("views", "likes", "dislikes", "comment_count"):
        try:
            r[f] = to_int(r[f])
        except (ValueError, TypeError):
            fails[f] += 1
            r[f] = 0
    for f in ("comments_disabled", "ratings_disabled"):
        try:
            r[f] = to_bool(r[f])
        except Exception:
            fails[f] += 1
            r[f] = False
    for f, fn in (("trending_date", parse_trending), ("publish_time", parse_publish)):
        try:
            r[f] = fn(r[f])
        except (ValueError, TypeError):
            fails[f] += 1
            ok = False
    if ok:
        clean.append(r)
print("Parse failures per field:", dict(fails))
print(f"Kept {len(clean):,} of {len(records):,}")

# %% Data structures
# Tuples: immutable snapshots, safe as dict keys / set members
key_tuples = [(r["video_id"], r["trending_date"], r["views"], r["likes"]) for r in clean]

# Sets: fast membership + set algebra
ids = {c: {r["video_id"] for r in clean if r["country"] == c} for c in COUNTRIES}
in_all = set.intersection(*ids.values())
print(f"Videos trending in all {len(COUNTRIES)} countries: {len(in_all):,}")
for c in COUNTRIES:
    others = set().union(*(ids[o] for o in COUNTRIES if o != c))
    print(f"Unique to {c}: {len(ids[c] - others):,}")

# Dict counter: O(1) update per key
channel_counts = {}
for r in clean:
    channel_counts[r["channel_title"]] = channel_counts.get(r["channel_title"], 0) + 1
top15 = sorted(channel_counts.items(), key=lambda kv: kv[1], reverse=True)[:15]  # slicing
for name, n in top15:
    print(f"{name:40s} {n:5d}")

# Nested dict: country -> category -> count
summary = {}
for r in clean:
    cat = category_names.get(r["category_id"], "Unknown")
    summary.setdefault(r["country"], {}).setdefault(cat, 0)
    summary[r["country"]][cat] += 1
for c, cats in summary.items():
    print(c, {k: cats[k] for k in list(cats)[:4]})
# Mutable: list, dict, set.  Immutable: tuple, str, int, date.

# %% Scope demo
outside = "I am global"
def scope_demo():
    inside = "I am local"
    print(outside)                       # reads global fine
    return inside
scope_demo()
try:
    print(inside)
except NameError as e:
    print("NameError:", e)               # local not visible outside

# %% Loops over strings
def title_features(title):
    upper_words = marks = 0
    for ch in title:
        if ch in "!?":
            marks += 1
    words = title.split()
    for w in words:
        if len(w) > 1 and w.isupper():
            upper_words += 1
    return {"upper_words": upper_words, "marks": marks, "n_words": len(words)}

for i in range(3):                       # range + index access
    print(clean[i]["title"], title_features(clean[i]["title"]))

THRESH, i, first = 10_000_000, 0, None   # while with break/continue
while i < len(clean):
    r = clean[i]
    i += 1
    if r["views"] <= 0:
        continue
    if r["views"] > THRESH:
        first = r
        break
print("First video over threshold:", first["title"] if first else None)

# %% Classification
def like_ratio(r):
    total = r["likes"] + r["dislikes"]
    return None if total == 0 else r["likes"] / total

def classify_video(r):
    if r["ratings_disabled"]:
        return "Unrated"
    ratio = like_ratio(r)
    if r["views"] <= 0 or ratio is None:
        return "Unrated"
    if ratio < DIVISIVE_RATIO and r["views"] >= STEADY_VIEWS:
        return "Divisive"
    if r["views"] >= VIRAL_VIEWS:
        if ratio >= VIRAL_RATIO:
            return "Viral Hit"
        return "Steady Performer"
    if r["views"] >= STEADY_VIEWS:
        return "Steady Performer"
    return "Low Engagement"

label_counts = {}
for r in clean:
    lab = classify_video(r)
    label_counts[lab] = label_counts.get(lab, 0) + 1
print(label_counts)
# Hand-trace (write in Markdown): record with 8M views, 200k likes, 5k dislikes:
# ratings_disabled False -> ratio 0.976 -> views>0 -> not <0.70 -> views>=5M -> ratio>=0.90 -> "Viral Hit"

# %% Refactor: repeated "safe parse with failure counter" -> one function
def safe_parse(rec, field, fn, default=None):
    try:
        rec[field] = fn(rec[field])
        return True
    except (ValueError, TypeError):
        fails[field] += 1
        rec[field] = default
        return False
# Gain: one place to change parsing/error policy; no copy-pasted try/except blocks.

# %% [markdown]
# # Part 2 - NumPy & Pandas
# %% Load
import numpy as np
import pandas as pd

DATA_DIR, COUNTRIES = "data", ["US", "GB", "IN"]

def read(path):
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")

frames = []
for c in COUNTRIES:
    d = read(f"{DATA_DIR}/{c}videos.csv")
    d["country"] = c
    print(c, d.shape); d.info(); print(d.head(3))
    frames.append(d)
df = pd.concat(frames, ignore_index=True)          # concat
print("Combined:", df.shape); print(df.describe())

# %% Data types and quality
df["trending_date"] = pd.to_datetime(df["trending_date"], format="%y.%d.%m", errors="coerce")
df["publish_time"] = pd.to_datetime(df["publish_time"], errors="coerce", utc=True).dt.tz_localize(None)
for c in ["comments_disabled", "ratings_disabled", "video_error_or_removed"]:
    df[c] = df[c].astype(str).str.lower().eq("true")
for c in ["views", "likes", "dislikes", "comment_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["category_id"] = pd.to_numeric(df["category_id"], errors="coerce")

# Issues: missing descriptions, removed videos, duplicates, bad dates
miss = df.isna().sum()
miss = pd.DataFrame({"count": miss, "pct": (miss / len(df) * 100).round(3)})
print(miss[miss["count"] > 0])
df["description"] = df["description"].fillna("")                       # text: empty is fine
df = df.dropna(subset=["views", "likes", "dislikes", "comment_count",
                       "trending_date", "publish_time"])              # unusable rows
before = len(df)
df = df.drop_duplicates(subset=["video_id", "trending_date", "country"], keep="last")
print("Duplicates removed:", before - len(df))
df = df[~df["video_error_or_removed"]].copy()

# %% NumPy arrays
views = df["views"].to_numpy(dtype=float)
likes = df["likes"].to_numpy(dtype=float)
dislikes = df["dislikes"].to_numpy(dtype=float)
comments = df["comment_count"].to_numpy(dtype=float)
for n, a in [("views", views), ("likes", likes), ("dislikes", dislikes), ("comments", comments)]:
    print(n, a.shape, a.dtype)
print(np.sort(views)[-10:][::-1])      # 10 largest
print(views[::100][:10])               # every 100th
print(views[100:110])                  # sub-array

def safe_div(a, b):
    return np.divide(a, b, out=np.zeros_like(a, dtype=float), where=b != 0)

like_ratio = safe_div(likes, likes + dislikes)
comment_rate = safe_div(comments, views)

def minmax(x):
    rng = x.max() - x.min()
    return (x - x.min()) / rng if rng else np.zeros_like(x)

# Weights: likes signal approval (0.35), comments signal deeper involvement (0.30),
# views signal reach (0.20), like ratio guards against disliked content (0.15)
engagement = (0.20 * minmax(views) + 0.35 * minmax(likes) +
              0.30 * minmax(comments) + 0.15 * like_ratio)
log_views = np.log10(views + 1)   # raw views span ~6 orders of magnitude: heavy right skew
top10_mask = engagement >= np.percentile(engagement, 90)
df["engagement"] = engagement
df["like_ratio"], df["comment_rate"], df["log_views"] = like_ratio, comment_rate, log_views
print("Top-10% flagged:", top10_mask.sum())

# %% Reshape + broadcasting (days x countries)
pivot = df.pivot_table(index="trending_date", columns="country", values="video_id",
                       aggfunc="count", fill_value=0)
M = pivot.to_numpy(dtype=float)                            # (days, countries)
print(M.shape, M.reshape(-1).shape, M.flatten()[:5])
share_of_day = M / M.sum(axis=1, keepdims=True)            # broadcasting
vs_country_avg = M / M.mean(axis=0, keepdims=True)         # broadcasting

# %% Filtering
q_a = df[(df["views"] >= 1_000_000) & (df["likes"] > 50_000)]
q_b = df.sort_values("engagement", ascending=False).head(20)[
    ["title", "country", "views", "likes", "engagement"]]

# %% Category merge
cats = pd.read_csv(f"{DATA_DIR}/categories.csv")           # check column names
n0 = len(df)
df = df.merge(cats[["category_id", "category_name"]], on="category_id", how="left")
assert len(df) == n0                                       # left merge: no records lost
df["category_name"] = df["category_name"].fillna("Unknown")
q_c = df[df["category_name"].isin(["Music", "Gaming"]) & (df["views"] > df["views"].median())]
print(q_a.shape, q_c.shape)
print(df.loc[df["views"].idxmax(), ["title", "views"]], df.iloc[:3, :4])

# %% Aggregation
agg = (df.groupby(["category_name", "country"])
         .agg(records=("video_id", "size"), avg_views=("views", "mean"),
              avg_likes=("likes", "mean"), avg_eng=("engagement", "mean"))
         .reset_index())
print(agg.head(10))
print(df["category_name"].value_counts(), df["category_name"].value_counts(normalize=True).round(3))
df["pub_dow"] = df["publish_time"].dt.day_name()
df["pub_hour"] = df["publish_time"].dt.hour
print(df.groupby("pub_dow")["views"].mean().sort_values(ascending=False))
print(df.groupby("pub_hour")["views"].mean().sort_values(ascending=False).head())

# %% Time to trend + lifespan
df["days_to_trend"] = (df["trending_date"] - df["publish_time"].dt.normalize()).dt.days
print(df["days_to_trend"].describe())
life = (df.groupby(["country", "video_id"])
          .agg(lifespan=("trending_date", "nunique"), title=("title", "first"),
               category_name=("category_name", "first"), peak_views=("views", "max"))
          .reset_index())
print(life.sort_values("lifespan", ascending=False).head(10))
print(life.groupby("category_name")["lifespan"].mean().sort_values(ascending=False))

# %% Channel summary merge
per_video = df.groupby("video_id").agg(channel_title=("channel_title", "first"),
                                       total_views=("views", "max")).reset_index()
per_channel = per_video.groupby("channel_title").agg(trending_videos=("video_id", "nunique"),
                                                     total_views=("total_views", "sum")).reset_index()
chan = per_video[["video_id", "channel_title"]].merge(per_channel, on="channel_title")
print(per_channel.sort_values("trending_videos", ascending=False).head(10))

# %% [markdown]
# # Part 3 - Visualization, EDA & Business Thinking
# %% Load + clean (self-contained)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px

DATA_DIR, COUNTRIES = "data", ["US", "GB", "IN"]

def read(p):
    try:
        return pd.read_csv(p)
    except UnicodeDecodeError:
        return pd.read_csv(p, encoding="latin-1")

df = pd.concat([read(f"{DATA_DIR}/{c}videos.csv").assign(country=c) for c in COUNTRIES],
               ignore_index=True)
print(df.shape, df.dtypes)
miss = (df.isna().mean() * 100).round(3)
print(miss[miss > 0])                                    # % missing per affected column

df["trending_date"] = pd.to_datetime(df["trending_date"], format="%y.%d.%m", errors="coerce")
df["publish_time"] = pd.to_datetime(df["publish_time"], errors="coerce", utc=True).dt.tz_localize(None)
for c in ["views", "likes", "dislikes", "comment_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["views", "likes", "dislikes", "comment_count", "trending_date", "publish_time"])
df = df.drop_duplicates(subset=["video_id", "trending_date", "country"])
df = df[~df["video_error_or_removed"].astype(str).str.lower().eq("true")]
cats = pd.read_csv(f"{DATA_DIR}/categories.csv")
df = df.merge(cats[["category_id", "category_name"]], on="category_id", how="left")
df["category_name"] = df["category_name"].fillna("Unknown")
df["days_to_trend"] = (df["trending_date"] - df["publish_time"].dt.normalize()).dt.days

# %% Matplotlib charts (add a 2-4 sentence interpretation + why-this-chart under each)
fig, ax = plt.subplots(figsize=(9, 5))
df["category_name"].value_counts().plot.bar(ax=ax)
ax.set(title="Trending records per category", xlabel="Category", ylabel="Records")
plt.tight_layout(); plt.show()

fig, ax = plt.subplots()
ax.hist(np.log10(df["views"] + 1), bins=50)
ax.set(title="Distribution of views (log10)", xlabel="log10(views)", ylabel="Records")
plt.show()

fig, ax = plt.subplots()
ax.scatter(df["views"], df["likes"], s=4, alpha=0.3)
ax.set(xscale="log", yscale="symlog", title="Views vs likes", xlabel="Views (log)", ylabel="Likes")
plt.show()

fig, ax = plt.subplots(figsize=(10, 4))
for c in COUNTRIES:
    s = df[df["country"] == c].groupby("trending_date").size()
    ax.plot(s.index, s.values, label=c)
ax.set(title="Trending records per day", xlabel="Date", ylabel="Records"); ax.legend()
plt.show()

order = df.groupby("category_name")["views"].median().sort_values().index
data = [np.log10(df.loc[df["category_name"] == k, "views"] + 1) for k in order]
fig, ax = plt.subplots(figsize=(10, 5))
ax.boxplot(data, labels=order)
ax.set(title="Views by category (log10)", xlabel="Category", ylabel="log10(views)")
plt.xticks(rotation=70); plt.tight_layout(); plt.show()

# %% Plotly
s = df.sample(min(5000, len(df)), random_state=1)
px.scatter(s, x="views", y="likes", color="category_name", hover_name="title",
           log_x=True, log_y=True, title="Views vs likes by category").show()
avg = df.groupby(["category_name", "country"])["views"].mean().reset_index()
px.bar(avg, x="category_name", y="views", color="country", barmode="group",
       title="Average views per category by country").show()

# %% Distributions + outliers
for col in ["views", "likes"]:
    x = df[col]
    mean, med, mode = x.mean(), x.median(), x.mode().iloc[0]
    q1, q3 = x.quantile([.25, .75]); iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_out = ((x < lo) | (x > hi)).sum()
    skew = "right-skewed" if mean > med > mode else "left-skewed" if mean < med < mode else "roughly symmetric"
    print(f"{col}: mean={mean:,.0f} median={med:,.0f} mode={mode:,.0f} -> {skew}; "
          f"IQR bounds=({lo:,.0f}, {hi:,.0f}) outliers={n_out:,}")
# Decision (write up): KEEP outliers - they are the genuinely viral videos the briefing is about.

# %% Correlation
num = df[["views", "likes", "dislikes", "comment_count", "days_to_trend"]]
corr = num.corr()
plt.figure(figsize=(6, 5))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
plt.title("Correlation matrix"); plt.show()
pairs = (corr.where(np.triu(np.ones(corr.shape, bool), k=1)).stack()
             .abs().sort_values(ascending=False))
print(pairs.head(2))   # two strongest pairs; interpret + note correlation != causation

# %% Funnel (unique videos)
vid = df.groupby(["country", "video_id"]).agg(peak=("views", "max"),
                                              comments=("comment_count", "max")).reset_index()
s1 = len(vid)
s2 = vid[vid["peak"] > vid["peak"].median()]
s3 = s2[s2["peak"] > vid["peak"].quantile(0.90)]
s4 = s3[s3["comments"] >= 1000]
funnel = pd.DataFrame({"stage": ["All trended", "> median peak views", "> p90 peak views", "1000+ comments"],
                       "count": [s1, len(s2), len(s3), len(s4)]})
funnel["conv_from_prev_%"] = (funnel["count"] / funnel["count"].shift(1) * 100).round(1)
funnel["conv_from_start_%"] = (funnel["count"] / s1 * 100).round(1)
print(funnel)

# %% Retention
life = df.groupby(["country", "video_id"]).agg(lifespan=("trending_date", "nunique"),
                                               cat=("category_name", "first")).reset_index()
days = [1, 2, 3, 5, 7]
def retention(g):
    return pd.Series({f"day{d}": (g["lifespan"] >= d).mean() * 100 for d in days})
by_country = life.groupby("country").apply(retention)
top_cats = life["cat"].value_counts().head(4).index
by_cat = life[life["cat"].isin(top_cats)].groupby("cat").apply(retention)
print(by_country.round(1)); print(by_cat.round(1))
fig, ax = plt.subplots()
for name, row in by_country.iterrows():
    ax.plot(days, row.values, marker="o", label=name)
ax.set(title="Retention curve by country", xlabel="Day on trending list", ylabel="% of videos still trending")
ax.legend(); plt.show()

# %% Cohorts
first = df.groupby(["country", "video_id"]).agg(first_day=("trending_date", "min"),
                                                peak=("views", "max"),
                                                lifespan=("trending_date", "nunique")).reset_index()
first["cohort"] = first["first_day"].dt.to_period("M")
cohort = first.groupby("cohort").agg(videos=("video_id", "size"), avg_peak=("peak", "mean"),
                                     avg_life=("lifespan", "mean"))
print(cohort)   # check whether odd cohorts are small (partial months at window edges)

# %% Briefing (write 5-8 sentences in README using numbers printed above, plus one limitation:
# data only covers videos that DID trend, within a fixed time window.)

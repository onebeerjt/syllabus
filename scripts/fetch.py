"""Look up where every pick streams (US) on JustWatch and cache posters.

Usage: python3 scripts/fetch.py   -> writes data/availability.json and data/posters/
"""
import base64, gzip, io, json, os, sys, time, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://apis.justwatch.com/graphql"
COUNTRY = "US"
QUERY = """
query($f: TitleFilter, $c: Country!, $l: Language!) {
  popularTitles(country: $c, first: 5, filter: $f) {
    edges { node { id
      content(country: $c, language: $l) { title originalReleaseYear fullPath posterUrl externalIds { imdbId } }
      offers(country: $c, platform: WEB) {
        monetizationType retailPrice(language: $l) standardWebURL
        package { clearName technicalName }
      }
    } }
  }
}"""

# How each JustWatch monetization type is grouped on the page.
KIND = {"FLATRATE": "stream", "FREE": "free", "ADS": "free", "RENT": "rent", "BUY": "buy"}


def post(body):
    req = urllib.request.Request(API, json.dumps(body).encode(), {
        "content-type": "application/json", "user-agent": "Mozilla/5.0 (syllabus-site)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def lookup(title, year):
    # Generic titles ("The Game") need the year in the query to surface the right film.
    for q in (title, f"{title} {year}"):
        data = post({"query": QUERY, "variables": {
            "f": {"searchQuery": q, "objectTypes": ["MOVIE"]}, "c": COUNTRY, "l": "en"}})
        nodes = [e["node"] for e in data["data"]["popularTitles"]["edges"]]
        # Prefer an exact release-year match, then one year either side (festival vs. release dates).
        for slack in (0, 1):
            for n in nodes:
                if abs((n["content"]["originalReleaseYear"] or 0) - year) <= slack:
                    return n
    return None


def imdb_ratings(ids):
    """Ratings for the given tt ids from IMDb's free daily dataset (same source Consensus uses)."""
    with urllib.request.urlopen("https://datasets.imdbws.com/title.ratings.tsv.gz", timeout=120) as r:
        rows = gzip.open(io.BytesIO(r.read()), "rt", encoding="utf-8")
        next(rows)  # header: tconst averageRating numVotes
        out = {}
        for line in rows:
            tconst, rating, votes = line.rstrip("\n").split("\t")
            if tconst in ids:
                out[tconst] = {"rating": float(rating), "votes": int(votes)}
        return out


def offers(node):
    out = {}
    for o in node["offers"]:
        kind = KIND.get(o["monetizationType"])
        if not kind:
            continue
        key = (kind, o["package"]["technicalName"])
        prev = out.get(key)
        out[key] = {"kind": kind, "name": o["package"]["clearName"], "id": o["package"]["technicalName"],
                    "url": o["standardWebURL"], "price": o["retailPrice"] or (prev or {}).get("price")}
    return list(out.values())


def poster(node, slug):
    path = (node["content"].get("posterUrl") or "").replace("{profile}", "s166").replace("{format}", "jpg")
    dest = os.path.join(ROOT, "data", "posters", slug + ".jpg")
    if not path:
        return None
    if not os.path.exists(dest):
        with urllib.request.urlopen("https://images.justwatch.com" + path, timeout=30) as r:
            open(dest, "wb").write(r.read())
    return "data:image/jpeg;base64," + base64.b64encode(open(dest, "rb").read()).decode()


def main():
    os.makedirs(os.path.join(ROOT, "data", "posters"), exist_ok=True)
    picks = json.load(open(os.path.join(ROOT, "data", "picks.json")))
    result, missing = {}, []
    for p in picks:
        key = f"{p['t']} ({p['y']})"
        try:
            node = lookup(p["t"], p["y"])
        except Exception as e:  # network hiccup: keep going, report at the end
            missing.append(f"{key}: {e}")
            continue
        if not node:
            missing.append(f"{key}: no JustWatch match")
            continue
        slug = node["content"]["fullPath"].rsplit("/", 1)[-1]
        result[key] = {"jw": "https://www.justwatch.com" + node["content"]["fullPath"],
                       "imdbId": (node["content"].get("externalIds") or {}).get("imdbId"),
                       "offers": offers(node), "poster": poster(node, slug)}
        print(f"{key}: {len(result[key]['offers'])} offers")
        time.sleep(0.3)
    ratings = imdb_ratings({v["imdbId"] for v in result.values() if v["imdbId"]})
    for v in result.values():
        v["imdb"] = ratings.get(v["imdbId"])
    print(f"IMDb ratings: {sum(1 for v in result.values() if v['imdb'])} of {len(result)}")
    json.dump({"fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "country": COUNTRY, "titles": result},
              open(os.path.join(ROOT, "data", "availability.json"), "w"), ensure_ascii=False)
    if missing:
        print("\nNot found:\n  " + "\n  ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()

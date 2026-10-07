"""Assemble site/index.html from the data files. Run scripts/fetch.py first to refresh streaming info."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRITERION_TITLES = 1891  # criterion.com/shop/browse/list, read 2026-10-06


def load(name):
    return json.load(open(os.path.join(ROOT, "data", name)))


REPO = os.environ.get("GITHUB_REPOSITORY", "onebeerjt/syllabus")
data = {"repo": REPO, "picks": load("picks.json"), "diary": load("diary.json"), "sources": load("sources.json"),
        "avail": load("availability.json"), "ccTotal": CRITERION_TITLES}
html = open(os.path.join(ROOT, "scripts", "template.html")).read()
# "</" inside the JSON would close the script tag early.
html = html.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
os.makedirs(os.path.join(ROOT, "site"), exist_ok=True)
# artifact.html is the bare fragment for claude.ai Artifacts; index.html is the full page for GitHub Pages.
open(os.path.join(ROOT, "site", "artifact.html"), "w").write(html)
page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
        '</head>\n<body>\n' + html + '\n</body>\n</html>\n')
open(os.path.join(ROOT, "site", "index.html"), "w").write(page)
print(f"site/index.html: {len(page) / 1024:.0f} KB, {len(data['picks'])} picks")

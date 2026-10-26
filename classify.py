"""Classify forum comments as acceptable / toxic / spam using Cloudflare's Clef,
then write results.json and comments_report.html.

Usage:
    python classify.py            # uses clef-flash
    python classify.py clef       # uses the larger, more accurate model
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

MODEL = sys.argv[1] if len(sys.argv) > 1 else "clef-flash"
LABELS = ["acceptable", "toxic", "spam"]

creds = dict(re.findall(r'export (\w+)="([^"]*)"', open("cloud-flare.local.sh").read()))
ACCOUNT = creds["CLOUDFLARE_ACCOUNT_ID"]
TOKEN = creds["CLOUDFLARE_API_TOKEN"]
URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/@cf/cloudflare/{MODEL}"

INSTRUCTIONS = (
    "`comment` is a post written by a student in the discussion forum of a college "
    "online course on Generative AI. Decide whether it is acceptable, toxic or spam. "
    "Students often ask questions, vent about difficulty, disagree, or write informally; "
    "that alone does NOT make a comment toxic or spam."
)
CRITERIA = {
    "acceptable": (
        "A genuine comment, question, answer, opinion, complaint about the course, "
        "or criticism of ideas or of the course, even if blunt, frustrated, informal, "
        "or with spelling mistakes. Pick this unless it clearly fits toxic or spam."
    ),
    "toxic": (
        "Insults, abuse, harassment, hate or discrimination, personal attacks on a "
        "person (student, teacher or staff), threats, or deliberately demeaning language. "
        "Criticising an idea or the course politely or bluntly is NOT toxic; "
        "attacking people is."
    ),
    "spam": (
        "Promotion or advertising, unrelated links, offers, referral or discount codes, "
        "requests to contact or join something elsewhere, get-rich-quick or "
        "certificate-selling content, or repeated/meaningless gibberish posted to "
        "gain attention rather than to discuss the course."
    ),
}


def call_clef(text, retries=5):
    payload = {
        "state": {"comment": text},
        "questions": {
            "label": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}
        },
    }
    for attempt in range(retries):
        req = urllib.request.Request(
            URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            if not data.get("success"):
                raise RuntimeError(data.get("errors"))
            return data["result"]["answers"]["label"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise RuntimeError("Too many retries")


def get_id_text(c, i):
    """Be tolerant of different JSON field names."""
    cid = c.get("id", c.get("comment_id", i + 1))
    text = c.get("text") or c.get("comment") or c.get("body") or c.get("content") or ""
    return cid, text


def main():
    comments = json.load(open("comments.json", encoding="utf-8"))
    if isinstance(comments, dict):  # e.g. {"comments": [...]}
        comments = next(v for v in comments.values() if isinstance(v, list))

    results = []
    for i, c in enumerate(comments):
        cid, text = get_id_text(c, i)
        ans = call_clef(text)
        results.append({
            "id": cid,
            "text": text,
            "label": ans["choice"],
            "confidence": ans.get("confidence"),
            "probabilities": ans.get("probabilities"),
        })
        print(f"{cid}: {ans['choice']} (conf {ans.get('confidence')})")

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "results": results}, f, indent=2, ensure_ascii=False)

    write_html(results)
    print("Wrote results.json and comments_report.html")


def write_html(results):
    counts = {l: sum(r["label"] == l for r in results) for l in LABELS}
    rows = []
    for r in results:
        conf = r["confidence"]
        low = conf is not None and conf < 0.4
        probs = " · ".join(f"{k} {v:.2f}" for k, v in (r["probabilities"] or {}).items())
        rows.append(
            f'<tr data-label="{r["label"]}" class="{"low" if low else ""}">'
            f'<td>{html.escape(str(r["id"]))}</td>'
            f'<td>{html.escape(r["text"])}</td>'
            f'<td><span class="pill {r["label"]}">{r["label"]}</span></td>'
            f'<td>{"" if conf is None else f"{conf:.2f}"}{" ⚠" if low else ""}'
            f'<div class="probs">{probs}</div></td></tr>'
        )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clef comment classification ({MODEL})</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#222}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{padding:.5rem .6rem;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}
 th{{position:sticky;top:0;background:#f6f6f6}}
 .pill{{padding:.15rem .6rem;border-radius:999px;font-size:.85rem;font-weight:600}}
 .acceptable{{background:#d9f2dd;color:#14532d}}
 .toxic{{background:#fddcdc;color:#7f1d1d}}
 .spam{{background:#fdecc8;color:#78350f}}
 tr.low{{background:#fffbea}}
 .probs{{font-size:.75rem;color:#777}}
 button{{margin:0 .3rem .8rem 0;padding:.35rem .8rem;border:1px solid #bbb;border-radius:6px;background:#fff;cursor:pointer}}
 button.on{{background:#222;color:#fff}}
</style></head><body>
<h1>Forum comments classified by Clef</h1>
<p>Model: <b>{MODEL}</b> · Total {len(results)} · acceptable {counts["acceptable"]} ·
toxic {counts["toxic"]} · spam {counts["spam"]}. ⚠ = low confidence (below 0.40), worth a close look.</p>
<div id="filters">
 <button class="on" data-f="all">All</button>
 <button data-f="acceptable">Acceptable</button>
 <button data-f="toxic">Toxic</button>
 <button data-f="spam">Spam</button>
 <button data-f="low">Low confidence</button>
</div>
<table><thead><tr><th>ID</th><th>Comment</th><th>Clef label</th><th>Confidence</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table>
<script>
document.querySelectorAll('#filters button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('#filters button').forEach(x => x.classList.remove('on'));
  b.classList.add('on');
  const f = b.dataset.f;
  document.querySelectorAll('tbody tr').forEach(tr => {{
    tr.style.display = (f==='all' || tr.dataset.label===f || (f==='low' && tr.classList.contains('low'))) ? '' : 'none';
  }});
}});
</script></body></html>"""
    with open("comments_report.html", "w", encoding="utf-8") as f:
        f.write(page)


if __name__ == "__main__":
    main()

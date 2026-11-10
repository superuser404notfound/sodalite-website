#!/usr/bin/env python3
"""Renders _src/page.html once per language from _src/strings/<code>.json.

  python3 _tools/build.py

English goes to /index.html (x-default), every other language to /<code>/index.html.
A missing or extra key, or markup other than <em>, <strong> and <a href>, stops the build.
"""
import datetime
import hashlib
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from locales import ALIASES, ENDONYMS, LOCALES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://sodalite.superuser404.de"
ALLOWED_TAG = re.compile(r"</?(em|strong)>|<a href=\"https://[^\"]+\">|</a>")

STRIPS = {
    "tv": (6, 1400, 788),
    "iphone": (6, 480, 1043),
    "ipad": (5, 1000, 750),
    "mac": (5, 1200, 750),
}
SETTINGS = ["accent", "appearance", "home", "controls", "playback", "tabs"]


def url_for(code):
    return f"{SITE}/" if code == "en" else f"{SITE}/{code.lower()}/"


def base_for(code):
    return "/" if code == "en" else f"/{code.lower()}/"


def check_markup(code, key, value):
    rest = ALLOWED_TAG.sub("", value)
    if "<" in rest or ">" in rest:
        raise SystemExit(f"{code}.json: {key} has markup that is not allowed: {value!r}")


def plain(value):
    return html.escape(re.sub(r"<[^>]+>", "", value), quote=True)


def redirect_script():
    table = json.dumps({"codes": [c.lower() for c in LOCALES], "alias": ALIASES}, separators=(",", ":"))
    return (
        f'<script type="application/json" id="langs">{table}</script>\n'
        "<script>\n"
        "(function () {\n"
        "  var stored = null;\n"
        "  try { stored = localStorage.getItem('lang'); } catch (e) {}\n"
        "  if (stored) return;\n"
        "  var t = JSON.parse(document.getElementById('langs').textContent);\n"
        "  var tags = navigator.languages || [navigator.language || ''];\n"
        "  for (var i = 0; i < tags.length; i++) {\n"
        "    var parts = String(tags[i]).toLowerCase().replace(/_/g, '-').split('-');\n"
        "    for (var n = parts.length; n > 0; n--) {\n"
        "      var c = parts.slice(0, n).join('-');\n"
        "      var hit = t.codes.indexOf(c) >= 0 ? c : t.alias[c];\n"
        "      if (hit) { if (hit !== 'en') location.replace('/' + hit + '/'); return; }\n"
        "    }\n"
        "  }\n"
        "})();\n"
        "</script>"
    )


def strip_html(code, s):
    shots = f"/media/shots/{code.lower()}/"
    out = {}
    for slot, (count, w, h) in STRIPS.items():
        name = s[f"platform_{slot}"]
        alt = plain(s["shot_alt"].replace("%s", name))
        out[f"strip_{slot}"] = "".join(
            f'<img src="{shots}{slot}-{n}.webp" alt="{alt}" width="{w}" height="{h}" loading="lazy">'
            for n in range(1, count + 1)
        )
    return out


def settings_html(s):
    items = []
    for page in SETTINGS:
        label = s[f"settings_{page}"]
        alt = plain(s["settings_alt"].replace("%s", label))
        items.append(
            f'<figure><img src="/media/ui/tvos-settings-{page}.webp" alt="{alt}" width="1400" '
            f'height="{788}" loading="lazy"><figcaption>{html.escape(label)}</figcaption></figure>'
        )
    return "".join(items)


def render(template, code, strings, version):
    values = {}
    for k, v in strings.items():
        check_markup(code, k, v)
        values[k] = v
    for k in ("meta_title", "meta_description"):
        values[k] = plain(strings[k])
    values.update(strip_html(code, strings))
    values["settings_strip"] = settings_html(strings)
    values.update({
        "lang": code,
        "canonical": url_for(code),
        "base": base_for(code),
        "shots": f"/media/shots/{code.lower()}/",
        "endonym": ENDONYMS[code],
        "version": version,
        "year": str(datetime.date.today().year),
        "redirect": redirect_script() if code == "en" else "",
        "hreflang": "\n".join(
            [f'<link rel="alternate" hreflang="{c}" href="{url_for(c)}">' for c in LOCALES]
            + [f'<link rel="alternate" hreflang="x-default" href="{url_for("en")}">']
        ),
        "langmenu": "".join(
            f'<li><a href="{base_for(c)}" hreflang="{c}" lang="{c}"'
            + (' aria-current="page"' if c == code else "")
            + f">{ENDONYMS[c]}</a></li>"
            for c in LOCALES
        ),
    })

    def sub(m):
        key = m.group(1)
        if key not in values:
            raise SystemExit(f"template placeholder {{{{{key}}}}} has no value for {code}")
        return values[key]

    return re.sub(r"\{\{([a-z0-9_]+)\}\}", sub, template)


def main():
    template = open(os.path.join(ROOT, "_src", "page.html"), encoding="utf-8").read()
    sdir = os.path.join(ROOT, "_src", "strings")
    en = json.load(open(os.path.join(sdir, "en.json"), encoding="utf-8"))
    used = set(re.findall(r"\{\{([a-z0-9_]+)\}\}", template))
    css = open(os.path.join(ROOT, "style.css"), "rb").read()
    version = hashlib.sha1(css).hexdigest()[:8]

    built = 0
    for code in LOCALES:
        path = os.path.join(sdir, f"{code}.json")
        if not os.path.exists(path):
            print(f"skip {code}: no strings yet")
            continue
        strings = json.load(open(path, encoding="utf-8"))
        missing = set(en) - set(strings)
        extra = set(strings) - set(en)
        if missing or extra:
            raise SystemExit(f"{code}.json: missing {sorted(missing)}, extra {sorted(extra)}")
        out = os.path.join(ROOT, "index.html") if code == "en" else os.path.join(ROOT, code.lower(), "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(render(template, code, strings, version))
        built += 1
    unused = set(en) - used - {f"platform_{p}" for p in STRIPS} - {"shot_alt", "settings_alt"} - {f"settings_{p}" for p in SETTINGS}
    if unused:
        print(f"warning: strings not used by the template: {sorted(unused)}")
    print(f"built {built} page(s)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validates the built site. Exit 0 when clean, 1 with a list of failures otherwise.

Run from the repo root: python3 _tools/check.py
"""
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from locales import LOCALES, resolve_language  # noqa: E402

FORBIDDEN = ["truehd atmos", "lossless truehd", "lossless dts", "lossless object audio", "atmos from truehd"]
MAC_FORBIDDEN = ["Dolby Vision", "Multiview", "Top Shelf", "AirPlay"]
PAGE_IMAGE_BUDGET = 2_500_000
IMAGE_LIMIT = 200_000

failures = []


def fail(where, reason):
    failures.append(f"{where}: {reason}")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.canonical = []
        self.hreflang = {}
        self.refs = []
        self.images = []
        self.text = []
        self.mac_text = []
        self._skip = 0
        self._mac_depth = 0
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical.append(a.get("href"))
        if tag == "link" and a.get("rel") == "alternate" and "hreflang" in a:
            self.hreflang[a["hreflang"]] = a.get("href")
        for key in ("href", "src"):
            if a.get(key):
                self.refs.append(a[key])
        if tag == "img" and a.get("src"):
            self.images.append(a["src"])
        if tag == "source" and a.get("srcset"):
            self.refs.append(a["srcset"].split()[0])
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("br", "img", "meta", "link", "input", "source", "hr"):
            return
        self._stack.append(tag)
        if self._mac_depth:
            self._mac_depth += 1
        elif a.get("data-platform") == "mac":
            self._mac_depth = 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1
        if self._stack:
            self._stack.pop()
            if self._mac_depth:
                self._mac_depth -= 1

    def handle_data(self, data):
        if self._skip:
            return
        self.text.append(data)
        if self._mac_depth:
            self.mac_text.append(data)

    def handle_comment(self, data):
        pass


def page_path(code):
    return os.path.join(ROOT, "index.html") if code == "en" else os.path.join(ROOT, code.lower(), "index.html")


def page_url(code):
    return "https://sodalite.superuser404.de/" if code == "en" else f"https://sodalite.superuser404.de/{code.lower()}/"


def resolve_local(page_file, ref):
    u = urlparse(ref)
    if u.scheme or ref.startswith("#") or ref.startswith("mailto:"):
        return None
    path = u.path
    if path.startswith("/"):
        target = os.path.join(ROOT, path.lstrip("/"))
    else:
        target = os.path.join(os.path.dirname(page_file), path)
    target = os.path.normpath(target)
    if os.path.isdir(target):
        target = os.path.join(target, "index.html")
    if not os.path.exists(target) and os.path.exists(target + ".html"):
        target += ".html"
    return target


def check_strings():
    sdir = os.path.join(ROOT, "_src", "strings")
    en_path = os.path.join(sdir, "en.json")
    if not os.path.exists(en_path):
        fail("_src/strings/en.json", "missing")
        return
    en = json.load(open(en_path, encoding="utf-8"))
    for code in LOCALES:
        p = os.path.join(sdir, f"{code}.json")
        if not os.path.exists(p):
            fail(f"_src/strings/{code}.json", "missing")
            continue
        d = json.load(open(p, encoding="utf-8"))
        for k in sorted(set(en) - set(d)):
            fail(f"_src/strings/{code}.json", f"missing key {k}")
        for k in sorted(set(d) - set(en)):
            fail(f"_src/strings/{code}.json", f"extra key {k}")
        for k, v in d.items():
            if not str(v).strip():
                fail(f"_src/strings/{code}.json", f"empty value {k}")
            tags_en = sorted(re.findall(r"</?(?:em|a|strong)\b", str(en.get(k, ""))))
            tags = sorted(re.findall(r"</?(?:em|a|strong)\b", str(v)))
            if k in en and tags != tags_en:
                fail(f"_src/strings/{code}.json", f"markup differs from en in {k}")


def check_page(code):
    path = page_path(code)
    rel = os.path.relpath(path, ROOT)
    if not os.path.exists(path):
        fail(rel, "missing")
        return
    html = open(path, encoding="utf-8").read()
    p = Page()
    p.feed(html)

    if p.lang != code:
        fail(rel, f"html lang is {p.lang!r}, expected {code!r}")
    if p.canonical != [page_url(code)]:
        fail(rel, f"canonical is {p.canonical}")
    for c in LOCALES:
        if p.hreflang.get(c) != page_url(c):
            fail(rel, f"hreflang {c} is {p.hreflang.get(c)!r}")
    if p.hreflang.get("x-default") != page_url("en"):
        fail(rel, "hreflang x-default missing or wrong")

    for ref in p.refs:
        target = resolve_local(path, ref)
        if target is not None and not os.path.exists(target):
            fail(rel, f"broken local link {ref}")

    text = "".join(p.text)
    if "{{" in html:
        fail(rel, "unrendered placeholder")
    if "—" in html:
        fail(rel, "em-dash")
    if re.search(r"\S - \S", text):
        fail(rel, "spaced hyphen used as a dash: " + re.search(r".{0,30}\S - \S.{0,30}", text).group(0))
    low = text.lower()
    for f in FORBIDDEN:
        if f in low:
            fail(rel, f"forbidden wording {f!r}")
    mac = "".join(p.mac_text)
    if not mac.strip():
        fail(rel, "no data-platform=mac section")
    for f in MAC_FORBIDDEN:
        if f.lower() in mac.lower():
            fail(rel, f"mac section claims {f!r}")

    total = 0
    for src in set(p.images):
        target = resolve_local(path, src)
        if target and os.path.exists(target):
            size = os.path.getsize(target)
            total += size
            if size > IMAGE_LIMIT and not src.endswith(".svg"):
                fail(rel, f"image over {IMAGE_LIMIT} bytes: {src} ({size})")
    if total > PAGE_IMAGE_BUDGET:
        fail(rel, f"page images total {total} bytes, budget {PAGE_IMAGE_BUDGET}")


def check_resolver():
    cases = {
        "pt-PT": "pt-PT", "pt": "pt-BR", "pt-BR": "pt-BR", "zh-TW": "zh-Hant", "zh-HK": "zh-Hant",
        "zh-Hant-TW": "zh-Hant", "zh": "zh-Hans", "zh-CN": "zh-Hans", "no": "nb", "nn": "nb",
        "nb-NO": "nb", "de-AT": "de", "en-GB": "en", "ar": "en", "": "en",
    }
    for tag, want in cases.items():
        got = resolve_language(tag)
        if got != want:
            fail("resolver", f"{tag!r} -> {got!r}, expected {want!r}")
    idx = page_path("en")
    if os.path.exists(idx):
        html = open(idx, encoding="utf-8").read()
        m = re.search(r'<script type="application/json" id="langs">(.*?)</script>', html, re.S)
        if not m:
            fail("index.html", "language table for the redirect missing")
        else:
            from locales import ALIASES
            data = json.loads(m.group(1))
            if data.get("codes") != [c.lower() for c in LOCALES] or data.get("alias") != ALIASES:
                fail("index.html", "redirect language table differs from _tools/locales.py")


def main():
    check_strings()
    for code in LOCALES:
        check_page(code)
    check_resolver()
    for f in ("privacy.html", "imprint.html", "logo.png", "CNAME"):
        if not os.path.exists(os.path.join(ROOT, f)):
            fail(f, "missing")
    if failures:
        print("\n".join(failures))
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("site check: all clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

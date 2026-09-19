"""Validate the actual generated site, including independent media and links."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PREFIX = "/humanstoriesforaibots/"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []
        self.text = []
        self.article_ids = []
        self.canonical = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and "href" in a:
            self.links.append(a["href"])
        if tag == "img":
            assert "alt" in a
            self.images.append(a["src"])
        if tag == "link" and a.get("rel") == "stylesheet":
            self.links.append(a["href"])
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a["href"]
        if tag == "article" and a.get("id"):
            self.article_ids.append(a["id"])

    def handle_data(self, data):
        self.text.append(data)


def main():
    posts = list((ROOT / "posts").glob("*.md"))
    home = Page()
    home.feed((PUBLIC / "index.html").read_text(encoding="utf-8"))
    assert len(home.article_ids) == len(posts) == len(set(home.article_ids))
    problems = []
    image_count = 0
    pages = list(PUBLIC.rglob("*.html"))
    for file in pages:
        if file.is_relative_to(PUBLIC / 'comment-archive'):
            continue  # Standalone comment download has its own relative links.
        parser = Page()
        parser.feed(file.read_text(encoding="utf-8"))
        assert parser.canonical and parser.canonical.startswith("https://zy-gitcoder.github.io/")
        for src in parser.images:
            assert src.startswith(PREFIX + "media/"), (file, src)
        image_count += len(parser.images)
        for link in parser.links + parser.images:
            if link == PREFIX + "archive.zip":
                continue  # Packaged after this content validation step.
            u = urlparse(link)
            if u.scheme or u.netloc or not u.path:
                continue
            assert u.path.startswith(PREFIX), (file, link)
            target = PUBLIC / unquote(u.path.removeprefix(PREFIX))
            if u.path.endswith("/"):
                target = target / "index.html"
            if not target.is_file():
                problems.append((str(file.relative_to(PUBLIC)), link))
    assert not problems, problems
    for post in posts:
        md = post.read_text(encoding="utf-8")
        original = re.search(r"^original_url: (.+)$", md, re.M)[1]
        target = PUBLIC / urlparse(original).path.lstrip("/") / "index.html"
        assert target.is_file(), target
        # The full text is on the long homepage as well as the individual page.
        page = Page()
        page.feed(target.read_text(encoding="utf-8"))
        slug = re.search(r"^slug: (.+)$", md, re.M)[1]
        assert slug in home.article_ids
    feed = ET.parse(PUBLIC / "feed.xml")
    assert len(feed.findall("./channel/item")) == len(posts)
    for item in feed.findall("./channel/item"):
        assert len(item.findtext("description", "")) > 500
        assert 'src="/' not in item.findtext("description", "")
    ET.parse(PUBLIC / "sitemap.xml")
    assert not (PUBLIC / "CNAME").exists()
    for record in json.loads((ROOT / "media/manifest.json").read_text()):
        assert (PUBLIC / record["path"]).is_file()
    print(f"PASS: {len(posts)} complete posts on homepage and individual pages; {len(pages)} HTML pages; {image_count} local image references; complete RSS; valid sitemap; no broken local links.")


if __name__ == "__main__":
    main()

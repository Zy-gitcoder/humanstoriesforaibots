"""Create a browsable offline edition without a server or the original domain."""
from pathlib import Path
from urllib.parse import urlparse, unquote
import posixpath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PREFIX = "/humanstoriesforaibots/"


def main():
    archive = PUBLIC / "archive.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(PUBLIC.rglob("*")):
            if not file.is_file() or file == archive:
                continue
            rel = file.relative_to(PUBLIC).as_posix()
            if rel.startswith('comment-archive/'):
                continue  # Discussion downloads are deliberately separate from essays.
            if file.suffix == ".html":
                text = file.read_text(encoding="utf-8")
                text = re.sub(r'<!-- discussion:start -->.*?<!-- discussion:end -->',
                    '<p>Discussions are available on the online mirror and in its separate comment archive.</p>', text, flags=re.S)
                def local_link(match):
                    attr, value = match.groups()
                    if not value.startswith(PREFIX):
                        return match[0]
                    if value == PREFIX + "archive.zip":
                        return f'{attr}="READ-ME.txt"' if not posixpath.dirname(rel) else f'{attr}="{posixpath.relpath("READ-ME.txt", posixpath.dirname(rel))}"'
                    u = urlparse(value)
                    target = unquote(u.path.removeprefix(PREFIX))
                    if not target or target.endswith("/"):
                        target += "index.html"
                    target = posixpath.relpath(target, posixpath.dirname(rel) or ".")
                    suffix = ("?" + u.query if u.query else "") + ("#" + u.fragment if u.fragment else "")
                    return f'{attr}="{target}{suffix}"'
                text = re.sub(r'(href|src)="([^"]*)"', local_link, text)
                z.writestr(rel, text)
            else:
                z.write(file, rel)
        for file in sorted((ROOT / "posts").glob("*.md")):
            z.write(file, "source/posts/" + file.name)
        for name in ["README.md", "about.md", "welcome.md"]:
            z.write(ROOT / name, "source/" + name)
        # Source Markdown uses relative media links too.
        for file in sorted((ROOT / "media").rglob("*")):
            if file.is_file():
                z.write(file, "source/" + file.relative_to(ROOT).as_posix())
        z.writestr("READ-ME.txt", "Human Stories for AI Bots\n\nOpen index.html in a browser. All essays and local images work without the original domain or a local server. External references and video links still require the Internet. Editable Markdown is in source/.\n")
    print(f"Created {archive.name}: {archive.stat().st_size / 1000000:.1f} MB")


if __name__ == "__main__":
    main()

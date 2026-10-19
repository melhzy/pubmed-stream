"""Build the documentation site from the repository's own files.

MkDocs reads pages from one folder, but pubmed-stream's documentation lives
where GitHub shows it: the README, tutorials/, docs/ and the changelog.  These
hooks add those files to the site in place, so nothing is copied or kept twice,
and fix the links that only work on GitHub:

- a link to a page of the site, written as a GitHub address (the README's
  links are, so they work on PyPI too), becomes a link within the site;
- a link to a file that is not a page, such as a script, goes to GitHub;
- a GitHub alert (``> [!IMPORTANT]``) becomes an admonition;
- a list right after a line of text, which GitHub allows, gets the blank line
  before it that MkDocs needs.
"""

import posixpath
import re
from pathlib import Path

from mkdocs.plugins import event_priority
from mkdocs.structure.files import File

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/melhzy/pubmed-stream"
BLOB, TREE = f"{REPO}/blob/main/", f"{REPO}/tree/main/"

# Repository files that become the site, by glob; the README is the home page
SOURCES = ["CHANGELOG.md", "docs/ARCHITECTURE.md", "docs/figures/*.png", "tutorials/*.md",
           "tutorials/*.ipynb", "tutorials/guides/*.md", "tutorials/guides/images/*.png"]
HOME = "index.md"

LINK = re.compile(r"(\]\()([^)\s]+)(\))")
ALERT = re.compile(r"^> \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\n((?:>.*\n?)*)", re.MULTILINE)
ALERT_KIND = {"NOTE": "note", "TIP": "tip", "IMPORTANT": "important", "WARNING": "warning",
              "CAUTION": "danger"}


def _site_path(repo_path):
    """Where a repository file is on the site, or None when it is not part of it."""
    if repo_path == "README.md":
        return HOME
    if repo_path == "tutorials" or repo_path == "tutorials/":
        return "tutorials/README.md"
    return repo_path if (ROOT / repo_path).is_file() and any(
        Path(repo_path).match(g) for g in SOURCES) else None


def _repo_path(src_uri):
    return "README.md" if src_uri == HOME else src_uri


@event_priority(100)   # before mkdocs-jupyter, which turns the notebooks into pages
def on_files(files, config):
    readme = File.generated(config, HOME, abs_src_path=str(ROOT / "README.md"))
    readme.edit_uri = "README.md"
    files.append(readme)
    for pattern in SOURCES:
        for path in sorted(ROOT.glob(pattern)):
            files.append(File(path.relative_to(ROOT).as_posix(), str(ROOT), config.site_dir,
                              config.use_directory_urls))
    return files


def _link(target, page_uri):
    """The site's version of a link written for GitHub."""
    if target.startswith((BLOB, TREE)):
        path, _, anchor = target.split("/main/", 1)[1].partition("#")
    elif "://" in target or target.startswith(("#", "mailto:")):
        return target
    else:
        path, _, anchor = target.partition("#")
        path = posixpath.normpath(posixpath.join(posixpath.dirname(_repo_path(page_uri)), path))
    anchor = "#" + anchor if anchor else ""
    site = _site_path(path)
    if site is None:
        kind = TREE if (ROOT / path).is_dir() else BLOB
        return kind + path + anchor
    return posixpath.relpath(site, posixpath.dirname(page_uri) or ".") + anchor


def _alert(match):
    body = re.sub(r"^> ?", "", match.group(2), flags=re.MULTILINE).strip("\n")
    return f"!!! {ALERT_KIND[match.group(1)]}\n\n" + "\n".join("    " + line for line in body.splitlines()) + "\n"


QUOTE = re.compile(r"^((?:> ?)*)(.*)$")
ITEM = re.compile(r"(?:[-*+]|\d+[.)])\s")


def _loosen_lists(markdown):
    """Add a blank line between a line of text and a list that follows it, in quotes too."""
    out, fence, before = [], False, ("", "")
    for line in markdown.split("\n"):
        quote, text = QUOTE.match(line).groups()
        if text.lstrip().startswith("```"):
            fence = not fence
        elif (not fence and ITEM.match(text) and before[1].strip() and not ITEM.match(before[1])
              and before[0] == quote and not before[1].startswith((" ", "|"))):
            out.append(quote.rstrip())
        out.append(line)
        before = (quote, text)
    return "\n".join(out)


def on_page_markdown(markdown, page, config, files):
    markdown = ALERT.sub(_alert, _loosen_lists(markdown))
    return LINK.sub(lambda m: m.group(1) + _link(m.group(2), page.file.src_uri) + m.group(3), markdown)


NOTEBOOK_LINK = re.compile(r'href="(?!https?:|#|mailto:)([^"#]+\.(?:md|ipynb))((?:#[^"]*)?)"')


def _notebook_link(path, anchor, page):
    link = _link(path + anchor, page.file.src_uri)
    return link if "://" in link else re.sub(r"\.(?:md|ipynb)(?=#|$)", ".html", link)


def on_post_page(html, page, config):
    """Notebook pages keep their GitHub links to .md files; point them at the site's pages, or at GitHub."""
    if page.file.src_uri.endswith(".ipynb"):
        html = NOTEBOOK_LINK.sub(lambda m: f'href="{_notebook_link(m.group(1), m.group(2), page)}"', html)
    return html

"""Hooks of MkDocs for the website of the documentation (mkdocs.yml).

The pages read the same on GitHub and on the website, with their links written for
GitHub. The hooks lead them to the pages of the website where MkDocs alone can't:

- MkDocs turns the links of the Markdown, such as [Games](games.md), into links to
  the pages of the website, but leaves the links in HTML as they are: those of a
  table, such as <a href="games.md">, would lead to the .md files there, which the
  website doesn't have. They get the address of the page, as the Markdown does.
- README.md and README.de.md are the start pages on GitHub and stay off the
  website, which starts with index.md and index.de.md. A link to them leads to the
  start page of the website.
- The pages of the further languages sit next to the English ones, named like them
  with their language, such as games.de.md next to games.md and index.nl.md next to
  index.md, and the plugin i18n builds the website of each language in its folder,
  such as de/ and nl/, with the English page where the language has none. Each
  website is built on its own and knows only its own pages, so a link to another
  language, such as [Deutsch](games.de.md) on an English page or [English](faq.md)
  on a Dutch one, leads to that page of the other website. So do the links of an
  English page on the website of a further language that has a page of their own:
  their anchors are those of the English pages.
- A page of a further language lies one folder deeper than its file, such as in
  de/, so the pictures of its HTML, such as <img src="images/de/card.png">, get the
  path from there, as those of the Markdown do.
- A page on GitHub starts with a line back to the overview, often with the links to
  the other languages, such as [← Documentation](README.md) · [Deutsch](faq.de.md)
  · [Nederlands](faq.nl.md). The website has its menu, its tabs and the switch of
  the language for that, so it leaves the line out.
- A further language may show an English page for want of its own, such as the
  Dutch website most pages. The language may give such a page a note in its own
  words, with a link to where native speakers help to translate it: extra.
  untranslated of its section in mkdocs.yml. The hooks of the blueprint mark the
  text of such a page as English, so that screen readers read it with an English
  voice; the note keeps the language of the website.
- A page may include a whole file of the repository, as changelog.md includes
  CHANGELOG.md with the line --8<-- "CHANGELOG.md", so that nothing is written
  twice. The links of that file are written from its own folder, such as
  [games](docs/games.md) from the root: they lead to the pages of the website, and
  to GitHub for the other files of the repository. The pencil of a page that is
  nothing but the file edits that file.
- The live demo in demo/ plays the cards of the integration, which the website
  takes from the integration as they are, so that it always shows the cards of its
  version: after the build, they join the page of the demo.

They also give search engines and the previews of shared links what they need:

- A start page is titled with the name of the website alone. Material does so on
  the English one, but titles the others after their tab, such as "Start -
  HomeDarts for Autodarts" the German one.
- A page that moved, such as LOCAL-CONTROL.md, keeps the old links of GitHub
  working. Its front matter names the page that took its place, moved:
  installation.md, and the hooks make it lead there at once, in the language of
  its website: search engines take that page for it and leave the old one out, and
  so does the search of the website.
- A page that asks search engines to leave it out, with <meta name="robots"
  content="noindex">, leaves the sitemap too, which lists the pages to index.

A link to a page that doesn't exist fails the build, as it does in the Markdown.
"""

from __future__ import annotations

import gzip
import logging
import posixpath
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

# The warnings of MkDocs, which mkdocs build --strict counts.
log = logging.getLogger("mkdocs.hooks.html_links")

# The language of the pages without a language in their name, and the further ones
# of the plugin i18n in mkdocs.yml, whose pages are named with it, such as
# games.de.md and index.nl.md.
ENGLISH = "en"
GERMAN = "de"
FURTHER = (GERMAN, "nl", "fr", "es")
# The language in the name of a page of a further language, such as .nl.md.
NAMED = re.compile(rf"\.({'|'.join(FURTHER)})\.md$")
# The start pages on GitHub, and those of the website that take their place. Only
# German has an overview of its own on GitHub.
START = {"README.md": "index.md", f"README.{GERMAN}.md": f"index.{GERMAN}.md"}
# The start page of the website in each language.
HOMES = {"index.md", *(f"index.{language}.md" for language in FURTHER)}
# The setting of a further language in extra of mkdocs.yml with the note on a page
# that it shows in English: its text and the name and address of its link.
UNTRANSLATED = "untranslated"
# The note, an admonition of Material without a title, in the language of the
# website, after the title of the page.
NOTE = (
    '<div class="admonition info untranslated" lang="{language}">'
    '<p>{text} <a href="{href}">{link}</a></p></div>'
)
TITLE_HEADING = re.compile(r"<h1\b.*?</h1>", re.DOTALL)
# A version of a page in another language in its head, which the plugin i18n writes.
VERSION = re.compile(r'<link\b[^>]*\brel="alternate"[^>]*\bhreflang="[^"]*"[^>]*>\s*')

# The cards of the integration with the texts they import, and where the live demo
# loads them from.
CARDS = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "homedarts"
    / "frontend"
    / "homedarts-card.js"
)
CARD_TEXTS = CARDS.parent / "text"
DEMO = "demo"

# The key of the front matter of a page that moved, with the page that took its
# place, and the one that the hooks give it with the address of that page.
MOVED_TO = "moved"
REDIRECT = "redirect"
# The head of a page that moved, as the redirects of MkDocs have it: search engines
# leave it out and follow its links, and the browser goes on to the address at once.
REDIRECT_HEAD = (
    '<meta name="robots" content="noindex, follow">'
    '<meta http-equiv="refresh" content="0; url={address}">'
)
# The title of a page, and the titles of the previews of a shared link, which the
# social plugin of Material writes.
TITLE = re.compile(r"<title>[^<]*</title>")
SHARED_TITLE = re.compile(r'(<meta property="(?:og|twitter):title" content=")[^"]*"')
# The canonical address of a page, which Material writes in its head.
CANONICAL = re.compile(r'(<link rel="canonical" href=")([^"]*)"')
# A page that asks search engines to leave it out.
NOINDEX = re.compile(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', re.I)
# A page in the sitemap: its address and everything else MkDocs says about it.
LISTED = re.compile(r"[ \t]*<url>\s*<loc>([^<]+)</loc>.*?</url>[ \t]*\n?", re.DOTALL)

# An address that is no relative path: with a scheme, from the root, or an anchor.
ABSOLUTE = re.compile(r"[a-z][a-z0-9+.-]*:|/|#", re.IGNORECASE)
# A relative link in HTML to a Markdown file, with an optional anchor.
LINK = re.compile(r'href="(?![a-z][a-z0-9+.-]*:|/|#)([^"#]+\.md)(#[^"]*)?"')
# In the Markdown: code, whose links are examples; a relative link to a Markdown
# file, with an optional anchor, where a picture is no link; or an address in HTML.
SOURCE = re.compile(
    r"(?P<code>^[ \t]*(?P<fence>```|~~~).*?^[ \t]*(?P=fence)|`[^`\n]*`)"
    r"|(?<!!)\[(?P<text>(?:[^\[\]]|\[[^\]]*\])*)\]"
    r"\((?![a-z][a-z0-9+.-]*:|/|#)(?P<path>[^)\s#]+\.md)(?P<anchor>#[^)\s]*)?\)"
    r"|\b(?P<attribute>src|srcset|href)=(?P<quote>[\"'])(?P<value>[^\"']*)(?P=quote)",
    re.MULTILINE | re.DOTALL,
)
# The line back to the overview of GitHub at the start of a page, after its title,
# with the links to the other languages if there are some, as a paragraph of its own.
BACK = re.compile(
    r"(?P<title>\A\s*(?:#[ \t][^\n]*\n)?)\s*"
    rf"\[← [^\]\n]+\]\((?:\.\./)?README(?:\.(?:{'|'.join(FURTHER)}))?\.md\)"
    r"(?: · \[[^\]\n]+\]\([^)\s]+\))*[ \t]*(?:\n(?=[ \t]*\n)|\n?\Z)"
)
# A line that includes a whole file with pymdownx.snippets, by its path from the
# root of the repository, such as --8<-- "CHANGELOG.md"; a section of a file, such
# as "docs/README.md:languages", is left to snippets.
INCLUDE = re.compile(r'^--8<-- "(?P<path>[^":]+\.md)"[ \t]*$', re.MULTILINE)
# In an included file: code, whose links are examples, or the relative address of
# a link or picture of the Markdown, of a link reference or of the HTML, without
# its anchor.
INCLUDED = re.compile(
    r"(?P<code>^[ \t]*(?P<fence>```|~~~).*?^[ \t]*(?P=fence)|`[^`\n]*`)"
    r"|(?P<before>\]\(|^[ \t]*\[[^\]\n]+\]:[ \t]*|\b(?:src|href)=[\"'])"
    r"(?![a-z][a-z0-9+.-]*:|/|#)(?P<path>[^)\s\"'#?]+)",
    re.MULTILINE | re.DOTALL,
)
# The branch whose files the links to GitHub show.
BRANCH = "main"


def website(page: Any) -> str:
    """The language of the website that page is built for, by its address: the
    further one of its folder, such as de/games.html, or English."""
    folder = page.file.url.partition("/")[0]
    return folder if folder in FURTHER else ENGLISH


def language_of(path: str) -> str:
    """The language of a file of docs/ by its name: the further one that names it,
    such as games.de.md, or English, such as games.md."""
    named = NAMED.search(path)
    return named[1] if named else ENGLISH


def english(path: str) -> str:
    """The English file of docs/ of a page in any language: games.md of games.de.md."""
    return NAMED.sub(".md", path)


def in_language(path: str, language: str) -> str:
    """The file of docs/ of the English page path in language: games.nl.md of games.md."""
    if language == ENGLISH:
        return path
    return f"{path.removesuffix('.md')}.{language}.md"


def relative(target: str, source: str) -> str:
    """The path target as a link of the file source needs it."""
    return posixpath.relpath(target, posixpath.dirname(source) or ".")


def linked(page: Any, path: str) -> str:
    """The file of docs/ that a link of page leads to."""
    return posixpath.normpath(
        posixpath.join(posixpath.dirname(page.file.src_uri), path)
    )


def other_language(page: Any, target: str, docs: Path) -> str | None:
    """The address of target for a link of page, if target is in another language.

    A page named with a further language, such as .de, is in that language. A page
    without one is English if the website of page has a page of its name in its
    own language; otherwise the website shows it in English, and a link to it stays
    on the website of page. The addresses are those of use_directory_urls: false,
    as the blueprint sets it.
    """
    theirs, ours = language_of(target), website(page)
    if theirs == ENGLISH and (
        ours == ENGLISH or not (docs / in_language(target, ours)).is_file()
    ):
        return None
    if theirs == ours:
        return None
    if not (docs / target).is_file():
        log.warning("%s links to %s, which isn't a page", page.file.src_uri, target)
        return None
    folder = "" if theirs == ENGLISH else f"{theirs}/"
    address = f"{folder}{english(target).removesuffix('.md')}.html"
    return relative(address, page.file.url)


def moved(page: Any, address: str) -> str:
    """A relative address of the HTML of page, from where the website puts page."""
    path, *rest = re.split(r"(?=[#?])", address, maxsplit=1)
    if not path or ABSOLUTE.match(path):
        return address
    return relative(linked(page, path), page.file.url) + "".join(rest)


def lead_on(page: Any, docs: Path, files: Any) -> None:
    """Let a page that moved lead to the page that took its place.

    The successor is the one of the website of page: on the German website its
    German page, if there is one, and so on. The head of page leads there
    (on_post_page), and the search of the website leaves page out.
    """
    target = linked(page, page.meta[MOVED_TO])
    own = in_language(target, website(page))
    if (docs / own).is_file():
        target = own
    found = files.get_file_from_path(target)
    if found is None:
        log.warning(
            "%s moved to %s, which isn't a page",
            page.file.src_uri,
            page.meta[MOVED_TO],
        )
        return
    page.meta[REDIRECT] = found.url_relative_to(page.file)
    page.meta["search"] = {"exclude": True}


def include(markdown: str, page: Any, config: Any) -> str:
    """The Markdown of page with the whole files of the repository that it includes.

    The links of such a file are written from its own folder. A link to a file of
    docs/ gets the path from page, which MkDocs and on_page_markdown then lead to
    the page of the website; a link to another file of the repository leads to the
    file on GitHub. A page that is nothing but one file is edited in that file.
    """
    docs = Path(config.docs_dir)
    folder = f"{docs.name}/"

    def expand(match: re.Match[str]) -> str:
        path = match["path"]
        file = docs.parent / path
        # pymdownx.snippets fails the build for a file that doesn't exist.
        if not file.is_file():
            return match[0]

        def rebase(link: re.Match[str]) -> str:
            if link["code"]:
                return link[0]
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(path), link["path"])
            )
            if target.startswith(folder):
                address = relative(target.removeprefix(folder), page.file.src_uri)
            else:
                address = f"{config.repo_url.rstrip('/')}/blob/{BRANCH}/{target}"
            return f"{link['before']}{address}"

        return INCLUDED.sub(rebase, file.read_text(encoding="utf-8"))

    whole = INCLUDE.fullmatch(markdown.strip())
    own = f"{folder}{page.file.src_uri}"
    if (
        whole
        and (docs.parent / whole["path"]).is_file()
        and page.edit_url
        and page.edit_url.endswith(own)
    ):
        page.edit_url = page.edit_url.removesuffix(own) + whole["path"]
    return INCLUDE.sub(expand, markdown)


def on_page_markdown(markdown: str, page: Any, config: Any, files: Any) -> str:
    """The Markdown of the page for the website: without the line back to the
    overview of GitHub, with the files it includes and with its links for the
    website."""
    docs = Path(config.docs_dir)
    markdown = BACK.sub(lambda match: match["title"], markdown, count=1)
    if INCLUDE.search(markdown):
        markdown = include(markdown, page, config)
    if MOVED_TO in page.meta:
        lead_on(page, docs, files)
    deeper = posixpath.dirname(page.file.url) != posixpath.dirname(page.file.src_uri)

    def replace(match: re.Match[str]) -> str:
        if match.group("code"):
            return match.group(0)
        if attribute := match.group("attribute"):
            value = match.group("value")
            if not deeper or (
                attribute == "href" and value.split("#")[0].endswith(".md")
            ):
                return match.group(0)
            if attribute == "srcset":
                value = ", ".join(
                    " ".join([moved(page, part.split()[0]), *part.split()[1:]])
                    for part in value.split(",")
                    if part.strip()
                )
            else:
                value = moved(page, value)
            quote = match.group("quote")
            return f"{attribute}={quote}{value}{quote}"
        text, anchor = match.group("text"), match.group("anchor") or ""
        file = linked(page, match.group("path"))
        target = START.get(file, file)
        if (address := other_language(page, target, docs)) is not None:
            return f'<a href="{address}{anchor}">{text}</a>'
        if target != file:
            return f"[{text}]({relative(target, page.file.src_uri)}{anchor})"
        return match.group(0)

    return SOURCE.sub(replace, markdown)


def in_english(page: Any) -> bool:
    """Whether page is an English page that the website of a further language shows
    for want of a page of its own, such as games.md as nl/games.html."""
    ours = website(page)
    return ours != ENGLISH and language_of(page.file.src_uri) != ours


def untranslated(html: str, page: Any, config: Any) -> str:
    """The HTML of an English page that a further language shows for want of a page
    of its own, with the note of the language after its title, if the language has
    one.

    A page that moved has no text to read; it leads on at once.
    """
    note = (getattr(config, "extra", None) or {}).get(UNTRANSLATED)
    if not in_english(page) or MOVED_TO in page.meta or not note:
        return html
    written = NOTE.format(
        language=website(page),
        text=escape(note["text"], quote=False),
        href=escape(note["href"]),
        link=escape(note["link"], quote=False),
    )
    title = TITLE_HEADING.search(html)
    end = title.end() if title else 0
    return f"{html[:end]}{written}{html[end:]}"


def on_page_content(html: str, page: Any, config: Any, files: Any) -> str:
    """The HTML of the page, with its links to Markdown files leading to pages, and
    the note of its language on a page that it shows in English."""
    html = untranslated(html, page, config)
    docs = Path(config.docs_dir)

    def replace(match: re.Match[str]) -> str:
        path, anchor = match.group(1), match.group(2) or ""
        file = linked(page, path)
        target = START.get(file, file)
        address = other_language(page, target, docs)
        if address is None:
            found = files.get_file_from_path(target)
            if found is None:
                log.warning(
                    "%s links in its HTML to %s, which isn't a page",
                    page.file.src_uri,
                    path,
                )
                return match.group(0)
            address = found.url_relative_to(page.file)
        return f'href="{address}{anchor}"'

    return LINK.sub(replace, html)


def on_post_page(output: str, page: Any, config: Any) -> str:
    """The head of the page, for search engines and the previews of shared links.

    A start page is titled with the name of its website alone, and a page that moved
    leads to the page that took its place. A page that a further language shows in
    English is a copy of the English page and no version of its own, so it names
    none: the plugin i18n writes the versions of the English page into its head, and
    the hooks of the blueprint, which run after these, keep them where the page has
    two languages besides English.
    """
    if in_english(page):
        output = VERSION.sub("", output)
    if page.file.src_uri in HOMES:
        name = escape(config.site_name)
        output = TITLE.sub(lambda _: f"<title>{name}</title>", output, count=1)
        output = SHARED_TITLE.sub(lambda match: f'{match[1]}{name}"', output)
    if (address := page.meta.get(REDIRECT)) is not None:
        # The canonical address of the page that took its place, and not the own one,
        # which the sitemap keeps, so that unlist() finds the page there.
        output = CANONICAL.sub(
            lambda match: f'{match[1]}{escape(urljoin(match[2], address))}"', output
        )
        head = REDIRECT_HEAD.format(address=escape(address))
        output = output.replace("</head>", f"{head}</head>", 1)
    return output


def unlist(site: Path, site_url: str) -> None:
    """Leave the pages that ask search engines not to index them out of the sitemap.

    MkDocs lists every page there, in each of its languages, and writes it once as
    text and once compressed.
    """
    sitemap = site / "sitemap.xml"
    if not sitemap.is_file():
        return
    hidden = {
        urljoin(site_url, path.relative_to(site).as_posix())
        for path in site.rglob("*.html")
        if NOINDEX.search(path.read_text("utf-8").partition("</head>")[0])
    }
    listed = sitemap.read_bytes().decode("utf-8")
    kept = LISTED.sub(lambda match: "" if match[1] in hidden else match[0], listed)
    if kept == listed:
        return
    sitemap.write_bytes(kept.encode("utf-8"))
    compressed = site / "sitemap.xml.gz"
    if compressed.is_file():
        compressed.write_bytes(gzip.compress(kept.encode("utf-8"), mtime=0))


def on_post_build(config: Any) -> None:
    """The cards of the integration next to the page of the live demo, and the
    sitemap without the pages that search engines are to leave out.

    The hooks of the blueprint, listed after these in mkdocs.yml, copy the sitemap
    into every folder of pages afterwards.
    """
    site = Path(config.site_dir)
    demo = site / DEMO
    # The German website has no demo of its own; it links to the one in English.
    if (demo / "index.html").is_file():
        shutil.copyfile(CARDS, demo / CARDS.name)
        shutil.copytree(CARD_TEXTS, demo / CARD_TEXTS.name, dirs_exist_ok=True)
    unlist(site, config.site_url or "")

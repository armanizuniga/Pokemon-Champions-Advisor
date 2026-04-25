"""
Scrape a website or ingest a local markdown file into the 'vgc_web' ChromaDB collection.

Crawls all internal links from the root URL, extracts text by section,
converts tables to readable text, and stores chunks with URL metadata.
Re-run safely — already-ingested content is skipped.

Usage:
    # Scrape a website
    python scripts/ingest_web.py https://www.vgcguide.com
    python scripts/ingest_web.py https://www.vgcguide.com --paths "/introduction,/battling,/teambuilding"

    # Ingest a local markdown knowledge base
    python scripts/ingest_web.py --file data/VGC_Pokemon_Champions_Knowledge_Base.md
"""

import hashlib
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import chromadb
import click
import httpx
from bs4 import BeautifulSoup
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

COLLECTION_NAME  = "vgc_web"
MAX_SECTION_WORDS = 400
CRAWL_DELAY       = 0.5   # seconds between requests
_ROOT             = Path(__file__).parents[1]
DB_PATH           = _ROOT / "data/chromadb"


# ── URL helpers ───────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    # Drop fragment, normalize trailing slash on path
    clean = parsed._replace(fragment="", query="")
    path = clean.path.rstrip("/") or "/"
    return urlunparse(clean._replace(path=path))


def same_domain(url: str, root: str) -> bool:
    return urlparse(url).netloc == urlparse(root).netloc


def under_paths(url: str, allowed_paths: list[str]) -> bool:
    if not allowed_paths:
        return True
    path = urlparse(url).path
    return any(path.startswith(p) for p in allowed_paths)


def discover_links(soup: BeautifulSoup, current_url: str, root: str, allowed_paths: list[str]) -> list[str]:
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        full = normalize_url(urljoin(current_url, href))
        if same_domain(full, root) and under_paths(full, allowed_paths):
            links.append(full)
    return links


# ── Content extraction ────────────────────────────────────────────────────────

def table_to_text(table) -> str:
    rows = []
    for row in table.find_all("tr"):
        cells = [c.get_text(separator=" ", strip=True) for c in row.find_all(["th", "td"])]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def extract_sections(soup: BeautifulSoup, url: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (page_title, [(section_heading, section_text), ...])."""
    for tag in soup(["nav", "header", "footer", "script", "style", "aside", "noscript"]):
        tag.decompose()

    title_tag  = soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else urlparse(url).path

    main = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.find("body")
    if not main:
        return page_title, []

    sections: list[tuple[str, str]] = []
    current_heading  = page_title
    current_lines: list[str] = []

    def flush():
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((current_heading, text))

    for el in main.descendants:
        if not hasattr(el, "name") or el.name is None:
            continue

        if el.name in ("h1", "h2", "h3"):
            flush()
            current_heading = el.get_text(strip=True)
            current_lines   = []

        elif el.name == "table":
            txt = table_to_text(el)
            if txt:
                current_lines.append(txt)
            el.decompose()

        elif el.name == "img":
            alt = el.get("alt", "").strip()
            if alt:
                current_lines.append(f"[Image: {alt}]")

        elif el.name in ("p", "li"):
            txt = el.get_text(separator=" ", strip=True)
            if txt:
                current_lines.append(txt)

    flush()
    return page_title, sections


def extract_markdown_sections(md_path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Split a markdown file into (heading, content) sections on ## and ### boundaries."""
    lines         = md_path.read_text().splitlines()
    file_title    = md_path.stem.replace("_", " ")
    sections: list[tuple[str, str]] = []
    current_heading = file_title
    current_lines: list[str] = []

    def flush():
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_heading, content))

    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            flush()
            current_heading = line.lstrip("#").strip()
            current_lines   = []
        elif line.startswith("# "):
            # Top-level heading — update title context but don't start a new section
            current_heading = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    flush()
    return file_title, sections


def chunk_section(heading: str, text: str) -> list[str]:
    """Split a section into chunks if it exceeds MAX_SECTION_WORDS."""
    words = text.split()
    if len(words) <= MAX_SECTION_WORDS:
        return [f"{heading}\n{text}"]

    chunks = []
    start  = 0
    while start < len(words):
        end   = start + MAX_SECTION_WORDS
        chunk = " ".join(words[start:end])
        chunks.append(f"{heading}\n{chunk}")
        start = end
    return chunks


# ── Chunk ID ──────────────────────────────────────────────────────────────────

def make_chunk_id(url: str, section_idx: int, chunk_idx: int) -> str:
    raw = f"{url}::{section_idx}::{chunk_idx}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Main ──────────────────────────────────────────────────────────────────────

@click.command()
@click.argument("root_url", default="")
@click.option(
    "--file", "local_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Ingest a local markdown file instead of crawling a URL.",
)
@click.option(
    "--paths",
    default="",
    help='Comma-separated URL path prefixes to crawl, e.g. "/introduction,/battling"',
)
@click.option(
    "--db-dir",
    default=str(DB_PATH),
    show_default=True,
    type=click.Path(file_okay=False),
    help="ChromaDB directory.",
)
@click.option(
    "--delay",
    default=CRAWL_DELAY,
    show_default=True,
    type=float,
    help="Seconds to wait between page requests.",
)
def main(root_url: str, local_file: str | None, paths: str, db_dir: str, delay: float) -> None:
    if not root_url and not local_file:
        console.print("[red]Provide a URL to crawl or --file to ingest a local markdown file.[/red]")
        raise SystemExit(1)

    # ── ChromaDB setup (shared) ───────────────────────────────────────────────
    db_path  = Path(db_dir)
    db_path.mkdir(parents=True, exist_ok=True)
    embed_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    chroma   = chromadb.PersistentClient(path=str(db_path))
    col      = chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    existing_ids: set[str] = set(col.get(include=[])["ids"])
    console.print(f"[dim]Collection '{COLLECTION_NAME}': {col.count()} existing chunks[/dim]\n")

    # ── Local file mode ───────────────────────────────────────────────────────
    if local_file:
        md_path    = Path(local_file)
        file_title, sections = extract_markdown_sections(md_path)
        console.print(f"[bold]Ingesting:[/bold] {md_path.name}  ({len(sections)} sections)")

        ids, docs, metas = [], [], []
        total_added = total_skipped = 0

        for sec_idx, (heading, text) in enumerate(sections):
            for chunk_idx, chunk in enumerate(chunk_section(heading, text)):
                cid = make_chunk_id(str(md_path), sec_idx, chunk_idx)
                if cid in existing_ids:
                    total_skipped += 1
                    continue
                ids.append(cid)
                docs.append(chunk)
                metas.append({
                    "source_type": "knowledge_base",
                    "site":        "local",
                    "url":         str(md_path),
                    "page_title":  file_title,
                    "section":     heading,
                    "chunk_index": chunk_idx,
                })

        if ids:
            col.upsert(ids=ids, documents=docs, metadatas=metas)
            total_added = len(ids)

        console.print(f"\n[green]Done.[/green] Added [bold]{total_added}[/bold] chunks, skipped [bold]{total_skipped}[/bold] already-ingested.")
        console.print(f"Collection [cyan]{COLLECTION_NAME}[/cyan] now has [bold]{col.count()}[/bold] chunks.")
        return

    # ── Web crawl mode ────────────────────────────────────────────────────────
    root_url      = normalize_url(root_url)
    allowed_paths = [p.strip() for p in paths.split(",") if p.strip()]
    site          = urlparse(root_url).netloc

    console.print(f"[bold]Crawling:[/bold] {root_url}")
    if allowed_paths:
        console.print(f"[dim]Limiting to paths: {', '.join(allowed_paths)}[/dim]")

    # ── BFS crawl ─────────────────────────────────────────────────────────────
    visited: set[str] = set()
    queue   = deque([root_url])
    total_added = 0
    total_skipped = 0
    http_client = httpx.Client(follow_redirects=True, timeout=15)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Crawling...", total=None)

        while queue:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            progress.update(task, description=f"[dim]{url}[/dim]")

            try:
                resp = http_client.get(url)
                if resp.status_code != 200:
                    continue
                if "text/html" not in resp.headers.get("content-type", ""):
                    continue
            except Exception as e:
                console.print(f"  [yellow]Skip[/yellow] {url} — {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Discover more links
            for link in discover_links(soup, url, root_url, allowed_paths):
                if link not in visited:
                    queue.append(link)

            # Extract + chunk
            page_title, sections = extract_sections(soup, url)
            ids, docs, metas = [], [], []

            for sec_idx, (heading, text) in enumerate(sections):
                for chunk_idx, chunk in enumerate(chunk_section(heading, text)):
                    cid = make_chunk_id(url, sec_idx, chunk_idx)
                    if cid in existing_ids:
                        total_skipped += 1
                        continue
                    ids.append(cid)
                    docs.append(chunk)
                    metas.append({
                        "source_type": "web",
                        "site":        site,
                        "url":         url,
                        "page_title":  page_title,
                        "section":     heading,
                        "chunk_index": chunk_idx,
                    })

            if ids:
                col.upsert(ids=ids, documents=docs, metadatas=metas)
                total_added += len(ids)

            time.sleep(delay)

    http_client.close()

    console.print(f"\n[green]Done.[/green] Crawled [bold]{len(visited)}[/bold] pages.")
    console.print(f"Added [bold]{total_added}[/bold] chunks, skipped [bold]{total_skipped}[/bold] already-ingested.")
    console.print(f"Collection [cyan]{COLLECTION_NAME}[/cyan] now has [bold]{col.count()}[/bold] chunks.")


if __name__ == "__main__":
    main()
"""
scraper.py — BeautifulSoup4 crawlers for Ugandan tax law sources.

WHAT THIS DOES:
    Visits ULII, URA, and MoFPED websites.
    Finds pages and PDFs related to tax law.
    Downloads and saves them locally to data/raw/.

EACH FUNCTION RETURNS a list of dicts:
    {"title": "...", "source": "ulii", "path": "data/raw/...", "url": "https://...", "type": "html"|"pdf"}

HOW TO RUN:
    python scraper.py           (all three sources)
    python scraper.py --ulii    (just ULII)
"""

import os, re, sys, time
from urllib.parse import urljoin, urlparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import requests
from bs4 import BeautifulSoup
from pathlib import Path

# ── Config ────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
DELAY = 2  # seconds between requests — be respectful to servers
BASE_DIR = Path(__file__).parent.parent / "data" / "raw"
DEAD_SITES: set[str] = set()


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or parsed.path or url).lower()


def _should_skip_url(url: str) -> bool:
    return _host_from_url(url) in DEAD_SITES


def _mark_dead_site(url: str, reason: str = "") -> None:
    host = _host_from_url(url)
    if not host:
        return
    DEAD_SITES.add(host)
    if reason:
        print(f"  ⚠ Skipping dead site {host}: {reason}")
    else:
        print(f"  ⚠ Skipping dead site {host}")


def _save(content: str, folder: str, filename: str) -> str:
    path = BASE_DIR / folder / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _save_bin(content: bytes, folder: str, filename: str) -> str:
    path = BASE_DIR / folder / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower().strip())
    return re.sub(r"[\s_]+", "-", text)[:80]


# ══════════════════════════════════════════════════════════
# 1. ULII — full text of tax statutes
# ══════════════════════════════════════════════════════════

ULII_ACTS = [
    ("Income Tax Act, Cap 338",
     "https://ulii.org/akn/ug/act/1997/11/eng@2024-12-23"),
    ("Value Added Tax Act",
     "https://ulii.org/akn/ug/act/statute/1996/8/eng@2000-12-31"),
    ("Excise Duty Act, 2014",
     "https://ulii.org/akn/ug/act/2014/11/eng@2023-12-31"),
    ("Tax Procedures Code Act, 2014",
     "https://ulii.org/akn/ug/act/2014/14/eng@2023-12-31"),
    ("Stamp Duty Act, 2014",
     "https://ulii.org/akn/ug/act/2014/13/eng@2023-12-31"),
    ("Tax Appeals Tribunals Act, Cap 345",
     "https://ulii.org/akn/ug/act/1997/12/eng@2023-12-31"),
]


def scrape_ulii() -> list[dict]:
    """Download the full text of each Ugandan tax act from ULII via Firecrawl.

    ULII puts a Cloudflare interactive challenge in front of its /akn/ act
    pages that plain requests/BeautifulSoup can't get past, so this source
    goes through the Firecrawl API instead of the shared `requests` session.
    """
    print("\nScraping ULII — tax statutes...")
    results = []

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        env_file = Path(__file__).parent.parent / "env" / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("FIRECRAWL_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break

    if not api_key:
        print("  ⚠ FIRECRAWL_API_KEY not set — skipping ULII.\n")
        return results

    from firecrawl import Firecrawl
    fc = Firecrawl(api_key=api_key)

    for title, url in ULII_ACTS:
        try:
            print(f"  {title}...", end=" ", flush=True)
            doc = fc.scrape(url, formats=["markdown"])
            if doc.metadata.status_code != 200 or not doc.markdown:
                raise RuntimeError(f"HTTP {doc.metadata.status_code}")

            # Some ULII pages only render chrome around an embedded PDF
            # viewer — the "/source" endpoint serves that PDF directly and
            # Firecrawl parses it into markdown for us.
            markdown, used_url = doc.markdown, url
            if len(doc.markdown) < 5000:
                src_url = url.rstrip("/") + "/source"
                src_doc = fc.scrape(src_url, formats=["markdown"])
                if src_doc.metadata.status_code == 200 and src_doc.markdown and len(src_doc.markdown) > len(doc.markdown):
                    markdown, used_url = src_doc.markdown, src_url

            path = _save(markdown, "ulii", _slug(title) + ".md")
            results.append({"title": title, "source": "ulii",
                            "url": used_url, "path": path, "type": "md"})
            print(f"({len(markdown):,} chars)")

        except Exception as e:
            print(f" {e}")

        time.sleep(1)

    print(f"  {len(results)}/{len(ULII_ACTS)} acts scraped.\n")
    return results


# ══════════════════════════════════════════════════════════
# 2. URA — tax guides, rulings, practice notes
# ══════════════════════════════════════════════════════════

URA_BASE = "https://ura.go.ug"
URA_SEEDS = [
    "/en/legal-policy/",
    "/en/domestic-taxes/",
    "/en/domestic-taxes/tax-exemption/",
    "/en/domestic-taxes/tax-exemption/income-tax-exemption/",
    "/en/domestic-taxes/tax-exemption/withholding-tax/",
    "/en/domestic-taxes/stamp-duty/",
    "/en/domestic-taxes/objection-appeals/",
    "/en/category/legal-policy/double-taxation-agreements/",
    "/download-category/laws-and-acts/",
]


def scrape_ura() -> list[dict]:
    """Crawl URA for tax guides and download linked PDFs."""
    print("\nScraping URA — guides and rulings...")
    results, visited = [], set()

    for seed in URA_SEEDS:
        url = urljoin(URA_BASE, seed)
        if url in visited or _should_skip_url(url):
            continue
        visited.add(url)

        try:
            print(f"  {seed}...", end=" ", flush=True)
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code in (401, 403, 404):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            # Save page HTML
            title = (soup.title.string or seed).strip()
            main = soup.select_one("main") or soup.body
            if main:
                path = _save(str(main), "ura", _slug(title) + ".html")
                results.append({"title": title, "source": "ura",
                                "url": url, "path": path, "type": "html"})

            # Download linked PDFs
            for a in soup.select('a[href$=".pdf"]')[:10]:
                pdf_url = urljoin(url, a.get("href", ""))
                if pdf_url in visited or _should_skip_url(pdf_url):
                    continue
                visited.add(pdf_url)
                try:
                    pt = a.get_text(strip=True) or pdf_url.split("/")[-1]
                    pr = requests.get(pdf_url, headers=HEADERS, timeout=60)
                    if pr.status_code in (401, 403, 404):
                        raise requests.HTTPError(f"HTTP {pr.status_code}")
                    pr.raise_for_status()
                    pp = _save_bin(pr.content, "ura", _slug(pt) + ".pdf")
                    results.append({"title": pt, "source": "ura",
                                    "url": pdf_url, "path": pp, "type": "pdf"})
                    print(".", end="", flush=True)
                except Exception as e:
                    _mark_dead_site(pdf_url, str(e))
                time.sleep(DELAY)

            print(" done")
        except Exception as e:
            _mark_dead_site(url, str(e))
            print(f"error: {e}")
        time.sleep(DELAY)

    print(f"  {len(results)} items from URA.\n")
    return results


# ══════════════════════════════════════════════════════════
# 3. MoFPED — budget docs, tax policy
# ══════════════════════════════════════════════════════════

MOFPED_BASE = "https://www.finance.go.ug"
MOFPED_SEEDS = [
    "/publications",
    "/publications/budget-documents",
    "/publications/laws-regulations",
    "/publications/policy-briefs",
    "/publications/policies-guidelines",
    "/publications/ministry-circulars",
    "/publications/ministerial-policy-statements",
]


def scrape_mofped() -> list[dict]:
    """Crawl MoFPED for budget and tax policy documents."""
    print("\nScraping MoFPED — budget and tax policy...")
    results, visited = [], set()

    for seed in MOFPED_SEEDS:
        url = urljoin(MOFPED_BASE, seed)
        if url in visited or _should_skip_url(url):
            continue
        visited.add(url)

        try:
            print(f"  {seed}...", end=" ", flush=True)
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code in (401, 403, 404):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            title = (soup.title.string or seed).strip()
            main = soup.select_one("main") or soup.body
            if main:
                path = _save(str(main), "mofped", _slug(title) + ".html")
                results.append({"title": title, "source": "mofped",
                                "url": url, "path": path, "type": "html"})

            for a in soup.select('a[href$=".pdf"]')[:15]:
                pdf_url = urljoin(url, a.get("href", ""))
                if pdf_url in visited or _should_skip_url(pdf_url):
                    continue
                visited.add(pdf_url)
                try:
                    pt = a.get_text(strip=True) or pdf_url.split("/")[-1]
                    pr = requests.get(pdf_url, headers=HEADERS, timeout=60)
                    if pr.status_code in (401, 403, 404):
                        raise requests.HTTPError(f"HTTP {pr.status_code}")
                    pr.raise_for_status()
                    pp = _save_bin(pr.content, "mofped", _slug(pt) + ".pdf")
                    results.append({"title": pt, "source": "mofped",
                                    "url": pdf_url, "path": pp, "type": "pdf"})
                    print("", end="", flush=True)
                except Exception as e:
                    _mark_dead_site(pdf_url, str(e))
                time.sleep(DELAY)
            print(" done")
        except Exception as e:
            _mark_dead_site(url, str(e))
            print(f"error: {e}")
        time.sleep(DELAY)

    print(f"  {len(results)} items from MoFPED.\n")
    return results

def load_local_docs() -> list[dict]:
    """Pick up any PDFs/HTML you dropped into data/raw/local/."""
    local_dir = BASE_DIR / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for f in local_dir.iterdir():
        if f.suffix in (".pdf", ".html", ".htm", ".txt"):
            results.append({
                "title": f.stem.replace("-", " ").replace("_", " ").title(),
                "source": "local",
                "url": "",
                "path": str(f),
                "type": "pdf" if f.suffix == ".pdf" else "html",
            })
            print(f"  📁 {f.name}")

    print(f"  {len(results)} local documents found.\n")
    return results

def scrape_all() -> list[dict]:
    docs = scrape_ulii() + scrape_ura() + scrape_mofped() + load_local_docs()
    print(f"═══ TOTAL: {len(docs)} documents ═══\n")
    return docs


if __name__ == "__main__":
    import sys
    if "--ulii" in sys.argv:     scrape_ulii()
    elif "--ura" in sys.argv:    scrape_ura()
    elif "--mofped" in sys.argv: scrape_mofped()
    else:                        scrape_all()
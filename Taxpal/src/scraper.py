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

import os, re, time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# ── Config ────────────────────────────────────────────────
HEADERS = {"User-Agent": "ClauseBot/1.0 (Educational tax law research)"}
DELAY = 2  # seconds between requests — be respectful to servers
BASE_DIR = Path(__file__).parent.parent / "data" / "raw"


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
    ("Income Tax Act, Cap 340",
     "https://ulii.org/akn/ug/act/1997/11/eng@2023-07-01"),
    ("Value Added Tax Act, Cap 349",
     "https://ulii.org/akn/ug/act/1996/8/eng@2023-07-01"),
    ("Excise Duty Act, 2014",
     "https://ulii.org/akn/ug/act/2014/11/eng@2023-07-01"),
    ("Tax Procedures Code Act, 2014",
     "https://ulii.org/akn/ug/act/2014/14/eng@2023-07-01"),
    ("Stamp Duty Act, Cap 342",
     "https://ulii.org/akn/ug/act/1915/2/eng@2023-07-01"),
    ("East African Community Customs Management Act",
     "https://ulii.org/akn/ug/act/2004/1/eng@2023-07-01"),
    ("Tax Appeals Tribunal Act, Cap 345",
     "https://ulii.org/akn/ug/act/1997/12/eng@2023-07-01"),
]


def scrape_ulii() -> list[dict]:
    """Download the full text of each Ugandan tax act from ULII."""
    print("\nScraping ULII — tax statutes...")
    results = []

    for title, url in ULII_ACTS:
        try:
            print(f"  {title}...", end=" ", flush=True)
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            # ULII puts the act inside <article class="akn-act">
            body = (soup.select_one("article.akn-act")
                    or soup.select_one(".akn-akomaNtoso")
                    or soup.select_one("main")
                    or soup.body)

            text = str(body) if body else r.text
            path = _save(text, "ulii", _slug(title) + ".html")
            results.append({"title": title, "source": "ulii",
                            "url": url, "path": path, "type": "html"})
            print(f"({len(text):,} chars)")

        except Exception as e:
            print(f" {e}")

        time.sleep(DELAY)

    print(f"  {len(results)}/{len(ULII_ACTS)} acts scraped.\n")
    return results


# ══════════════════════════════════════════════════════════
# 2. URA — tax guides, rulings, practice notes
# ══════════════════════════════════════════════════════════

URA_BASE = "https://www.ura.go.ug"
URA_SEEDS = [
    "/tax-types/", "/tax-types/income-tax/",
    "/tax-types/value-added-tax/", "/tax-types/excise-duty/",
    "/publications/public-rulings/", "/publications/practice-notes/",
]


def scrape_ura() -> list[dict]:
    """Crawl URA for tax guides and download linked PDFs."""
    print("\nScraping URA — guides and rulings...")
    results, visited = [], set()

    for seed in URA_SEEDS:
        url = urljoin(URA_BASE, seed)
        if url in visited:
            continue
        visited.add(url)

        try:
            print(f"  {seed}...", end=" ", flush=True)
            r = requests.get(url, headers=HEADERS, timeout=30)
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
                if pdf_url in visited:
                    continue
                visited.add(pdf_url)
                try:
                    pt = a.get_text(strip=True) or pdf_url.split("/")[-1]
                    pr = requests.get(pdf_url, headers=HEADERS, timeout=60)
                    pr.raise_for_status()
                    pp = _save_bin(pr.content, "ura", _slug(pt) + ".pdf")
                    results.append({"title": pt, "source": "ura",
                                    "url": pdf_url, "path": pp, "type": "pdf"})
                    print(".", end="", flush=True)
                except Exception:
                    pass
                time.sleep(DELAY)

            print(" done")
        except Exception as e:
            print(f"error: {e}")
        time.sleep(DELAY)

    print(f"  {len(results)} items from URA.\n")
    return results


# ══════════════════════════════════════════════════════════
# 3. MoFPED — budget docs, tax policy
# ══════════════════════════════════════════════════════════

MOFPED_BASE = "https://www.finance.go.ug"
MOFPED_SEEDS = ["/budget-documents/", "/tax-policy/", "/publications/"]


def scrape_mofped() -> list[dict]:
    """Crawl MoFPED for budget and tax policy documents."""
    print("\nScraping MoFPED — budget and tax policy...")
    results, visited = [], set()

    for seed in MOFPED_SEEDS:
        url = urljoin(MOFPED_BASE, seed)
        if url in visited:
            continue
        visited.add(url)

        try:
            print(f"  {seed}...", end=" ", flush=True)
            r = requests.get(url, headers=HEADERS, timeout=30)
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
                if pdf_url in visited:
                    continue
                visited.add(pdf_url)
                try:
                    pt = a.get_text(strip=True) or pdf_url.split("/")[-1]
                    pr = requests.get(pdf_url, headers=HEADERS, timeout=60)
                    pr.raise_for_status()
                    pp = _save_bin(pr.content, "mofped", _slug(pt) + ".pdf")
                    results.append({"title": pt, "source": "mofped",
                                    "url": pdf_url, "path": pp, "type": "pdf"})
                    print("", end="", flush=True)
                except Exception:
                    pass
                time.sleep(DELAY)
            print(" done")
        except Exception as e:
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
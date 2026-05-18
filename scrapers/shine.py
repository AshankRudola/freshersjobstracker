import sys
import time
import random
import requests
import re as _re
from bs4 import BeautifulSoup
import os

DEBUG_LEVEL = int(os.environ.get('DEBUG_LEVEL', 1))
from utils import get_job_age_hours


class ShineScraper:
    """
    Requests + BeautifulSoup scraper for Shine.com.
    Shine renders job listings server-side — no Selenium needed.

    URL pattern (no location):
        Page 1: https://www.shine.com/job-search/{kw}-jobs?sort=1&fexp=1&fexp=2
        Page N: https://www.shine.com/job-search/{kw}-jobs-{N}?sort=1&fexp=1&fexp=2
    URL pattern (with location):
        Page 1: https://www.shine.com/job-search/{kw}-jobs-in-{loc}?sort=1&fexp=1&fexp=2
        Page N: https://www.shine.com/job-search/{kw}-jobs-in-{loc}-{N}?sort=1&fexp=1&fexp=2

    sort=1  → Sort by date (latest first)
    fexp=1  → Experience: < 1 year
    fexp=2  → Experience: 1 to 2 years
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.shine.com/",
    }

    def __init__(self, delay=1):
        self.delay = delay

    def _build_url(self, kw_slug, loc_slug, page):
        """Build Shine URL with sort=1 (latest)."""
        # URL params enforced at server level: sort by date
        params = "sort=1"

        if not loc_slug:
            if page == 1:
                return f"https://www.shine.com/job-search/{kw_slug}-jobs?{params}"
            else:
                return f"https://www.shine.com/job-search/{kw_slug}-jobs-{page}?{params}"
        else:
            if page == 1:
                return f"https://www.shine.com/job-search/{kw_slug}-jobs-in-{loc_slug}?{params}"
            else:
                return f"https://www.shine.com/job-search/{kw_slug}-jobs-in-{loc_slug}-{page}?{params}"

    def search(self, keywords: str, location: str, max_results: int = 100,
               existing_urls: set = None) -> list:
        all_jobs = []
        seen_urls = set(existing_urls) if existing_urls else set()
        page = 1

        # Clean keywords and location for URL
        kw_slug = keywords.lower().strip().replace(" ", "-")
        loc_slug = location.lower().strip().replace(" ", "-")

        print(f"  [SHINE] Searching: '{keywords}' in '{location if location else 'All India'}' (sorted by date, 0-2yr exp)", file=sys.stderr)

        while len(all_jobs) < max_results and page <= 10:
            url = self._build_url(kw_slug, loc_slug, page)

            try:
                resp = requests.get(url, headers=self.HEADERS, timeout=15)
                if resp.status_code != 200:
                    print(f"  [SHINE] HTTP {resp.status_code} on page {page}. Stopping.",
                          file=sys.stderr)
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')

                # Job cards use dynamic classes like jobCardNova_bigCard or jdbigCard
                job_cards = soup.find_all(
                    "div", 
                    class_=lambda c: c and ("jobcardnova" in c.lower() or "jdbigcard" in c.lower() or "job_card" in c.lower())
                )

                if not job_cards:
                    # Fallback: search for any div that looks like a job card
                    job_cards = soup.find_all("div", attrs={"data-job-id": True})

                if not job_cards:
                    print(f"  [SHINE] No jobs found on page {page}. Stopping.", file=sys.stderr)
                    break

                if DEBUG_LEVEL >= 1:
                    print(f"  [SHINE] Page {page}: found {len(job_cards)} cards", file=sys.stderr)

                for card in job_cards:
                    if len(all_jobs) >= max_results:
                        break

                    try:
                        # ── Title ──
                        title_el = card.find("a", href=True)
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or title == "N/D":
                            continue

                        # Keyword relevance check
                        search_words = [w.lower() for w in keywords.split() if len(w) > 2]
                        if search_words and not any(w in title.lower() for w in search_words):
                            continue

                        # ── URL ──
                        job_url = title_el.get("href", "")
                        if job_url and not job_url.startswith("http"):
                            job_url = "https://www.shine.com" + job_url

                        # ── Company ──
                        comp_el = card.find(lambda tag: tag.name in ["div", "span"] and 
                                           any("company" in c.lower() or "cname" in c.lower() 
                                               for c in (tag.get("class", []) or [])))
                        if not comp_el:
                            comp_el = card.find("span", class_=lambda c: c and "company" in c.lower())
                        company = comp_el.get_text(strip=True) if comp_el else "N/D"

                        # ── Location ──
                        loc_el = card.find(lambda tag: tag.name in ["div", "span"] and 
                                          any("loc" in c.lower() for c in (tag.get("class", []) or [])))
                        if not loc_el:
                            # Fallback: look for location icon + adjacent text
                            pin_icon = card.find(lambda tag: tag.name in ["svg", "img", "i"] and 
                                                "location" in str(tag).lower())
                            if pin_icon and pin_icon.find_parent("div"):
                                loc_el = pin_icon.find_parent("div").find("span")
                        loc_text = loc_el.get_text(strip=True) if loc_el else "N/D"

                        # ── Posted Date ──
                        date_el = card.find("span", class_=lambda c: c and "posted" in c.lower())
                        if not date_el:
                            date_el = card.find("div", class_=lambda c: c and "posted" in c.lower())
                        posted_date = date_el.get_text(strip=True).replace("posted", "").replace("<!-- -->", "").strip() if date_el else "N/D"

                        if posted_date == "N/D":
                            m = _re.search(r'(today|just now|\d+\+?\s+(day|hour|minute|month|week)s?\s+ago)', card.get_text().lower())
                            if m:
                                posted_date = m.group(0)

                        # Age filter: max 30 days
                        if posted_date != 'N/D':
                            age_hours = get_job_age_hours(posted_date)
                            if age_hours != 999999 and age_hours > 720: # 30 days max
                                if DEBUG_LEVEL >= 1:
                                    print(f"  [SHINE] Skipping old: {title} ({posted_date})", file=sys.stderr)
                                continue

                        # ── Experience ──
                        exp_el = card.find(lambda tag: tag.name in ["div", "span"] and 
                                          any("exp" in c.lower() or "experience" in c.lower() 
                                              for c in (tag.get("class", []) or [])))
                        experience = exp_el.get_text(strip=True) if exp_el else "N/A"

                        if experience in ("N/A", "None", ""):
                            # Fallback: scan card text for experience pattern
                            m = _re.search(r'(\d+)\s*(-|to|and)?\s*(\d+)?\s*(year|yr)s?', card.get_text().lower())
                            if m:
                                experience = m.group(0)

                        if "intern" in title.lower() or "internship" in title.lower():
                            experience = "Intern"

                        if experience not in ("N/A", "None", "", "Intern"):
                            try:
                                import re as _re
                                nums = [int(n) for n in _re.findall(r'\d+', experience)]
                                if nums and not any(n in [0, 1, 2] for n in nums):
                                    continue
                            except:
                                pass

                        # ── Deduplicate and add ──
                        if job_url and job_url not in seen_urls:
                            all_jobs.append({
                                "title": title,
                                "company": company,
                                "location": loc_text,
                                "url": job_url,
                                "posted_date": posted_date,
                                "experience": experience,
                                "source": "shine",
                            })
                            seen_urls.add(job_url)

                    except Exception as card_err:
                        if DEBUG_LEVEL >= 2:
                            print(f"  [SHINE] Card parse error: {card_err}", file=sys.stderr)
                        continue

            except Exception as e:
                print(f"  [SHINE] Request error on page {page}: {e}", file=sys.stderr)
                break

            page += 1
            time.sleep(self.delay + random.uniform(0.5, 1.0))

        print(f"  [SHINE] Found {len(all_jobs)} jobs total", file=sys.stderr)
        all_jobs.sort(key=lambda x: get_job_age_hours(x.get('posted_date', 'N/D')))
        return all_jobs[:max_results]

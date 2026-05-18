import sys
import time
import random
import requests
import re
import os
from datetime import datetime, timezone

DEBUG_LEVEL = int(os.environ.get('DEBUG_LEVEL', 1))
from utils import get_job_age_hours


class UnstopScraper:
    """
    Requests-based Unstop scraper using their public (undocumented) REST API.
    Returns clean JSON with ISO timestamps — no Selenium needed.

    API endpoint: https://unstop.com/api/public/opportunity/search-new
    Params: opportunity=jobs, sort=recent, page=N, size=20, q=<keyword>
    """

    BASE_URL = "https://unstop.com/api/public/opportunity/search-new"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://unstop.com/jobs",
    }
    MAX_28_DAYS_HOURS = 672  # 28 * 24

    def __init__(self, delay=1):
        self.delay = delay

    def _age_hours_from_iso(self, iso_str: str) -> float:
        """Convert an ISO-8601 datetime string to age in hours from now."""
        if not iso_str:
            return 999999
        try:
            dt = datetime.fromisoformat(iso_str.strip())
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = now - dt
            return diff.total_seconds() / 3600
        except Exception:
            return 999999

    def search(self, keywords: str, location: str, max_results: int = 100,
               existing_urls: set = None) -> list:
        all_jobs = []
        seen_urls = set(existing_urls) if existing_urls else set()
        page = 1
        PAGE_SIZE = 100

        print(f"  [UNSTOP] Searching: '{keywords}' in '{location}'", file=sys.stderr)

        while len(all_jobs) < max_results and page <= 50:
            params = {
                "opportunity": "jobs",
                "sort": "recent",
                "page": page,
                "size": PAGE_SIZE,
                "q": keywords,
                "location_search": location,
            }

            try:
                resp = requests.get(
                    self.BASE_URL, params=params,
                    headers=self.HEADERS, timeout=15
                )
                if resp.status_code != 200:
                    print(f"  [UNSTOP] HTTP {resp.status_code} on page {page}. Stopping.",
                          file=sys.stderr)
                    break

                data = resp.json()
            except Exception as e:
                print(f"  [UNSTOP] Request error: {e}", file=sys.stderr)
                break

            raw = data.get("data", {})
            items = raw.get("data", []) if isinstance(raw, dict) else []

            if not items:
                print(f"  [UNSTOP] No results on page {page}. Stopping.", file=sys.stderr)
                break

            stop_early = False
            for item in items:
                if len(all_jobs) >= max_results:
                    break

                title = item.get("title", "").strip()
                
                # Trust the API's relevance engine instead of strictly matching the title.
                # The API searches across tags and descriptions as well.

                seo_url = item.get("seo_url", "")
                org = item.get("organisation", {}) or {}
                company = org.get("name", "N/D").strip()

                loc_list = item.get("locations", []) or []
                job_location = ", ".join(
                    l.get("city", "") for l in loc_list if l.get("city")
                ) or "N/D"

                approved_date = item.get("approved_date", "") or ""
                posted_date = approved_date.strip() if approved_date else "N/D"

                age_hours = self._age_hours_from_iso(approved_date)
                if age_hours > 720 and approved_date: # 30 days max
                    if DEBUG_LEVEL >= 1:
                        print(f"  [UNSTOP] Skipping old job ({approved_date}).", file=sys.stderr)
                    continue

                try:
                    dt = datetime.fromisoformat(approved_date.strip())
                    posted_date = dt.strftime("%d %b %Y")
                except Exception:
                    posted_date = approved_date[:10] if approved_date else "N/D"

                experience = "N/A"
                if "intern" in title.lower() or "internship" in title.lower():
                    experience = "Intern"
                else:
                    desc = item.get("description", "") or ""
                    exp_match = re.search(r'(\d+)\s*(-|to|and)?\s*(\d+)?\s*(year|yr)s?', desc.lower())
                    if exp_match:
                        try:
                            experience = exp_match.group(0)
                            nums = [int(n) for n in re.findall(r'\d+', experience)]
                            if nums and not any(n in [0, 1, 2] for n in nums):
                                continue
                        except Exception:
                            pass
                    elif "freshers" in desc.lower() or "0-1 year" in desc.lower() or "0-2 year" in desc.lower():
                        experience = "0-2 years"

                if title and seo_url and seo_url not in seen_urls:
                    all_jobs.append({
                        "title": title,
                        "company": company,
                        "location": job_location,
                        "url": seo_url,
                        "posted_date": posted_date,
                        "experience": experience,
                        "source": "unstop",
                    })
                    seen_urls.add(seo_url)

            if stop_early:
                break

            page += 1
            time.sleep(self.delay + random.uniform(0.3, 0.8))

        print(f"  [UNSTOP] Found {len(all_jobs)} jobs total", file=sys.stderr)
        all_jobs.sort(key=lambda x: get_job_age_hours(x.get('posted_date', 'N/D')))
        return all_jobs[:max_results]

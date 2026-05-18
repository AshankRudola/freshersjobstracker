import sys
import os
import io

# Fix encoding
if sys.stdout is not None and getattr(sys.stdout, 'encoding', '') != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except AttributeError:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from scrapers.linkedin import LinkedInScraper
from scrapers.naukri import NaukriScraper
from scrapers.indeed import IndeedScraper
from scrapers.shine import ShineScraper
from scrapers.unstop import UnstopScraper

keywords = "Digital Marketing"
location = "bangalore"

print(f"--- DIAGNOSTIC: '{keywords}' in '{location}' ---")

scrapers = [
    ("LinkedIn", LinkedInScraper()),
    ("Naukri", NaukriScraper()),
    ("Indeed", IndeedScraper()),
    ("Shine", ShineScraper()),
    ("Unstop", UnstopScraper()),
]

for name, scraper in scrapers:
    print(f"\n[TEST] {name}...")
    try:
        res = scraper.search(keywords, location, max_results=20)
        print(f"{name} returned {len(res)} jobs.")
        for j in res[:3]:
            print(f"  - {j['title']} | Exp: {j.get('experience', 'N/A')} | Date: {j.get('posted_date', 'N/D')}")
    except Exception as e:
        print(f"{name} ERROR: {e}")

print("\n--- DIAGNOSTIC COMPLETE ---")

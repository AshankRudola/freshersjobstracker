import sys
import os
import io
import requests

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from scrapers.linkedin import LinkedInScraper
from scrapers.unstop import UnstopScraper
from scrapers.shine import ShineScraper

keywords = "Digital Marketing"
location = "bangalore"

print(f"--- FAST DIAGNOSTIC: '{keywords}' in '{location}' ---")

scrapers = [
    ("LinkedIn", LinkedInScraper()),
    ("Unstop", UnstopScraper()),
    ("Shine", ShineScraper()),
]

for name, scraper in scrapers:
    print(f"\n[TEST] {name}...")
    try:
        res = scraper.search(keywords, location, max_results=50)
        print(f"{name} returned {len(res)} jobs.")
        # Check experience filtering
        filtered_count = 0
        for j in res:
            exp = j.get('experience', 'N/A')
            # Extract years if possible
            import re
            years = 0
            if exp and exp != 'N/A' and exp != 'Intern':
                m = re.search(r'(\d+)', exp)
                if m: years = int(m.group(1))
            
            if years <= 2 or exp == 'Intern' or exp == 'N/A':
                filtered_count += 1
        
        print(f"  {filtered_count} jobs passed experience filter (<= 2 yrs).")
    except Exception as e:
        print(f"{name} ERROR: {e}")

print("\n--- FAST DIAGNOSTIC COMPLETE ---")

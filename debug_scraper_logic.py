import sys
import os
import io

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from scrapers.naukri import NaukriScraper
from scrapers.shine import ShineScraper
from scrapers.indeed import IndeedScraper

def test_naukri():
    print("=== Testing Naukri ===")
    scraper = NaukriScraper()
    # We want to see what URLs it generates and why jobs are skipped
    res = scraper.search("digital marketing", "", max_results=100)
    print(f"Naukri Total: {len(res)}")
    for r in res[:5]: print(r)

def test_shine():
    print("\n=== Testing Shine ===")
    scraper = ShineScraper()
    # Debug level 2 or higher if supported
    res = scraper.search("digital marketing", "", max_results=100)
    print(f"Shine Total: {len(res)}")
    for r in res[:5]: print(r)

def test_indeed():
    print("\n=== Testing Indeed ===")
    scraper = IndeedScraper()
    res = scraper.search("digital marketing", "", max_results=50)
    print(f"Indeed Total: {len(res)}")
    for r in res[:5]: print(r)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "naukri": test_naukri()
        elif sys.argv[1] == "shine": test_shine()
        elif sys.argv[1] == "indeed": test_indeed()
    else:
        test_shine()
        test_indeed()
        test_naukri()

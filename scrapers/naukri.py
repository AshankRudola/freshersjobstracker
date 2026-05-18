import time
import random
import sys
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import get_job_age_hours
import os

DEBUG_LEVEL = int(os.environ.get('DEBUG_LEVEL', 1))

class NaukriScraper:
    """
    Selenium-based Naukri scraper.
    CSS selectors borrowed from: https://github.com/somranal2799/naukri-job-scraper-dashboard
    """
    def __init__(self, delay=2):
        self.delay = delay

    def _create_driver(self):
        """Create a headless Chrome driver (auto-detects chromedriver)"""
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--log-level=3')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            return driver
        except Exception as e:
            # Write to a dedicated error file since we are in a sub-module
            with open('scraper_errors.log', 'a') as f:
                f.write(f"Naukri Driver Error: {str(e)}\n")
            raise e

    def _parse_experience(self, exp_text):
        """Parse experience string like '0-2 Yrs' and return the minimum number as string"""
        if not exp_text or exp_text in ('N/A', 'Not mentioned'):
            return 'N/A'
        m = re.search(r'(\d+)', exp_text)
        if m:
            return str(int(m.group(1)))
        return 'N/A'

    def search(self, keywords: str, location: str, max_results: int = 100, existing_urls: set = None) -> list:
        all_jobs = []
        seen_urls = set(existing_urls) if existing_urls else set()
        driver = None

        try:
            print(f"  [NAUKRI] Launching headless browser...", file=sys.stderr)
            driver = self._create_driver()

            # Naukri URL pattern: role-jobs-in-location for page 1, role-jobs-in-location-{offset} for page 2+
            kw_slug = keywords.lower().replace(' ', '-')
            loc_slug = location.lower().replace(' ', '-')
            page = 0
            while len(all_jobs) < max_results and page < 50:
                # Handle empty location
                if not loc_slug:
                    base_url = f"https://www.naukri.com/{kw_slug}-jobs"
                else:
                    base_url = f"https://www.naukri.com/{kw_slug}-jobs-in-{loc_slug}"
                
                # Add pagination
                if page > 0:
                    base_url += f"-{page + 1}"
                
                # Remove experience=0 to allow 1-3 year roles; sort=f ensures Freshness (Date)
                url = f"{base_url}?k={kw_slug}&sort=f"

                print(f"  [NAUKRI] Page {page + 1}: scraping...", file=sys.stderr)
                driver.get(url)
                time.sleep(self.delay + random.uniform(2, 5))

                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, "article.jobTuple, div.srp-jobtuple-wrapper")
                        )
                    )
                except Exception:
                    print(f"  [NAUKRI] No job cards found on page {page + 1}. Stopping.", file=sys.stderr)
                    break

                job_cards = driver.find_elements(By.CSS_SELECTOR, "article.jobTuple, div.srp-jobtuple-wrapper")
                if not job_cards:
                    print(f"  [NAUKRI] Empty page {page + 1}. Stopping.", file=sys.stderr)
                    break

                for job in job_cards:
                    if len(all_jobs) >= max_results:
                        break

                    try:
                        title_el = job.find_element(By.CSS_SELECTOR, "a.title")
                        title = title_el.text.strip()
                        
                        # Keyword relevance check
                        search_words = [w.lower() for w in keywords.split() if len(w) > 2]
                        if search_words and not any(w in title.lower() for w in search_words):
                            continue
                            
                        job_url = title_el.get_attribute("href") or 'N/D'

                        # Company
                        try:
                            company = job.find_element(By.CSS_SELECTOR, "a.comp-name").text.strip()
                        except Exception:
                            company = 'N/D'

                        # Location
                        loc_els = job.find_elements(By.CSS_SELECTOR, "span.locWdth")
                        job_location = loc_els[0].text.strip() if loc_els else 'N/D'

                        # Experience
                        exp_els = job.find_elements(By.CSS_SELECTOR, "span.expwdth")
                        experience = exp_els[0].text.strip() if exp_els else 'N/A'
                        
                        if experience not in ('N/A', 'Not mentioned'):
                            import re as _re
                            nums = [int(n) for n in _re.findall(r'\d+', experience)]
                            if nums and not any(n in [0, 1, 2] for n in nums):
                                continue

                        # Posted date
                        date_els = job.find_elements(By.CSS_SELECTOR, "span.job-post-day, span.footer-item, span.agrow")
                        posted_date = 'N/D'
                        for el in date_els:
                            txt = el.text.strip()
                            if any(x in txt.lower() for x in ['ago', 'today', 'just now']):
                                posted_date = txt
                                break
                        
                        if posted_date == 'N/D':
                            all_spans = job.find_elements(By.TAG_NAME, "span")
                            for s in all_spans:
                                txt = s.text.strip()
                                if any(x in txt.lower() for x in ['ago', 'today', 'just now']):
                                    posted_date = txt
                                    break
                        
                        if posted_date != 'N/D':
                            age_hours = get_job_age_hours(posted_date)
                            if age_hours != 999999 and age_hours > 720: # 30 days max
                                if DEBUG_LEVEL >= 1:
                                    print(f"  [NAUKRI] Skipping old job ({posted_date}).", file=sys.stderr)
                                continue

                        if 'intern' in title.lower():
                            experience = 'Intern'

                        # Deduplicate
                        if title and job_url != 'N/D' and job_url not in seen_urls:
                            all_jobs.append({
                                'title': title,
                                'company': company,
                                'location': job_location,
                                'url': job_url,
                                'posted_date': posted_date,
                                'experience': experience,
                                'source': 'naukri'
                            })
                            seen_urls.add(job_url)

                    except Exception as e:
                        continue

                time.sleep(self.delay + random.uniform(0.5, 1.5))
                page += 1

        except Exception as e:
            print(f"  [NAUKRI] Scraper error: {e}", file=sys.stderr)
            raise e
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        print(f"  [NAUKRI] Found {len(all_jobs)} jobs total", file=sys.stderr)
        all_jobs.sort(key=lambda x: get_job_age_hours(x.get('posted_date', 'N/D')))
        return all_jobs[:max_results]

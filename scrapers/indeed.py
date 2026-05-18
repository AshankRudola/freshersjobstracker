import sys
import time
import random
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

# Add the project root to sys.path to allow importing from utils
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import get_job_age_hours

DEBUG_LEVEL = int(os.environ.get('DEBUG_LEVEL', 1))

class IndeedScraper:
    def __init__(self, delay=3):
        self.delay = delay
        self.HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }

    def _create_driver(self):
        """Create a headless Chrome driver"""
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--log-level=3')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-notifications')
        options.add_argument('--start-maximized')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f'user-agent={self.HEADERS["User-Agent"]}')

        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            # More stealth
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            last_err = e
            time.sleep(2)
        
        with open('scraper_errors.log', 'a') as f:
            f.write(f"Indeed Driver Error: {str(last_err)}\n")
        raise last_err

    def search(self, keywords: str, location: str, max_results: int = 100, existing_urls: set = None) -> list:
        all_jobs = []
        seen_urls = set(existing_urls) if existing_urls else set()
        driver = None

        # Expanded list of 12 Indian job hubs to maximize Page 1 yield
        MAJOR_INDIAN_HUBS = [
            "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune", 
            "Chennai", "Gurgaon", "Noida", "Kolkata", "Ahmedabad", 
            "Chandigarh", "Jaipur"
        ]
        
        # If no location provided, iterate through all major hubs to maximize yield
        target_locations = [location] if location else MAJOR_INDIAN_HUBS
        if not location:
            print(f"  [INDEED] Searching across {len(target_locations)} Indian hubs...", file=sys.stderr)

        try:
            for current_loc in target_locations:
                if len(all_jobs) >= max_results:
                    break
                
                # Restart driver for each hub to bypass Cloudflare 'Just a moment...' session flags
                if driver:
                    try: driver.quit()
                    except: pass
                
                print(f"  [INDEED] Launching headless browser for {current_loc}...", file=sys.stderr)
                driver = self._create_driver()

                base_url = "https://in.indeed.com/jobs"
                page = 0
                
                while len(all_jobs) < max_results and page < 5: # Limit hubs to 5 pages max
                    offset = page * 10
                    params = {
                        'q': keywords,
                        'l': current_loc,
                        'sort': 'date',
                        'start': offset
                    }
                    url = f"{base_url}?{urlencode(params)}"

                    print(f"  [INDEED] Page {page + 1} ({current_loc}): scraping...", file=sys.stderr)
                    driver.get(url)
                    time.sleep(self.delay + random.uniform(1, 3))

                    # Check for sign-in wall
                    if "auth" in driver.current_url.lower() or "login" in driver.current_url.lower() or "account" in driver.current_url.lower():
                        print(f"  [INDEED] Sign-in wall for {current_loc} on page {page + 1}. Moving to next location.", file=sys.stderr)
                        break

                    # Check for Cloudflare
                    page_title = driver.title.lower()
                    if "hcaptcha" in driver.page_source.lower() or "cloudflare" in page_title or "just a moment" in page_title:
                        print(f"  [INDEED] Blocked by CAPTCHA/Cloudflare. Stopping hub {current_loc}.", file=sys.stderr)
                        break

                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".job_seen_beacon"))
                        )
                    except:
                        print(f"  [INDEED] No more cards for {current_loc}. Stopping hub.", file=sys.stderr)
                        break

                    job_cards = driver.find_elements(By.CSS_SELECTOR, ".job_seen_beacon")

                    if not job_cards:
                        break

                    for job in job_cards:
                        if len(all_jobs) >= max_results:
                            return all_jobs[:max_results]
                        
                        try:
                            title_el = job.find_element(By.CSS_SELECTOR, ".jcs-JobTitle")
                            title = title_el.text.strip()
                            
                            jk = job.get_attribute("data-jk") or ""
                            if jk:
                                job_url = f"https://in.indeed.com/viewjob?jk={jk}"
                            else:
                                raw_href = title_el.get_attribute("href") or ""
                                if "indeed.com" in raw_href:
                                    job_url = raw_href.split("&vjs=")[0]
                                else:
                                    import re as _re
                                    m = _re.search(r"jk=([a-f0-9]+)", raw_href)
                                    job_url = f"https://in.indeed.com/viewjob?jk={m.group(1)}" if m else raw_href

                            # Company
                            try:
                                company = job.find_element(By.CSS_SELECTOR, "[data-testid='company-name']").text.strip()
                            except:
                                company = 'N/D'

                            # Location
                            try:
                                job_location = job.find_element(By.CSS_SELECTOR, "[data-testid='text-location']").text.strip()
                            except:
                                job_location = 'N/D'

                            # Date
                            posted_date = 'N/D'
                            for selector in ["[data-testid='myJobsStateDate']", "span.date", "span[class*='date']"]:
                                try:
                                    date_el = job.find_element(By.CSS_SELECTOR, selector)
                                    txt = date_el.text.strip().replace('Posted', '').strip()
                                    if txt:
                                        posted_date = txt
                                        break
                                except: continue

                            # Experience Filter
                            experience = 'N/A'
                            try:
                                exp_match = re.search(r'(\d+)\s*(-|to|and)?\s*(\d+)?\s*(year|yr)s?', job.text.lower())
                                if exp_match:
                                    experience = exp_match.group(0)
                                    nums = [int(n) for n in re.findall(r'\d+', experience)]
                                    if nums and not any(n in [0, 1, 2] for n in nums):
                                        continue
                            except: pass

                            if 'intern' in title.lower() or 'internship' in title.lower():
                                experience = 'Intern'

                            # Filter by age (max 30 days to ensure recency)
                            if posted_date != 'N/D':
                                age_hours = get_job_age_hours(posted_date)
                                if age_hours != 999999 and age_hours > 720: # 30 days max
                                    if DEBUG_LEVEL >= 1:
                                        print(f"  [INDEED] Skipping old job ({posted_date}) in {current_loc}.", file=sys.stderr)
                                    continue

                            # Deduplicate
                            if title and job_url and job_url not in seen_urls:
                                all_jobs.append({
                                    'title': title, 'company': company, 'location': job_location,
                                    'url': job_url, 'posted_date': posted_date, 'experience': experience,
                                    'source': 'indeed'
                                })
                                seen_urls.add(job_url)
                            else:
                                if DEBUG_LEVEL >= 2:
                                    print(f"  [INDEED] Skipping duplicate/empty: {title}", file=sys.stderr)

                        except: continue
                    page += 1

            all_jobs.sort(key=lambda x: get_job_age_hours(x.get('posted_date', 'N/D')))
            return all_jobs[:max_results]
        except Exception as e:
            print(f"  [INDEED] Critical error: {e}", file=sys.stderr)
            raise e
        finally:
            if driver: driver.quit()

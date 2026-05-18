import requests
from bs4 import BeautifulSoup
import time
import sys
import re
import random
import io
from utils import get_job_age_hours


# Pool of realistic user agents to rotate through
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0',
]

class LinkedInScraper:
    def __init__(self, delay=2):
        self.delay = delay
        self.max_retries = 3
        self.backoff_factor = 2
        self.session = requests.Session()
        self._rotate_ua()  # Set initial user agent

    def _rotate_ua(self):
        """Rotate user agent to reduce rate-limiting risk"""
        ua = random.choice(USER_AGENTS)
        self.session.headers.update({
            'User-Agent': ua,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.linkedin.com/jobs',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        })

    def _retry_request(self, url, timeout=10):
        """Retry request with exponential backoff on 429"""
        for attempt in range(self.max_retries):
            try:
                self._rotate_ua()  # Rotate UA on each request
                resp = self.session.get(url, timeout=timeout)
                if resp.status_code == 429:
                    wait_time = (self.backoff_factor ** attempt) * 10
                    print(f"  Rate limited (429). Waiting {wait_time}s before retry...", file=sys.stderr)
                    time.sleep(wait_time)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                wait_time = (self.backoff_factor ** attempt) * 5
                err_msg = str(e).split('(')[0].strip() if '(' in str(e) else str(e)
                print(f"  Request failed ({err_msg}). Retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
        return None

    def _build_search_url(self, keywords, location, start):
        """Build LinkedIn search URL with all optimized filters"""
        from urllib.parse import urlencode
        params = {
            'keywords': keywords,
            'location': location,
            'f_TPR': 'r2592000',   # Past month
            'sortBy': 'DD',        # Sort by most recent (Date Descending)
            'start': start
        }
        base = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?'
        return base + urlencode(params)

    def search(self, keywords: str, location: str, max_results: int = 100, existing_urls: set = None) -> list:
        all_jobs = []
        seen_urls = set(existing_urls) if existing_urls else set()
        start_offset = 0
        consecutive_empty_pages = 0
        max_empty_pages = 3
        batch_size = 25

        # Ensure LinkedIn defaults to India if no location is specified
        search_location = location if location else "India"

        while len(all_jobs) < max_results:
            url = self._build_search_url(keywords, search_location, start_offset)
            try:
                resp = self._retry_request(url)
                if resp is None:
                    break
                time.sleep(self.delay + random.uniform(0, 1))  # Randomized delay
                soup = BeautifulSoup(resp.text, 'html.parser')
                jobs_html = soup.find_all('li')
                if not jobs_html:
                    print(f"  [LINKEDIN] Page {start_offset // batch_size + 1}: No jobs found (Length: {len(resp.text)}).", file=sys.stderr)
                    if "authwall" in resp.url or "login" in resp.url.lower():
                        print(f"  [LINKEDIN] Redirected to login/authwall. IP likely flagged.", file=sys.stderr)
                        break
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= max_empty_pages:
                        break
                    start_offset += batch_size
                    continue
                consecutive_empty_pages = 0

                for job_html in jobs_html:
                    if len(all_jobs) >= max_results:
                        return all_jobs[:max_results]

                    title_tag = job_html.find('h3', class_='base-search-card__title')
                    company_tag = job_html.find('h4', class_='base-search-card__subtitle')
                    location_tag = job_html.find('span', class_='job-search-card__location')
                    link_tag = job_html.find('a', class_='base-card__full-link')
                    date_tag = job_html.find('time')

                    title = title_tag.text.strip() if title_tag else 'N/D'
                    company = company_tag.text.strip() if company_tag else 'N/D'
                    job_location = location_tag.text.strip() if location_tag else 'N/D'
                    job_url = link_tag['href'] if (link_tag and 'href' in link_tag.attrs) else 'N/D'
                    posted_date = date_tag.text.strip() if date_tag else 'N/D'
                    ago_time = job_html.find('span', class_='job-search-card__listdate')
                    if ago_time:
                        posted_date = ago_time.text.strip()

                    if title != 'N/D' and job_url != 'N/D' and job_url not in seen_urls:
                        # Filter by age (max 30 days)
                        if posted_date != 'N/D':
                            age_hours = get_job_age_hours(posted_date)
                            if age_hours != 999999 and age_hours > 720: # 30 days * 24 hours
                                continue

                        experience = 'N/A'
                        skip_job = False

                        # Fetch JD to enrich the experience column
                        try:
                            time.sleep(0.5 + random.uniform(0, 0.5))  # Shorter delay since API pre-filters
                            jd_resp = self.session.get(job_url, timeout=5)
                            if jd_resp and jd_resp.status_code == 200:
                                jd_soup = BeautifulSoup(jd_resp.text, 'html.parser')
                                desc_div = jd_soup.find('div', class_='description__text')
                                if desc_div:
                                    desc_text = desc_div.text
                                    m = re.search(
                                        r'(\d+)[+ \-]*(?:to|-)?[\s]*(\d+)?[\s]*(?:years?|yrs?)(?:\s+of)?(?:\s+hands-on)?(?:\s+relevant)?(?:\s+experience)?',
                                        desc_text, re.IGNORECASE
                                    )
                                    if m:
                                        experience = m.group(0).strip()
                                        nums = [int(n) for n in re.findall(r'\d+', experience)]
                                        if nums and not any(n in [0, 1, 2] for n in nums):
                                            skip_job = True
                        except requests.exceptions.SSLError:
                            pass  # Silently skip — job still gets added with N/A experience
                        except Exception:
                            pass  # Silently skip — job still gets added with N/A experience

                        if skip_job:
                            continue

                        if 'intern' in title.lower():
                            experience = 'Intern'
                            
                        all_jobs.append({
                            'title': title,
                            'company': company,
                            'location': job_location,
                            'url': job_url,
                            'posted_date': posted_date,
                            'experience': experience,
                            'source': 'linkedin'
                        })
                        seen_urls.add(job_url)

                start_offset += batch_size
            except requests.RequestException as e:
                print(f"Request failed: {e}", file=sys.stderr)
                break
            except Exception as e:
                print(f"Unexpected error: {e}", file=sys.stderr)
                break

        all_jobs.sort(key=lambda x: get_job_age_hours(x.get('posted_date', 'N/D')))
        return all_jobs[:max_results]

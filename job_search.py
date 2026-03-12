import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE = "seen_jobs.json"

# These queries are DIFFERENT from account 1
# Focus: Consulting, Strategy, Startups, Ops, General MBA roles
SEARCH_QUERIES = [
    "strategy consultant MBA India",
    "management consultant associate India",
    "business consultant India",
    "consulting analyst India",
    "associate consultant India",
    "operations consultant India",
    "founders office India",
    "business strategy manager India",
    "corporate strategy India",
    "growth manager India",
    "market entry strategy India",
    "go to market strategy India",
    "product strategy manager India",
    "business transformation India",
    "process excellence India",
    "operational excellence India",
    "demand planning manager India",
    "commercial manager FMCG",
    "key account manager pharma",
    "zonal sales manager pharma",
    "area sales manager medical",
    "brand manager healthcare",
    "product launch manager pharma",
    "market access manager pharma",
    "business development pharma India",
]

PAGES_PER_QUERY = 3

INCLUDE_KEYWORDS = [
    "product manager", "associate product manager", "apm",
    "product analyst", "product operations", "product lead",
    "product owner", "product strategy",
    "strategy analyst", "strategy consultant", "strategy manager",
    "business strategy", "corporate strategy", "strategic initiatives",
    "management consultant", "consulting analyst", "associate consultant",
    "business consultant", "operations consultant",
    "business analyst", "commercial manager",
    "sales manager", "zonal sales", "area sales",
    "key account manager", "kam",
    "business development manager", "business development",
    "gtm", "go-to-market", "market entry",
    "brand manager", "product launch", "market access",
    "category manager", "trade marketing",
    "operations manager", "operational excellence",
    "process excellence", "process improvement",
    "supply chain manager", "demand planning",
    "founders office", "founder's office",
    "business transformation", "transformation manager",
    "growth manager", "growth analyst",
    "market research analyst", "market intelligence",
    "commercial excellence", "program manager",
    "project manager",
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", " sr ", "lead ", "principal",
    "vp", "vice president", "director", "head of",
    "avp", "evp", "svp", "cxo", "ceo", "coo", "cto", "cfo",
    "general manager", "dgm", "agm",
    "associate director", "associate vp",
    "intern", "internship", "fresher", "trainee",
    "chief of staff",
    "software engineer", "software developer", "developer",
    "data scientist", "machine learning", "devops", "backend",
    "frontend", "full stack", "qa engineer", "test engineer",
    "data engineer", "cloud engineer",
    "technical program", "technical project",
    "it project", "it manager", "application manager",
    "accountant", "finance manager", "chartered accountant",
    "radiologist", "doctor", "physician", "nurse", "technician",
    "driver", "field technician", "warehouse",
    "recruiter", "hr manager", "talent acquisition",
    "content writer", "graphic designer", "telecaller",
    "cyber", "cybersecurity", "network",
    "banking", "insurance", "mortgage",
    "channel sales", "channel partner",
    "influencer", "social media manager",
]

INCLUDE_LOCATIONS = [
    "bengaluru", "bangalore", "hyderabad", "mumbai",
    "delhi", "gurugram", "gurgaon", "noida",
    "remote", "india", "pan india", "work from home",
    "chennai", "pune",
]

def clean(text):
    text = text or ""
    text = text.replace("&", "and").replace("<", "").replace(">", "")
    return text.strip()

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_seen_jobs(seen_jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_jobs, f, indent=2)

def fetch_jobs(query, start=0):
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        "?keywords={}&location=India&f_TPR=r7200&start={}"
    ).format(requests.utils.quote(query), start)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.text
    except Exception as e:
        print("Error fetching '{}' start={}: {}".format(query, start, e))
        return ""

def parse_jobs(html):
    jobs = []
    blocks = html.split('<div class="base-card')

    title_re = re.compile(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>\s*([^<]+)\s*</h3>', re.I)
    company_re = re.compile(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>[\s\S]*?<a[^>]*>\s*([^<]+)\s*</a>', re.I)
    location_re = re.compile(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<]+)\s*</span>', re.I)
    url_re = re.compile(r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', re.I)
    posted_re = re.compile(r'<time[^>]*>\s*([^<]+)\s*</time>', re.I)

    for block in blocks:
        title_m = title_re.search(block)
        url_m = url_re.search(block)
        if not title_m or not url_m:
            continue

        company_m = company_re.search(block)
        location_m = location_re.search(block)
        posted_m = posted_re.search(block)

        jobs.append({
            "title": clean(title_m.group(1)),
            "company": clean(company_m.group(1) if company_m else "Unknown"),
            "location": clean(location_m.group(1) if location_m else "India"),
            "url": url_m.group(1).strip().split("?")[0],
            "posted": clean(posted_m.group(1) if posted_m else "Recently"),
        })

    return jobs

def is_relevant(job):
    title = job["title"].lower()
    location = job["location"].lower()
    if not any(k in title for k in INCLUDE_KEYWORDS):
        return False
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return False
    if not any(l in location for l in INCLUDE_LOCATIONS):
        return False
    return True

def send_telegram(message):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            print("Telegram error: {} - {}".format(response.status_code, response.text))
        return response.ok
    except Exception as e:
        print("Telegram error: {}".format(e))
        return False

def main():
    seen_jobs = load_seen_jobs()
    new_jobs = []
    all_urls = set()

    for query in SEARCH_QUERIES:
        for page in range(PAGES_PER_QUERY):
            start = page * 25
            print("Fetching: '{}' page {}".format(query, page + 1))
            html = fetch_jobs(query, start=start)
            jobs = parse_jobs(html)
            if not jobs:
                print("  No results on page {}, stopping.".format(page + 1))
                break
            for job in jobs:
                url = job["url"]
                if url in all_urls:
                    continue
                all_urls.add(url)
                if url in seen_jobs:
                    continue
                if not is_relevant(job):
                    continue
                new_jobs.append(job)
                seen_jobs[url] = datetime.now(timezone.utc).isoformat()

    print("Total new jobs found: {}".format(len(new_jobs)))

    if not new_jobs:
        print("No new matching jobs found.")
        save_seen_jobs(seen_jobs)
        return

    IST = timezone(timedelta(hours=5, minutes=30))
    batch_time = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    for job in new_jobs:
        message = (
            "New Job Alert - LinkedIn\n\n"
            "Found at: {}\n\n"
            "Role: {}\n"
            "Company: {}\n"
            "Location: {}\n"
            "Posted: {}\n\n"
            "Apply here: {}"
        ).format(batch_time, job["title"], job["company"], job["location"], job["posted"], job["url"])

        success = send_telegram(message)
        if success:
            print("Sent: {} at {}".format(job["title"], job["company"]))
        else:
            print("Failed: {}".format(job["title"]))

    save_seen_jobs(seen_jobs)
    print("Done.")

if __name__ == "__main__":
    main()

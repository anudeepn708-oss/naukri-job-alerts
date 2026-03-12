import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")
SEEN_JOBS_FILE = "seen_jobs.json"

SEARCH_QUERIES = [
    "product manager",
    "associate product manager",
    "product analyst",
    "business analyst",
    "strategy analyst",
    "strategy consultant",
    "management consultant",
    "GTM manager",
    "operations manager",
    "supply chain manager",
    "business development manager",
    "category manager",
    "program manager",
    "chief of staff",
    "sales manager",
    "market research analyst",
    "growth analyst",
    "consulting analyst",
    "commercial excellence",
    "corporate strategy",
]

INCLUDE_KEYWORDS = [
    "product manager", "associate product manager", "apm",
    "product analyst", "product operations", "product lead",
    "product owner", "strategy analyst", "strategy consultant",
    "strategy manager", "management consultant", "consulting analyst",
    "associate consultant", "business analyst", "sales manager",
    "sales operations", "sales analyst", "business development manager",
    "gtm manager", "go-to-market manager", "marketing manager",
    "brand manager", "category manager", "trade marketing manager",
    "operations manager", "operations analyst", "supply chain manager",
    "supply chain analyst", "demand planning", "process improvement",
    "business operations manager", "chief of staff", "program manager",
    "project manager", "growth analyst", "market research analyst",
    "market intelligence", "commercial excellence", "kpi analyst",
    "business development", "channel sales manager", "corporate strategy",
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", " sr ", "lead ", "principal", "staff ",
    "vp", "vice president", "director", "head of", "head -",
    "avp", "evp", "svp", "cxo", "ceo", "coo", "cto", "cfo",
    "general manager", "deputy general manager", "dgm", "agm",
    "associate director", "associate vp",
    "intern", "internship", "fresher", "trainee",
    "software engineer", "software developer", "developer",
    "data scientist", "machine learning", "devops", "backend",
    "frontend", "full stack", "full-stack", "qa engineer",
    "test engineer", "data engineer", "mlops", "cloud engineer",
    "accountant", "finance manager", "chartered accountant",
    "radiologist", "doctor", "physician", "nurse", "technician",
    "driver", "field technician", "warehouse", "blue collar",
    "recruiter", "hr manager", "talent acquisition",
    "content writer", "graphic designer", "telecaller",
]

def clean(text):
    text = text or ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&amp;", "and").replace("&lt;", "").replace("&gt;", "")
    text = text.replace("&", "and").replace("|", "-").replace("#", "")
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text.strip()

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_seen_jobs(seen_jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_jobs, f, indent=2)

def fetch_adzuna_jobs(query, page=1):
    url = "https://api.adzuna.com/v1/api/jobs/in/search/{}".format(page)
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": query,
        "where": "India",
        "results_per_page": 50,
        "max_days_old": 1,
        "sort_by": "date",
        "content-type": "application/json",
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        print("  Status: {}".format(response.status_code))
        return response.json()
    except Exception as e:
        print("Error fetching Adzuna '{}': {}".format(query, e))
        return {}

def parse_adzuna_jobs(data):
    jobs = []
    try:
        for job in data.get("results", []):
            title = clean(job.get("title", ""))
            company = clean(job.get("company", {}).get("display_name", "Unknown"))
            location = clean(job.get("location", {}).get("display_name", "India"))
            url = job.get("redirect_url", "")
            created = job.get("created", "")
            try:
                dt = datetime.strptime(created[:10], "%Y-%m-%d")
                posted = dt.strftime("%d %b %Y")
            except Exception:
                posted = "Recently"
            if not title or not url:
                continue
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "posted": posted,
            })
    except Exception as e:
        print("Parse error: {}".format(e))
    return jobs

def is_relevant(job):
    title = job["title"].lower()
    if not any(k in title for k in INCLUDE_KEYWORDS):
        return False
    if any(k in title for k in EXCLUDE_KEYWORDS):
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
        print("Fetching Adzuna: '{}'".format(query))
        data = fetch_adzuna_jobs(query)
        total = data.get("count", 0)
        jobs = parse_adzuna_jobs(data)
        print("  Total available: {}, Fetched: {}".format(total, len(jobs)))

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
            "New Job Alert - Adzuna\n\n"
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

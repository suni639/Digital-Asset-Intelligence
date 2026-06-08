import os
import sys
import json
import time
import datetime
import subprocess
import smtplib
import warnings
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

# 1. Self-install dependencies if missing (primarily for local execution safety)
def install_dependencies():
    required_packages = ["requests", "beautifulsoup4", "google-genai", "markdown"]
    for pkg in required_packages:
        try:
            if pkg == "google-genai":
                from google import genai
            else:
                __import__(pkg)
        except ImportError:
            print(f"Installing missing dependency: {pkg}...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
            except Exception as e:
                print(f"Failed to install package {pkg}: {e}", file=sys.stderr)
                with open("error_log.txt", "a") as f:
                    f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR: Failed to install {pkg}: {str(e)}\n")

install_dependencies()

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
from google import genai
import markdown

# Helper to fetch environment variables, supporting fallback to Windows registry for local setups
def get_env_var(name):
    val = os.environ.get(name)
    if not val and sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
            val, _ = winreg.QueryValueEx(key, name)
            winreg.CloseKey(key)
        except Exception:
            pass
    return val

# Verify all mandatory environment variables are set before proceeding
def verify_environment():
    missing_vars = []
    required_vars = ["GEMINI_API_KEY", "SMTP_USER", "SMTP_PASS"]
    
    for var in required_vars:
        if not get_env_var(var):
            missing_vars.append(var)
            
    if missing_vars:
        print(f"CRITICAL ERROR: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
        print("Please ensure these are configured in your system environment or as GitHub Repository Secrets.", file=sys.stderr)
        
        # Log to error_log.txt as a fallback
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] ERROR: Startup aborted due to missing variables: {', '.join(missing_vars)}\n")
            
        return False
    return True

# 2. Configuration & State Paths
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(WORKSPACE_DIR, "config.json")
STATE_PATH = os.path.join(WORKSPACE_DIR, "system_state.json")
ERROR_LOG_PATH = os.path.join(WORKSPACE_DIR, "error_log.txt")

# Load Configuration
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    print(f"Error loading config.json: {e}", file=sys.stderr)
    sys.exit(1)

# Load State (Runs cleanly from scratch if system_state.json does not exist)
try:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {"last_run": None, "processed_urls": {}}
except Exception as e:
    state = {"last_run": None, "processed_urls": {}}

# Automatic migration from list format to dictionary format
if isinstance(state.get("processed_urls"), list):
    print("Migrating system state format: converting URL list to timestamped dictionary...")
    new_processed = {}
    for url in state["processed_urls"]:
        new_processed[url] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["processed_urls"] = new_processed
elif not isinstance(state.get("processed_urls"), dict):
    state["processed_urls"] = {}

# 3. Scraping Functions
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def log_error(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] ERROR: {msg}\n")
    print(f"ERROR: {msg}", file=sys.stderr)

def fetch_url(url, silent_on_403=False):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            if silent_on_403:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] WARNING: HTTP 403 Forbidden for {url}. Crawling blocked, using RSS summary instead.\n")
                return None
        log_error(f"Failed to fetch {url}: {e}")
        return None
    except Exception as e:
        log_error(f"Failed to fetch {url}: {e}")
        return None

def fetch_jina_reader(url):
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "User-Agent": HEADERS["User-Agent"]
    }
    try:
        print(f"Attempting Jina Reader crawling fallback for: {url}")
        r = requests.get(jina_url, headers=headers, timeout=20)
        r.raise_for_status()
        if r.text and len(r.text.strip()) > 100:
            return r.text
        return ""
    except Exception as e:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] WARNING: Jina Reader fallback failed for {url}: {e}\n")
        return ""

def extract_article_body(url):
    r = fetch_url(url, silent_on_403=True)
    if not r:
        # Fallback to Jina Reader to bypass Cloudflare 403 blocks
        jina_text = fetch_jina_reader(url)
        if jina_text:
            return jina_text[:4000]
        return ""
    try:
        soup = BeautifulSoup(r.text, 'html.parser')
        # Common WordPress and news main body tags
        content_div = soup.find('div', class_=re.compile(r'entry-content|post-content|article-body|story-content'))
        if content_div:
            paragraphs = content_div.find_all('p')
        else:
            paragraphs = soup.find_all('p')
        
        text = "\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
        # Limit length to avoid token explosion
        return text[:4000]
    except Exception as e:
        log_error(f"Failed parsing body for {url}: {e}")
        return ""

def scrape_ledger_insights():
    articles = []
    url = "https://www.ledgerinsights.com/category/news/"
    r = fetch_url(url)
    if not r:
        return articles
    try:
        soup = BeautifulSoup(r.text, 'html.parser')
        for article in soup.find_all('article'):
            h2 = article.find('h2')
            if h2:
                a = h2.find('a')
                if a:
                    title = a.get_text(strip=True)
                    link = a.get('href')
                    if link and link not in state.get("processed_urls", {}):
                        body = extract_article_body(link)
                        articles.append({
                            "title": title,
                            "url": link,
                            "source": "Ledger Insights",
                            "date": datetime.datetime.now().strftime("%Y-%m-%d"), # Fallback to today
                            "content": body
                        })
    except Exception as e:
        log_error(f"Parsing Ledger Insights failed: {e}")
    return articles

def parse_rss_feed(source_name, feed_url):
    articles = []
    r = fetch_url(feed_url)
    if not r:
        return articles
    try:
        # Use html.parser to parse feed leniently and handle invalid XML tokens
        soup = BeautifulSoup(r.content, 'html.parser')
        for item in soup.find_all('item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            pub_date_elem = item.find('pubdate') or item.find('pubDate')
            desc_elem = item.find('description')
            
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Handle links that may be embedded inside other XML tags
            link = ""
            if link_elem:
                link = link_elem.get_text(strip=True)
                if not link and link_elem.next_sibling:
                    link = link_elem.next_sibling.strip() if isinstance(link_elem.next_sibling, str) else ""
            
            # Fallback regex URL parsing if link tag is empty
            if not link and item.text:
                urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', item.text)
                if urls:
                    link = urls[0]
                    
            pub_date = pub_date_elem.get_text(strip=True) if pub_date_elem else ""
            desc = desc_elem.get_text(strip=True) if desc_elem else ""
            
            desc_cleaned = BeautifulSoup(desc, 'html.parser').get_text(strip=True) if desc else ""
            
            if link and link not in state.get("processed_urls", {}):
                body = extract_article_body(link)
                if not body:
                    body = desc_cleaned
                
                articles.append({
                    "title": title,
                    "url": link,
                    "source": source_name,
                    "date": pub_date,
                    "content": body
                })
    except Exception as e:
        log_error(f"Parsing RSS feed {source_name} failed: {e}")
    return articles

def scrape_atlantic_council_tracker():
    articles = []
    url = "https://www.atlanticcouncil.org/cbdctracker/"
    r = fetch_url(url)
    if not r:
        return articles
    try:
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        m_countries = re.search(r'(\d+)\s+countries', text, re.IGNORECASE)
        m_gdp = re.search(r'(\d+)%\s+of\s+global\s+GDP', text, re.IGNORECASE)
        
        summary_info = ""
        if m_countries:
            summary_info += f"Countries exploring CBDC: {m_countries.group(0)}. "
        if m_gdp:
            summary_info += f"Global GDP represented: {m_gdp.group(0)}. "
            
        summary_info += " Brazil's Drex wholesale pilot active. US focusing on Project Cedar wholesale interbank settlement."
        
        tracker_key = f"atlantic_council_cbdc_tracker_{datetime.datetime.now().strftime('%Y-%W')}"
        if tracker_key not in state.get("processed_urls", {}):
            articles.append({
                "title": "Atlantic Council CBDC Tracker Update - May 2026",
                "url": tracker_key,
                "source": "Atlantic Council CBDC Tracker",
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "content": text[:4000] if len(text) > 500 else summary_info
            })
    except Exception as e:
        log_error(f"Scraping Atlantic Council tracker failed: {e}")
    return articles

# 4. Ingestion Runner (Dynamic loading from config.json)
def ingest_all():
    all_articles = []
    sources = config.get("sources", {})
    
    if "ledger_insights" in sources:
        print("Ingesting Ledger Insights...")
        all_articles.extend(scrape_ledger_insights())
        
    if "finextra" in sources:
        print("Ingesting Finextra RSS...")
        all_articles.extend(parse_rss_feed(sources["finextra"]["name"], sources["finextra"]["url"]))
        
    if "blockworks" in sources:
        print("Ingesting Blockworks RSS...")
        all_articles.extend(parse_rss_feed(sources["blockworks"]["name"], sources["blockworks"]["url"]))
        
    if "the_block" in sources:
        print("Ingesting The Block RSS...")
        all_articles.extend(parse_rss_feed(sources["the_block"]["name"], sources["the_block"]["url"]))
        
    if "bis" in sources:
        print("Ingesting BIS RSS...")
        all_articles.extend(parse_rss_feed(sources["bis"]["name"], sources["bis"]["url"]))
        
    if "atlantic_council" in sources:
        print("Ingesting Atlantic Council...")
        all_articles.extend(scrape_atlantic_council_tracker())
        
    return all_articles

# 5. Gemini Analysis & Synthesis
def run_gemini_synthesis(articles):
    gemini_key = get_env_var("GEMINI_API_KEY")
    if not gemini_key:
        log_error("GEMINI_API_KEY environment variable is not set. Synthesis skipped.")
        return None
        
    client = genai.Client(api_key=gemini_key)
    
    # Construct input payload
    articles_data = []
    for idx, art in enumerate(articles):
        articles_data.append(f"""
[Article {idx+1}]
Title: {art['title']}
Source: {art['source']}
URL: {art['url']}
Date: {art['date']}
Content: {art['content']}
""")
    
    articles_input = "\n\n".join(articles_data)
    
    prompt = f"""
You are the lead Institutional Analyst for the Institutional Digital Asset Intelligence Engine (Project ID: DA-INTEL-01).
Your task is to apply a strict binary filter ("The Noise Gate") to the following harvested articles and synthesise them into a highly professional weekly briefing.

Allowed Content Attributes (High-Signal):
- Tokenised commercial bank liabilities (Deposit tokens, JPM Coin, GBTD).
- Delivery vs. Payment (DvP) and atomic settlement mechanics.
- Real-World Asset (RWA) tokenisation (sovereign bonds, private credit, funds like BlackRock's BUIDL).
- Central Bank Digital Currencies (Wholesale CBDC infrastructure over Retail).
- Legislative developments (EU MiCA enforcement timelines, UK Property Digital Assets Bill, US payment stablecoin frameworks, SEC asset custody rules/SAB 121 updates).
- Post-trade market utilities (DTCC, Euroclear, Swift network orchestration trials).

Forbidden Content Attributes (Noise - DISCARD IMMEDIATELY):
- Token spot price movements, percent gains/losses, or technical chart analysis.
- Retail exchange listings, retail trading volumes, or consumer wallet integrations.
- Speculative market commentary, influencer sentiment, and retail protocol updates (DeFi yield farms, memecoins, NFTs).
- Retail reward points systems.

Instructions:
1. Discard any article that triggers the forbidden attributes.
2. Write strictly in British English (e.g., tokenised, tokenisation, prioritised, decentralised, utilising, programmes, centre, defence, licences).
3. Embed direct markdown links to sources inline with the text wherever a development or project is mentioned.
4. DO NOT output a top-level H1 title — the title comes from the Hugo front matter.
5. The briefing layout must strictly match this markdown format:

## 1. MACRO VIEW
[5-7 punchy bullet points. Each bullet must open with a **bold declarative statement** (the headline), followed by 1-2 sentences of supporting facts. No hedge language ("appears to", "it is evident that", "underscored by"). No AI fluff. Write like a sharp sell-side analyst note — state the fact, state why it matters. Each bullet must be independently scannable.]

## 2. CORE PILLAR DEVELOPMENTS
* **Banking Infrastructure & Commercial Rails:** [Tokenised deposits, wholesale network expansions, intraday liquidity settlement.]
* **Institutional Asset Management & RWAs:** [Fund tokenisation updates, institutional custody shifts, security tokens.]
* **Sovereign Infrastructure & CBDCs:** [Wholesale CBDC trials, cross-border experiments, multi-ledger integrations.]
* **Regulatory & Legal Frameworks:** [Active compliance timelines, legal definitions of digital property, sandbox entries.]

## 3. STRUCTURAL & OPERATIONAL PAIN POINTS
* **Interoperability Silos:** [Where separate private blockchains or ledgers failed to bridge cleanly.]
* **Balance Sheet & Liquidity Friction:** [Disintermediation risks or regulatory constraints impacting capital efficiency.]
* **Post-Trade Plumbing Constraints:** [Settlement bottlenecks or custodian friction.]

## 4. NEW HIGH-SIGNAL TARGETS FOR TRACKING
* [List of 3-5 hyper-specific project names, working groups, or pieces of legislation discovered this week to add to keyword filters. Include markdown links to the sources if available.]

Here are the harvested articles:
{articles_input}
"""
    
    try:
        gemini_model = get_env_var("GEMINI_MODEL") or "gemini-3.5-flash"
        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        log_error(f"Gemini API generation failed: {e}")
        return None

# 6. HTML Newsletter Formatter
def convert_markdown_to_newsletter_html(subject, date_str, markdown_content):
    # Convert markdown to basic HTML
    raw_html = markdown.markdown(markdown_content)
    
    # Wrap the synthesis block in a card
    if "<h2>1. MACRO VIEW</h2>" in raw_html:
        parts = raw_html.split("<h2>2. CORE PILLAR DEVELOPMENTS</h2>")
        if len(parts) > 1:
            synthesis_part = parts[0]
            rest_part = parts[1]
            
            # Find synthesis paragraph and wrap it in the card styling
            synthesis_part = synthesis_part.replace("<p>", '<div class="synthesis-card"><p>', 1)
            synthesis_part += '</div>'
            
            raw_html = synthesis_part + "<h2>2. CORE PILLAR DEVELOPMENTS</h2>" + rest_part

    css_styles = """
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #f1f5f9;
      color: #334155;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }
    .email-container {
      max-width: 680px;
      margin: 40px auto;
      background-color: #ffffff;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
      overflow: hidden;
    }
    .header {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      padding: 32px;
      color: #ffffff;
    }
    .header h1 {
      font-size: 22px;
      font-weight: 700;
      margin: 0 0 6px 0;
      letter-spacing: -0.5px;
    }
    .header .date {
      font-size: 13px;
      color: #94a3b8;
      font-weight: 500;
    }
    .content {
      padding: 32px;
      line-height: 1.6;
    }
    .content h1 {
      display: none; /* Hide the h1 inside content as it is already in the header */
    }
    .content h2 {
      font-size: 14px;
      font-weight: 700;
      color: #0f172a;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 6px;
      margin-top: 28px;
      margin-bottom: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .content p {
      margin-top: 0;
      margin-bottom: 16px;
      font-size: 14px;
      color: #475569;
    }
    .synthesis-card {
      background-color: #f8fafc;
      border-left: 4px solid #2563eb;
      padding: 18px;
      border-radius: 0 8px 8px 0;
      margin-bottom: 24px;
    }
    .synthesis-card p {
      margin: 0;
      font-size: 14.5px;
      color: #1e293b;
      line-height: 1.6;
    }
    .content ul {
      padding-left: 20px;
      margin-top: 8px;
      margin-bottom: 20px;
    }
    .content li {
      margin-bottom: 12px;
      font-size: 13.5px;
      color: #475569;
    }
    .content li strong {
      color: #0f172a;
    }
    .content a {
      color: #2563eb;
      text-decoration: none;
      font-weight: 500;
    }
    .content a:hover {
      text-decoration: underline;
    }
    .footer {
      background-color: #f8fafc;
      padding: 24px;
      text-align: center;
      font-size: 11px;
      color: #94a3b8;
      border-top: 1px solid #f1f5f9;
    }
    """
    
    html_newsletter = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    {css_styles}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="header">
      <h1>Institutional Digital Asset Intelligence</h1>
      <div class="date">{date_str}</div>
    </div>
    <div class="content">
      {raw_html}
    </div>
    <div class="footer">
      This is an automated intelligence briefing compiled by DA-INTEL-01.<br>
      To modify subscription preferences or source endpoints, edit config.json.
    </div>
  </div>
</body>
</html>
"""
    return html_newsletter

# 7. Email Delivery Layer (Multipart MIME)
def send_email(subject, plain_body, html_body, recipient_email):
    smtp_user = get_env_var('SMTP_USER')
    smtp_pass = get_env_var('SMTP_PASS')
    
    if not smtp_user or not smtp_pass:
        log_error("SMTP_USER or SMTP_PASS environment variables are not set. Email dispatch aborted.")
        return False
        
    msg = MIMEMultipart('alternative')
    msg['From'] = smtp_user
    msg['To'] = recipient_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(plain_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    
    max_retries = 3
    
    # Custom retry sleep intervals:
    # If running inside GitHub Actions, fail fast (10s intervals) to avoid burning user's runner minutes.
    # Otherwise, wait 15 minutes as per local schedule requirements.
    is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    retry_interval = 10 if is_github_actions else 15 * 60
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Connecting to SMTP server (attempt {attempt}/{max_retries})...")
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipient_email, msg.as_string())
            server.quit()
            print("Email sent successfully!")
            return True
        except Exception as e:
            log_error(f"Email delivery attempt {attempt} failed: {str(e)}")
            if attempt < max_retries:
                print(f"Waiting {retry_interval} seconds before retrying...")
                time.sleep(retry_interval)
            else:
                return False

def prune_state(state_dict, max_age_days=60):
    if "processed_urls" not in state_dict or not isinstance(state_dict["processed_urls"], dict):
        return state_dict
        
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=max_age_days)
    
    pruned_urls = {}
    pruned_count = 0
    for url, ts_str in state_dict["processed_urls"].items():
        try:
            ts = datetime.datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            
            if ts >= cutoff:
                pruned_urls[url] = ts_str
            else:
                pruned_count += 1
        except Exception:
            pruned_urls[url] = ts_str
            
    state_dict["processed_urls"] = pruned_urls
    if pruned_count > 0:
        print(f"Pruned {pruned_count} URLs older than {max_age_days} days from the system state.")
    return state_dict

# 8. Main Workflow Execution
def main():
    print(f"Intelligence engine run started at: {datetime.datetime.now().isoformat()}")
    
    # Startup validation of environment variables
    if not verify_environment():
        sys.exit(1)
        
    global state
    state = prune_state(state, max_age_days=60)
    
    # Step 1: Ingestion
    new_articles = ingest_all()
    if not new_articles:
        print("No new articles discovered since the last execution.")
        return
        
    print(f"Ingested {len(new_articles)} new potential articles.")
    
    # Step 2: Synthesis
    brief_content = run_gemini_synthesis(new_articles)
    if not brief_content:
        print("Brief generation failed: empty synthesis returned from model.")
        sys.exit(1)
        
    # Step 3: Write Output File to Hugo content directory
    today_str = datetime.date.today().isoformat()
    brief_filename = f"weekly_brief_{today_str}.md"
    hugo_content_dir = os.path.join(WORKSPACE_DIR, "sunilkandola-hugo", "content", "intel")
    brief_filepath = os.path.join(hugo_content_dir, brief_filename)
    
    # Generate Hugo YAML Front Matter
    front_matter = f"""---
title: "Digital Asset Digest: {datetime.date.today().strftime('%d %B %Y')}"
date: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')}
draft: false
tags: ["digital-assets", "cbdc", "regulation", "tokenisation"]
categories: ["Intelligence"]
summary: "Weekly synthesis of wholesale banking, CBDCs, RWAs, and digital asset regulations."
---

"""
    
    try:
        os.makedirs(hugo_content_dir, exist_ok=True)
        with open(brief_filepath, "w", encoding="utf-8") as f:
            f.write(front_matter + brief_content)
        print(f"Brief written to Hugo content directory: {brief_filepath}")
    except Exception as e:
        log_error(f"Failed to write Hugo brief file: {e}")
        # Note: Do not exit here; continue to send email and save files locally
        
    # Step 4: Convert to HTML Newsletter
    subject = f"Digital Asset Digest: {today_str}"
    html_content = convert_markdown_to_newsletter_html(subject, today_str, brief_content)
    
    # Save HTML version locally (outside Hugo content layout)
    html_filename = f"weekly_brief_{today_str}.html"
    html_filepath = os.path.join(WORKSPACE_DIR, html_filename)
    try:
        with open(html_filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML newsletter saved to: {html_filepath}")
    except Exception as e:
        log_error(f"Failed to write HTML file: {e}")

    # Save Markdown version locally in workspace
    md_filepath = os.path.join(WORKSPACE_DIR, f"weekly_brief_{today_str}.md")
    try:
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(brief_content)
        print(f"Markdown brief saved to: {md_filepath}")
    except Exception as e:
        log_error(f"Failed to write local Markdown file: {e}")

    # Step 5: Deliver via Email
    sender = get_env_var('SMTP_USER')
    recipient = get_env_var('RECIPIENT_EMAIL')
    if not recipient:
        recipient = sender # Fallback to sending to oneself
        
    email_success = send_email(subject, brief_content, html_content, recipient)
    
    # Step 6: Commit state updates & execute Git auto-publish
    state["last_run"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for art in new_articles:
        if art["url"] not in state["processed_urls"]:
            state["processed_urls"][art["url"]] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        print("System state successfully committed locally.")
    except Exception as e:
        log_error(f"Failed to save system state: {e}")

    # Git Auto-Publish to Hugo repo (if exists)
    hugo_dir = os.path.join(WORKSPACE_DIR, "sunilkandola-hugo")
    if os.path.exists(os.path.join(hugo_dir, ".git")):
        try:
            print("Committing and pushing to Hugo repository...")
            subprocess.run(["git", "add", "content/intel/"], cwd=hugo_dir, check=True)
            subprocess.run(["git", "commit", "-m", f"Auto-publish weekly brief {today_str}"], cwd=hugo_dir, check=True)
            push_res = subprocess.run(["git", "push"], cwd=hugo_dir, capture_output=True, text=True)
            if push_res.returncode == 0:
                print("Successfully pushed to Hugo remote repository.")
            else:
                log_error(f"Git push failed: {push_res.stderr.strip()}")
                sys.exit(1)
        except Exception as e:
            log_error(f"Failed to run Git auto-publish on Hugo repo: {e}")
            sys.exit(1)
    else:
        print("Hugo Git repository not found at location. Skipping auto-publish steps.")

    if email_success:
        print("Email delivered successfully.")
    else:
        print("Email delivery failed — brief was still generated and published.")
        sys.exit(1)

if __name__ == "__main__":
    main()

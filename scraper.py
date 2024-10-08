#tompithsatom/qifshamotrenemail:0.1.0 - works perfectly
#still stable 0.1.1
#still stable 0.2.1/0 good
import sys
import os
import json
import time
import re
import requests
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from functools import wraps
import threading
import validators
import random
from urllib.parse import unquote
from collections import Counter
import logging
from bs4 import BeautifulSoup
from itertools import cycle
import subprocess
import csv
import urllib.request
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add these functions at the beginning of the file, after the imports

def get_vpn_servers():
    url = 'http://www.vpngate.net/api/iphone/'
    request = urllib.request.Request(url)
    response = urllib.request.urlopen(request)
    data = response.read().decode('utf-8')
    
    servers = []
    for row in csv.reader(data.splitlines()):
        if len(row) > 14 and row[0] != '*':
            servers.append({
                'country': row[6],
                'ip': row[1],
                'score': int(row[2]),
                'ping': int(row[3]),
                'speed': int(row[4]),
                'config_data': row[14]
            })
    
    return sorted(servers, key=lambda x: x['score'], reverse=True)

def connect_vpn(server):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(server['config_data'])
        temp_file_path = temp_file.name
    
    try:
        subprocess.run(['sudo', 'openvpn', '--config', temp_file_path], check=True)
        logger.info(f"Connected to VPN server in {server['country']}")
        return True
    except subprocess.CalledProcessError:
        logger.error("Failed to connect to VPN server")
        return False
    finally:
        os.unlink(temp_file_path)

def disconnect_vpn():
    try:
        subprocess.run(['sudo', 'killall', 'openvpn'], check=True)
        logger.info("Disconnected from VPN")
        return True
    except subprocess.CalledProcessError:
        logger.error("Failed to disconnect from VPN")
        return False

# Add a global variable to keep track of the current VPN server
current_vpn_server = None

# Add this new class definition
class CustomUserAgent:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'
        ]
    
    def random(self):
        return random.choice(self.user_agents)

# Initialize the CustomUserAgent
ua = CustomUserAgent()

app = Flask(__name__)

def get_emails(text, driver):
    # More comprehensive regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    potential_emails = re.findall(email_pattern, text)
    
    # Search for emails in href attributes
    links = driver.find_elements_by_xpath("//a[contains(@href, 'mailto:')]")
    for link in links:
        href = link.get_attribute('href')
        if href.startswith('mailto:'):
            potential_emails.append(unquote(href[7:]))  # Remove 'mailto:' and decode
    
    # Additional validation and filtering
    valid_emails = []
    for email in potential_emails:
        if validators.email(email):
            # Check if it's a Gmail address (modify if you want to include other domains)
            if email.lower().endswith('@gmail.com'):
                valid_emails.append(email.lower())  # Convert to lowercase for consistency
    
    return list(set(valid_emails))  # Remove duplicates

def save_emails(emails, output_file='emails.txt'):
    logger.info(f"Saving {len(emails)} emails to {output_file}...")
    try:
        with open(output_file, 'w') as f:
            for email in emails:
                f.write(email + '\n')
        logger.info("Emails saved successfully.")
    except Exception as e:
        logger.error(f"Error saving emails: {e}")

def send_to_webhook(emails, webhook_url, record_id):
    logger.info(f"Sending {len(emails)} emails to webhook: {webhook_url}")
    try:
        # Remove any potential duplicates and sort the emails
        unique_emails = sorted(set(emails))
        
        # Format the emails as a single comma-separated string
        formatted_emails = ', '.join(unique_emails)
        
        payload = {
            'emails': formatted_emails,
            'recordId': record_id
        }
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        logger.info("Emails and recordId sent to webhook successfully.")
    except Exception as e:
        logger.error(f"Error sending data to webhook: {e}")

def initialize_driver(max_attempts=5):
    logger.info("Initializing Selenium WebDriver...")
    attempts = 0
    while attempts < max_attempts:
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={ua.random()}")
            
            chrome_options.binary_location = "/usr/bin/google-chrome-stable"
            
            driver = webdriver.Chrome(options=chrome_options)
            
            # Test the connection by loading a simple page
            driver.set_page_load_timeout(30)  # Set a timeout for page load
            driver.get("https://www.google.com")
            
            logger.info("WebDriver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Error initializing WebDriver: {e}")
            attempts += 1
            if attempts < max_attempts:
                logger.info(f"Retrying. Attempt {attempts + 1} of {max_attempts}")
            if 'driver' in locals():
                driver.quit()
    
    logger.error(f"Failed to initialize WebDriver after {max_attempts} attempts.")
    return None

def generate_urls(names, domain, niches, num_pages=5):
    logger.info("Generating URLs...")
    urls = []
    for name in names:
        for niche in niches:
            for page in range(1, num_pages + 1):
                url = f"https://www.google.com/search?q=%22{name}%22+%22{domain}%22+%22{niche}%22&start={page}"
                urls.append(url)
    logger.info(f"Generated {len(urls)} URLs.")
    return urls

def scrape_emails_from_url(driver, url, email_counter, consecutive_zero_count):
    logger.info(f"Scraping emails from URL: {url}")
    # Set a new random user agent for each request
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": ua.random()})
    driver.get(url)
    
    # Add a small random delay after loading the page
    time.sleep(random.uniform(1, 3))  # Random delay between 1 and 3 seconds
    
    page_source = driver.page_source
    emails = get_emails(page_source, driver)
    
    # Update the counter with new emails
    for email in emails:
        email_counter[email] += 1
    
    unique_emails = set(emails)
    logger.info(f"Found {len(unique_emails)} unique emails on this page.")

    # Check if we've hit consecutive zero results
    if consecutive_zero_count >= 2:
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Check for normal search results
        search_results = soup.find_all('div', class_='g')
        if search_results:
            logger.info("Page is okay: Normal search results found.")
        else:
            # Check for potential issues
            captcha = soup.find('div', id='captcha-form')
            if captcha:
                logger.warning("CAPTCHA detected on the page.")
            elif "unusual traffic" in page_source.lower():
                logger.warning("Unusual traffic message detected.")
            elif "blocked" in page_source.lower():
                logger.warning("IP might be blocked by Google.")
            else:
                logger.warning("Unexpected page content. Dumping HTML:")
                logger.warning(page_source[:1000])  # Log first 1000 characters of HTML
    
    return unique_emails

def scrape_emails(names, domain, niches, webhook_url=None, record_id=None, all_emails=None, email_counter=None):
    global current_vpn_server
    logger.info("Starting a scraper run...")
    
    # Connect to VPN if not already connected
    if current_vpn_server is None:
        servers = get_vpn_servers()
        for server in servers:
            if connect_vpn(server):
                current_vpn_server = server
                break
        if current_vpn_server is None:
            logger.error("Failed to connect to any VPN server. Exiting scrape_emails.")
            return set(), Counter(), names, niches

    driver = initialize_driver()
    if driver is None:
        logger.error("Failed to initialize WebDriver after multiple attempts. Exiting scrape_emails.")
        return set(), Counter(), names, niches

    if all_emails is None:
        all_emails = set()
    if email_counter is None:
        email_counter = Counter()
    
    total_combinations = len(names) * len(niches)
    completed_combinations = 0
    
    start_time = time.time()
    last_pause_time = start_time
    backoff_time = 60
    max_pages_per_combination = 5
    consecutive_zero_count = 0

    remaining_names = []
    remaining_niches = []

    for name in names:
        for niche in niches:
            urls = generate_urls([name], domain, [niche], num_pages=max_pages_per_combination)
            emails_found_for_combination = False

            for url_index, url in enumerate(urls):
                current_time = time.time()
                time_since_last_pause = current_time - last_pause_time

                if time_since_last_pause >= 300:
                    logger.info("Process has been running for 5 minutes. Implementing 280-second wait...")
                    time.sleep(280)
                    last_pause_time = time.time()
                    logger.info("Resuming after 280-second wait.")

                try:
                    emails = scrape_emails_from_url(driver, url, email_counter, consecutive_zero_count)
                    
                    if emails:
                        all_emails.update(emails)
                        emails_found_for_combination = True
                        consecutive_zero_count = 0
                        logger.info(f"Found {len(emails)} emails for {name} + {niche} on page {url_index + 1}")
                    else:
                        logger.info(f"No emails found for {name} + {niche} on page {url_index + 1}")
                        consecutive_zero_count += 1

                    if consecutive_zero_count >= 3:
                        logger.info("Three consecutive zero results. Analyzing page content.")
                        # The page analysis is now done in scrape_emails_from_url
                        remaining_names = names[names.index(name):]
                        remaining_niches = niches[niches.index(niche):]
                        driver.quit()
                        return all_emails, email_counter, remaining_names, remaining_niches

                    if url_index == max_pages_per_combination - 1 and not emails_found_for_combination:
                        logger.info(f"No emails found for {name} + {niche} after checking {max_pages_per_combination} pages.")

                    delay = random.uniform(3, 7)
                    logger.info(f"Waiting for {delay:.2f} seconds before the next request...")
                    time.sleep(delay)
                except Exception as e:
                    logger.error(f"Error scraping URL {url}: {e}")
                    logger.info("Reinitializing WebDriver...")
                    driver.quit()
                    driver = initialize_driver()
                    if driver is None:
                        logger.error("Failed to reinitialize WebDriver. Exiting scrape_emails.")
                        return all_emails, email_counter, names[names.index(name):], niches[niches.index(niche):]
                    continue

            completed_combinations += 1
            progress = (completed_combinations / total_combinations) * 100
            logger.info(f"Search progress: {progress:.2f}% completed")

    driver.quit()
    logger.info("WebDriver closed.")
    
    # Disconnect from VPN at the end of the scraping run
    disconnect_vpn()
    current_vpn_server = None

    return all_emails, email_counter, [], []  # No remaining names or niches if we've completed all

def manage_scraping_runs(names, domain, niches, webhook_url=None, record_id=None):
    all_emails = set()
    email_counter = Counter()
    run_count = 1

    while names and niches:
        logger.info(f"Starting scraping run #{run_count}")
        emails, counter, remaining_names, remaining_niches = scrape_emails(names, domain, niches, webhook_url, record_id, all_emails, email_counter)
        all_emails.update(emails)
        email_counter.update(counter)

        if remaining_names:
            logger.info("Starting a new thread with remaining names and niches")
            thread = threading.Thread(target=scrape_emails, args=(remaining_names, domain, remaining_niches, webhook_url, record_id, all_emails, email_counter))
            thread.start()
            thread.join()  # Wait for the thread to complete before continuing

        names = remaining_names
        niches = remaining_niches
        run_count += 1

    email_list = list(all_emails)
    save_emails(email_list)
    
    if webhook_url:
        send_to_webhook(email_list, webhook_url, record_id)
    
    logger.info(f"All scraping runs finished. Total unique emails collected: {len(email_list)}")
    logger.info("Email frequency:")
    for email, count in email_counter.most_common():
        logger.info(f"{email}: {count} times")
    
    return email_list

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == os.environ.get('GOOGLE_API_KEY'):
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated

def background_scrape(names_list, domain, niches_list, webhook_url, record_id):
    emails = manage_scraping_runs(names_list, domain, niches_list, webhook_url, record_id)
    logger.info(f"Background scraping completed. Total emails found: {len(emails)}")

@app.route('/scrape', methods=['POST'])
@require_api_key
def scrape():
    logger.info("Received scrape request")
    data = request.json
    names = data.get('names', '')
    domain = data.get('domain', '')
    niches = data.get('niche', '')
    webhook_url = data.get('webhook', '')
    record_id = data.get('recordId', '')

    logger.info(f"Scrape request parameters: names={names}, domain={domain}, niches={niches}")

    names_list = [name.strip() for name in names.split(',') if name.strip()]
    niches_list = [niche.strip() for niche in niches.split(',') if niche.strip()]

    # Start the scraping process in a background thread
    thread = threading.Thread(target=background_scrape, args=(names_list, domain, niches_list, webhook_url, record_id))
    thread.start()
    
    logger.info(f"Scraping started for record ID: {record_id}")
    return jsonify({'message': 'Scraping started, will be sent to:', 'recordId': record_id}), 200

if __name__ == '__main__':
    logger.info("Starting the Flask application")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
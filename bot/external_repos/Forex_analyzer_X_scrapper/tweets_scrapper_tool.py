from seleniumbase import SB
from bs4 import BeautifulSoup
import time
import urllib.parse
import sys
import csv
import re
import random
import requests
import os
import shutil
import google.generativeai as genai
import pathlib

# --- Default Configuration ---
# These will be used if the user doesn't provide their own inputs.
DEFAULT_EMAIL = "Email@gmail.com"
DEFAULT_PASSWORD = "password"
DEFAULT_USERNAME = "username"
DEFAULT_KEYWORDS = ["Eurusd 4h,$BTCUSD"]

DEFAULT_START_DATE = ""
DEFAULT_END_DATE = ""
# IMPORTANT: Replace "YOUR_GEMINI_API_KEY" with your actual Gemini API key get it from https://aistudio.google.com/apikey
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"  # <--- REPLACE WITH YOUR KEY

# --- Default Gemini Prompt ---
DEFAULT_GEMINI_PROMPT = """ edit gemini prompt here """

# --- Helper Functions (Original logic preserved) ---
def is_valid_date(date_string):
    """Checks if a date string is in YYYY-MM-DD format."""
    return re.match(r'^\d{4}-\d{2}-\d{2}$', date_string)

def realistic_sleep(min_time, max_time):
    """Sleeps for a random duration within a given range."""
    time.sleep(random.uniform(min_time, max_time))

def download_images(image_urls, output_dir, tweet_id):
    """Downloads images from a list of URLs and returns their local paths."""
    downloaded_paths = []
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, img_url in enumerate(image_urls):
        try:
            response = requests.get(img_url, stream=True)
            response.raise_for_status()

            file_extension = os.path.splitext(img_url.split('?')[0])[-1]
            if not file_extension:
                file_extension = '.jpg'

            image_filename = f"{tweet_id}_image_{i}{file_extension}"
            image_path = os.path.join(output_dir, image_filename)

            with open(image_path, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            downloaded_paths.append(image_path)
            print(f"Downloaded: {image_filename}")
            realistic_sleep(0.5, 1.5)
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {img_url}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while downloading {img_url}: {e}")
    return downloaded_paths

def scrape_tweets(sb, seen_tweet_urls):
    """Scrolls through the current page and scrapes all tweets with realistic delays."""
    tweets_data = []
    last_height = sb.execute_script("return document.body.scrollHeight")

    while True:
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        print("Scrolling down...")
        print("Waiting for new tweets to load (25-35 seconds)...")
        realistic_sleep(25, 35)

        page_source = sb.get_page_source()
        soup = BeautifulSoup(page_source, 'html.parser')
        tweet_containers = soup.find_all('article', {'data-testid': 'tweet'})
        print(f"Found {len(tweet_containers)} tweet containers on this scroll.")

        if not tweet_containers:
            print("No new tweet containers found.")
            break

        new_tweets_found_on_scroll = False
        for tweet_container in tweet_containers:
            author, tweet_text, tweet_url, tweet_date = "N/A", "N/A", "N/A", "N/A"
            image_urls = []

            author_element = tweet_container.find('div', {'data-testid': 'User-Name'})
            if author_element:
                author_links = author_element.find_all('a', {'role': 'link'})
                for link in author_links:
                    if link.text.strip().startswith('@'):
                        author = link.text.strip()
                        break

            tweet_text_element = tweet_container.find('div', {'data-testid': 'tweetText'})
            if tweet_text_element:
                tweet_text = tweet_text_element.get_text(strip=True)

            time_element = tweet_container.find('time')
            if time_element:
                if time_element.parent and time_element.parent.has_attr('href'):
                    tweet_url = "https://twitter.com" + time_element.parent['href']
                if time_element.has_attr('datetime'):
                    tweet_date = time_element['datetime']

            media_elements = tweet_container.find_all('img', class_='css-9pa8cd')
            for img_tag in media_elements:
                img_src = img_tag.get('src')
                if img_src and "pbs.twimg.com/media/" in img_src:
                    image_urls.append(img_src)

            if tweet_url not in seen_tweet_urls:
                seen_tweet_urls.add(tweet_url)
                tweets_data.append({
                    'author': author, 'text': tweet_text, 'url': tweet_url,
                    'date': tweet_date, 'image_urls': image_urls,
                    'downloaded_image_paths': []  # Will be populated after downloading
                })
                cleaned_author = author.encode("ascii", "ignore").decode("ascii")
                cleaned_text = tweet_text.encode("ascii", "ignore").decode("ascii")
                print(f"Scraped: {cleaned_author} - {cleaned_text[:30]}... (Images: {len(image_urls)})")
                new_tweets_found_on_scroll = True

        new_height = sb.execute_script("return document.body.scrollHeight")
        if not new_tweets_found_on_scroll and new_height == last_height:
            print("Reached the end of the page.")
            break
        last_height = new_height

    return tweets_data

# --- MODIFIED Gemini API Function ---
def get_gemini_prediction(keyword, all_tweets_data, custom_prompt):
    """Analyzes tweet data and images using Gemini, associating images with authors."""
    print(f"\n--- Analyzing data for '{keyword}' with Gemini API ---")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error configuring Gemini API. Check your API key. Error: {e}")
        return

    # Build the prompt for Gemini, associating images with authors
    prompt_parts = [custom_prompt, "\n--- Tweet Data & Associated Images ---\n"]

    for tweet in all_tweets_data:
        # Add the text part of the tweet first
        prompt_parts.append(f"Author: {tweet['author']}\nTweet: {tweet['text']}\nURL: {tweet['url']}\n")

        # Now, add images and explicitly state who they belong to
        if tweet['downloaded_image_paths']:
            prompt_parts.append(f"Images from Author {tweet['author']}:")
            for image_path in tweet['downloaded_image_paths']:
                try:
                    # This is the key change: Upload the image right after stating the author
                    prompt_parts.append(genai.upload_file(str(image_path)))
                except Exception as e:
                    print(f"Warning: Could not upload image {image_path}. Skipping. Error: {e}")
        prompt_parts.append("\n---\n") # Separator between tweets

    # Call the Gemini API
    try:
        print("Generating report with Gemini... This may take a moment.")
        model = genai.GenerativeModel(model_name="gemini-2.5-pro")
        response = model.generate_content(prompt_parts, request_options={"timeout": 600})

        report_filename = f"gemini_report_{keyword.replace(' ', '_')}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Successfully saved Gemini analysis to: {report_filename}")

    except Exception as e:
        print(f"An error occurred while calling the Gemini API: {e}")


# --- Main Script ---
# --- Interactive Setup ---
print("--- Twitter Scraper & Gemini Analyzer ---")
print("\n" + "="*50)
print("! ! ! W A R N I N G ! ! !")
print("This tool works by acting like a real human user to avoid")
print("getting blocked. This means it will be SLOW. It will pause")
print("for long, random intervals. Please be patient and let it run.")
print("="*50 + "\n")

user_keywords_str = input(f"Enter keywords separated by commas (e.g., Eurusd, Usdjpy, (or press Enter for default: {' '.join(DEFAULT_KEYWORDS)}): ")
user_start_date = input(f"Enter START date in YYYY-MM-DD format (or press Enter for none): ")
user_end_date = input(f"Enter END date in YYYY-MM-DD format (or press Enter for none): ")
use_default_prompt = input("Use default Gemini prompt? (Y/n): ").lower()

user_gemini_prompt = DEFAULT_GEMINI_PROMPT
if use_default_prompt == 'n':
    print("\nEnter your custom multi-line prompt. Press Ctrl+D (Linux/Mac) or Ctrl+Z then Enter (Windows) when done.")
    user_gemini_prompt = sys.stdin.read()

# Use user inputs or fall back to defaults
KEYWORDS = user_keywords_str.split(",") if user_keywords_str else DEFAULT_KEYWORDS
START_DATE = user_start_date if user_start_date else DEFAULT_START_DATE
END_DATE = user_end_date if user_end_date else DEFAULT_END_DATE
EMAIL = DEFAULT_EMAIL
PASSWORD = DEFAULT_PASSWORD
USERNAME = DEFAULT_USERNAME

# --- Validation ---
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    print("\nError: Please set your GEMINI_API_KEY in the script before running.")
    sys.exit(1)
if START_DATE and not is_valid_date(START_DATE):
    print(f"\nError: Invalid START_DATE format: {START_DATE}. Please use YYYY-MM-DD.")
    sys.exit(1)
if END_DATE and not is_valid_date(END_DATE):
    print(f"\nError: Invalid END_DATE format: {END_DATE}. Please use YYYY-MM-DD.")
    sys.exit(1)

with SB(uc=True, headless=False) as sb:
    # --- Original Login Logic (Preserved as requested) ---
    print("Opening Twitter login page...")
    sb.open("https://twitter.com/i/flow/login")

    try:
        print("Entering email...")
        sb.wait_for_element_present('input[name="text"]', timeout=15)
        realistic_sleep(1, 2)
        sb.type('input[name="text"]', EMAIL)
        realistic_sleep(0.5, 1)
        sb.click('button:contains("Next")')
        print("Email entered, clicked Next.")
    except Exception as e:
        print(f"Error during email entry: {e}")
        sb.save_screenshot("login_error.png")
        sys.exit(1)

    print("Waiting for next step after email entry...")
    realistic_sleep(4, 6)

    if sb.is_element_present('input[name="text"]'):
        try:
            print("Username/phone verification step detected. Entering username...")
            realistic_sleep(1, 2)
            sb.type('input[name="text"]', USERNAME)
            realistic_sleep(0.5, 1)
            sb.click('button:contains("Next")')
            print("Username entered, clicked Next.")
        except Exception as e:
            print(f"Error during username/phone verification: {e}")
            sb.save_screenshot("login_error.png")
            sys.exit(1)

    try:
        print("Entering password...")
        sb.wait_for_element_present('input[name="password"]', timeout=15)
        realistic_sleep(1, 2)
        sb.type('input[name="password"]', PASSWORD)
        realistic_sleep(0.5, 1)
        sb.click('button[data-testid="LoginForm_Login_Button"]')
        print("Password entered, clicked Login.")
    except Exception as e:
        print(f"Error during password entry: {e}")
        sb.save_screenshot("login_error.png")
        sys.exit(1)

    print("\nLogin successful. Starting keyword searches...")
    realistic_sleep(2, 4)

    for keyword in KEYWORDS:
        print(f"\n--- Starting search for keyword: {keyword} ---")
        keyword_images_dir = f"images_{keyword.replace(' ', '_')}"

        search_query = urllib.parse.quote(keyword)
        SEARCH_URL = f"https://twitter.com/search?q={search_query}"
        if START_DATE:
            SEARCH_URL += f"%20until%3A{END_DATE}" if END_DATE else ""
            SEARCH_URL += f"%20since%3A{START_DATE}"
        SEARCH_URL += "&src=typed_query&f=top"

        print(f"Navigating to search URL: {SEARCH_URL}")
        sb.open(SEARCH_URL)

        seen_tweet_urls = set()
        print("\n--- Scraping Top Tweets ---")
        sb.wait_for_element_present('div[data-testid="primaryColumn"]', timeout=20)
        
        all_tweets_for_keyword = scrape_tweets(sb, seen_tweet_urls)
        print(f"Found {len(all_tweets_for_keyword)} Top tweets for {keyword}.")

        if not all_tweets_for_keyword:
            print(f"No tweets found for '{keyword}'. Skipping to next keyword.")
            continue
            
        # Download images and store their paths within the tweet data
        print("\n--- Downloading Images ---")
        for tweet_data in all_tweets_for_keyword:
            tweet_id = tweet_data['url'].split('/')[-1] if tweet_data['url'] != "N/A" else f"no_url_{random.randint(1000,9999)}"
            downloaded_paths = download_images(tweet_data['image_urls'], keyword_images_dir, tweet_id)
            tweet_data['downloaded_image_paths'] = downloaded_paths

        # Call Gemini with the complete, structured data
        get_gemini_prediction(keyword, all_tweets_for_keyword, user_gemini_prompt)

        # Clean up temporary image files
        print(f"Cleaning up temporary files for {keyword}...")
        if os.path.exists(keyword_images_dir):
            shutil.rmtree(keyword_images_dir)
        print("Cleanup complete.")

    print("\nAll keyword searches complete.")
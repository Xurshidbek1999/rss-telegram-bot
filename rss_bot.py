import os
import time
import hashlib
import feedparser
import requests
from io import BytesIO
from googletrans import Translator
from telegram import Bot, InputMediaPhoto
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Load .env locally (in hosting use secrets)
load_dotenv()  

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_IDS = os.getenv("CHANNEL_IDS", "").split(",")  # comma-separated
RSS_FEEDS = os.getenv("RSS_FEEDS", "").split(",")
LANG_TARGET = os.getenv("LANG_TARGET", "en")
DB_FILE = os.getenv("DB_FILE", "posted.txt")

bot = Bot(token=BOT_TOKEN)
translator = Translator()

if not os.path.exists(DB_FILE):
    open(DB_FILE, "w").close()

with open(DB_FILE, "r", encoding="utf-8") as f:
    posted = set(line.strip() for line in f if line.strip())

def make_id(entry):
    s = entry.get("link", "") + entry.get("title", "")
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    if "media_thumbnail" in entry:
        return entry.media_thumbnail[0].get("url")
    if "summary" in entry and "<img" in entry.summary:
        import re
        m = re.search(r'<img[^>]+src=["\'](.*?)["\']', entry.summary)
        if m:
            return m.group(1)
    return None

def generate_hashtags(text):
    words = [w.strip(".,:;\"'()[]") for w in text.split() if len(w) > 4]
    tags = []
    for w in words:
        w2 = ''.join(ch for ch in w if ch.isalnum())
        if not w2: continue
        if len(tags) >= 5: break
        tags.append("#" + w2.capitalize())
    return " ".join(tags)

def format_post(title, summary, url):
    tags = generate_hashtags(title)
    post = f"📰 *{title}*\n\n{summary}\n\n🔗 [Read more]({url})\n\n{tags}"
    return post

def process_feed(feed_url):
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:5]:
        uid = make_id(entry)
        if uid in posted:
            continue
        title = entry.get("title", "")
        link = entry.get("link", "")
        summary = entry.get("summary", "")
        # translate
        try:
            t_title = translator.translate(title, dest=LANG_TARGET).text
            t_summary = translator.translate(summary, dest=LANG_TARGET).text
        except Exception:
            t_title = title
            t_summary = summary
        image_url = extract_image(entry)
        post_text = format_post(t_title, t_summary, link)
        for ch in CHANNEL_IDS:
            if not ch: continue
            try:
                if image_url:
                    r = requests.get(image_url, timeout=6)
                    if r.status_code == 200:
                        bot.send_photo(chat_id=ch, photo=BytesIO(r.content),
                                       caption=post_text, parse_mode=ParseMode.MARKDOWN)
                    else:
                        bot.send_message(chat_id=ch, text=post_text, parse_mode=ParseMode.MARKDOWN)
                else:
                    bot.send_message(chat_id=ch, text=post_text, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                print("Send error:", e)
        # mark posted
        with open(DB_FILE, "a", encoding="utf-8") as f:
            f.write(uid + "\n")
        posted.add(uid)
        time.sleep(1)

if __name__ == "__main__":
    # one run - suitable for hosting (host will restart script or keep it running)
    for url in RSS_FEEDS:
        if url.strip():
            process_feed(url.strip())
    print("Run finished.")

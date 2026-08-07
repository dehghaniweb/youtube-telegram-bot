import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

CHANNELS_FILE = "channels.txt"
STATE_FILE = "state.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"


def load_channels():
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_feed(channel_id):
    url = (
        "https://www.youtube.com/feeds/videos.xml?"
        + urllib.parse.urlencode({"channel_id": channel_id})
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def parse_feed(data):
    root = ET.fromstring(data)

    channel_name = ""
    title = ""
    video_id = ""
    video_url = ""
    published = ""

    author = root.find(f"{ATOM}author/{ATOM}name")
    if author is not None:
        channel_name = author.text or ""

    entry = root.find(f"{ATOM}entry")

    if entry is None:
        return None

    title_element = entry.find(f"{ATOM}title")
    if title_element is not None:
        title = title_element.text or ""

    video_element = entry.find(f"{YT}videoId")
    if video_element is not None:
        video_id = video_element.text or ""

    published_element = entry.find(f"{ATOM}published")
    if published_element is not None:
        published = published_element.text or ""

    if video_id:
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    if not video_id or not title or not video_url:
        return None

    return {
        "channel_name": channel_name,
        "video_id": video_id,
        "title": title,
        "url": video_url,
        "published": published
    }


def send_telegram(message):
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": "false"
    }).encode("utf-8")

    request = urllib.request.Request(
        TELEGRAM_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def main():
    channels = load_channels()
    state = load_state()

    print(f"Checking {len(channels)} YouTube channels...")

    first_run = not bool(state)
    changed = False

    for channel_id in channels:
        try:
            data = get_feed(channel_id)
            video = parse_feed(data)

            if not video:
                print(f"No video found: {channel_id}")
                continue

            latest_video_id = video["video_id"]
            old_video_id = state.get(channel_id)

            # First run:
            # Save current video but don't send it.
            if first_run or old_video_id is None:
                state[channel_id] = latest_video_id
                changed = True

                print(
                    f"Initialized: {video['channel_name']} - "
                    f"{video['title']}"
                )
                continue

            # No new video
            if latest_video_id == old_video_id:
                print(
                    f"No new video: {video['channel_name']}"
                )
                continue

            # New video
            message = (
                f"🎬 ویدیوی جدید\n\n"
                f"📺 {video['channel_name']}\n"
                f"🎞 {video['title']}\n\n"
                f"🔗 {video['url']}"
            )

            send_telegram(message)

            print(
                f"NEW VIDEO: {video['channel_name']} - "
                f"{video['title']}"
            )

            state[channel_id] = latest_video_id
            changed = True

        except Exception as e:
            print(f"ERROR {channel_id}: {e}")

    if changed:
        save_state(state)

    print(
        "Finished:",
        datetime.now(timezone.utc).isoformat()
    )


if __name__ == "__main__":
    main()

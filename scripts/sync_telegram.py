import json
import os
import pathlib
import urllib.request
import urllib.parse

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
IMAGES = DOCS / "images"
STATE_FILE = DOCS / "state.json"
PHOTOS_FILE = DOCS / "photos.json"

DOCS.mkdir(exist_ok=True)
IMAGES.mkdir(exist_ok=True)

def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))

def download(url, path):
    with urllib.request.urlopen(url) as response:
        path.write_bytes(response.read())

state = {"offset": 0}
if STATE_FILE.exists():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))

photos = []
if PHOTOS_FILE.exists():
    photos = json.loads(PHOTOS_FILE.read_text(encoding="utf-8"))

known_ids = {item["id"] for item in photos}

params = urllib.parse.urlencode({
    "offset": state.get("offset", 0),
    "timeout": 0,
    "allowed_updates": json.dumps(["channel_post"]),
})

updates = get_json(f"{API}/getUpdates?{params}")

for update in updates.get("result", []):
    state["offset"] = update["update_id"] + 1

    post = update.get("channel_post")
    if not post or "photo" not in post:
        continue

    photo = post["photo"][-1]
    file_id = photo["file_id"]
    unique_id = photo["file_unique_id"]

    if unique_id in known_ids:
        continue

    file_info = get_json(f"{API}/getFile?file_id={urllib.parse.quote(file_id)}")
    file_path = file_info["result"]["file_path"]

    ext = pathlib.Path(file_path).suffix or ".jpg"
    local_name = f"{unique_id}{ext}"
    local_path = IMAGES / local_name

    download(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}", local_path)

    photos.insert(0, {
        "id": unique_id,
        "image": f"images/{local_name}",
        "caption": post.get("caption", ""),
        "date": post.get("date"),
        "telegram_message_id": post.get("message_id"),
    })

STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
PHOTOS_FILE.write_text(json.dumps(photos, indent=2, ensure_ascii=False), encoding="utf-8")

import json
import os
import pathlib
import re
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

SYNC_TAG_LENIN_RE = re.compile(r"(?:^|\s)#?Sync_Tag\s*:\s*Lenin\b", re.IGNORECASE)
LENIN_RE = re.compile(r"\blenin\b", re.IGNORECASE)
NON_PERSON_LENIN_RE = re.compile(
    r"\b(?:lenin\s+(?:mausoleum|maosoleum|prize|portrait)|order\s+of\s+lenin)\b",
    re.IGNORECASE,
)
POSTER_RE = re.compile(r"\bposter\b", re.IGNORECASE)
ARTWORK_RE = re.compile(r"\b(painting|drawing|art)\b", re.IGNORECASE)

def has_sync_tag_lenin(text):
    return SYNC_TAG_LENIN_RE.search(text or "") is not None

def clean_caption(text):
    text = SYNC_TAG_LENIN_RE.sub(" ", text or "")
    return re.sub(r"[ \t]{2,}", " ", text).strip()

def lenin_person_text(text):
    return NON_PERSON_LENIN_RE.sub(" ", text or "")

def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))

def download(url, path):
    with urllib.request.urlopen(url) as response:
        path.write_bytes(response.read())

state = {"offset": 0}
if STATE_FILE.exists():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))

lenin_tagged_ids = set(state.get("lenin_tagged_ids", []))

photos = []
if PHOTOS_FILE.exists():
    photos = json.loads(PHOTOS_FILE.read_text(encoding="utf-8"))

for item in photos:
    caption = item.get("caption", "")
    if has_sync_tag_lenin(caption):
        lenin_tagged_ids.add(item["id"])
        item["caption"] = clean_caption(caption)

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

    caption = post.get("caption", "")
    if has_sync_tag_lenin(caption):
        lenin_tagged_ids.add(unique_id)

    file_info = get_json(f"{API}/getFile?file_id={urllib.parse.quote(file_id)}")
    file_path = file_info["result"]["file_path"]

    ext = pathlib.Path(file_path).suffix or ".jpg"
    local_name = f"{unique_id}{ext}"
    local_path = IMAGES / local_name

    download(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}", local_path)

    photos.insert(0, {
        "id": unique_id,
        "image": f"images/{local_name}",
        "caption": clean_caption(caption),
        "date": post.get("date"),
        "telegram_message_id": post.get("message_id"),
    })

state["lenin_tagged_ids"] = sorted(lenin_tagged_ids)
STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
PHOTOS_FILE.write_text(json.dumps(photos, indent=2, ensure_ascii=False), encoding="utf-8")

def caption_text(item):
    return item.get("caption", "")

def is_lenin(item):
    if item.get("id") in lenin_tagged_ids:
        return True
    return LENIN_RE.search(lenin_person_text(caption_text(item))) is not None

def is_lenin_poster(item):
    text = caption_text(item)
    return is_lenin(item) and POSTER_RE.search(text) is not None

def is_lenin_art(item):
    text = caption_text(item)
    return is_lenin(item) and ARTWORK_RE.search(text) is not None

lenin_posters = []
lenin_artworks = []
lenin_photos = []

for item in photos:
    if not is_lenin(item):
        continue

    if is_lenin_poster(item):
        lenin_posters.append(item)
    elif is_lenin_art(item):
        lenin_artworks.append(item)
    else:
        lenin_photos.append(item)

(DOCS / "lenin_posters.json").write_text(
    json.dumps(lenin_posters, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

(DOCS / "lenin_artworks.json").write_text(
    json.dumps(lenin_artworks, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

(DOCS / "lenin_photos.json").write_text(
    json.dumps(lenin_photos, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

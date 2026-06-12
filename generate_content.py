"""
Nexora Labs - TikTok Motivation Auto Generator
Dijalankan otomatis via GitHub Actions setiap hari
"""

import os
import json
import random
import textwrap
from pathlib import Path
from datetime import datetime

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]   # Set di GitHub Secrets
GDRIVE_CREDS    = os.environ["GDRIVE_CREDS_JSON"]  # JSON string dari service account
GROQ_API_KEY    = os.environ["GROQ_API_KEY"]

CANVAS_W, CANVAS_H = 1080, 1920
SLIDES_PER_POST    = 5
OUTPUT_DIR         = Path("output_slides")

# ─── FONTS ─────────────────────────────────────────────────────────────────────
# DejaVu sudah built-in di Linux runner GitHub Actions
FONT_TITLE  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_BODY   = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# ─── GROQ: Generate Quotes ──────────────────────────────────────────────────────
def generate_quotes() -> list[str]:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a raw, authentic motivational voice in the style of @vleucs. "
                    "Write 5 short, hard-hitting English motivation quotes. "
                    "No fluff. Each quote max 15 words. "
                    "Return ONLY a JSON array of 5 strings, nothing else."
                )
            },
            {"role": "user", "content": "Generate 5 quotes for today's post."}
        ],
        "temperature": 0.9,
        "max_tokens": 300
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    content = content.replace("```json", "").replace("```", "").strip()
    return json.loads(content)


# ─── IMAGE GENERATION ──────────────────────────────────────────────────────────
def grunge_texture(w: int, h: int) -> np.ndarray:
    """Generate noise-based grunge texture."""
    base = np.zeros((h, w, 3), dtype=np.uint8)
    # Dark red-black gradient base
    for y in range(h):
        ratio = y / h
        base[y, :, 0] = int(40 * ratio + 10)   # R: dark red tint
        base[y, :, 1] = int(5 * ratio)           # G: near zero
        base[y, :, 2] = int(5 * ratio)           # B: near zero
    # Grain noise
    noise = np.random.randint(-30, 30, (h, w, 3), dtype=np.int16)
    result = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return result


def make_slide(quote: str, slide_num: int, total: int) -> Image.Image:
    # Background
    arr = grunge_texture(CANVAS_W, CANVAS_H)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Optional: dark vignette overlay
    vignette = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for i in range(200):
        alpha = int(120 * (i / 200))
        vdraw.rectangle([i, i, CANVAS_W - i, CANVAS_H - i], outline=(0, 0, 0, alpha))
    img.paste(Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB"))
    draw = ImageDraw.Draw(img)

    # Red accent line (top & bottom)
    draw.rectangle([80, 160, CANVAS_W - 80, 165], fill=(180, 0, 0))
    draw.rectangle([80, CANVAS_H - 165, CANVAS_W - 80, CANVAS_H - 160], fill=(180, 0, 0))

    # Quote text (centered vertically)
    try:
        font_quote  = ImageFont.truetype(FONT_TITLE, 72)
        font_accent = ImageFont.truetype(FONT_BODY, 38)
        font_counter = ImageFont.truetype(FONT_BODY, 32)
    except IOError:
        font_quote = font_accent = font_counter = ImageFont.load_default()

    # Word-wrap quote
    wrapped = textwrap.fill(quote.upper(), width=18)
    lines = wrapped.split("\n")
    line_h = 88
    total_text_h = len(lines) * line_h
    y_start = (CANVAS_H - total_text_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        text_w = bbox[2] - bbox[0]
        x = (CANVAS_W - text_w) // 2
        y = y_start + i * line_h
        # Shadow
        draw.text((x + 3, y + 3), line, font=font_quote, fill=(80, 0, 0))
        draw.text((x, y), line, font=font_quote, fill=(255, 255, 255))

    # Branding
    brand = "NEXORA LABS"
    bbox = draw.textbbox((0, 0), brand, font=font_accent)
    bw = bbox[2] - bbox[0]
    draw.text(((CANVAS_W - bw) // 2, 100), brand, font=font_accent, fill=(180, 0, 0))

    # Slide counter
    counter = f"{slide_num}/{total}"
    draw.text((CANVAS_W - 100, CANVAS_H - 120), counter,
              font=font_counter, fill=(120, 120, 120))

    return img


# ─── GOOGLE DRIVE UPLOAD ───────────────────────────────────────────────────────
def get_drive_service():
    creds_data = json.loads(GDRIVE_CREDS)
    creds = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def upload_to_drive(service, filepath: Path, folder_id: str) -> str:
    meta = {
        "name": filepath.name,
        "parents": [folder_id]
    }
    media = MediaFileUpload(str(filepath), mimetype="image/jpeg", resumable=True)
    file = service.files().create(body=meta, media_body=media, fields="id").execute()
    return file.get("id")


# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("🚀 Nexora Labs - Content Generator starting...")
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 1. Generate quotes
    print("📝 Generating quotes via Groq...")
    quotes = generate_quotes()
    print(f"   Got {len(quotes)} quotes")

    # 2. Generate slides
    print("🎨 Rendering slides...")
    slide_paths = []
    for i, quote in enumerate(quotes[:SLIDES_PER_POST], start=1):
        img = make_slide(quote, i, SLIDES_PER_POST)
        ts = datetime.now().strftime("%Y%m%d")
        fname = OUTPUT_DIR / f"slide_{ts}_{i}.jpg"
        img.save(fname, "JPEG", quality=92)
        slide_paths.append(fname)
        print(f"   Slide {i}: {fname.name}")

    # 3. Upload to Google Drive
    print("☁️  Uploading to Google Drive...")
    service = get_drive_service()
    for path in slide_paths:
        file_id = upload_to_drive(service, path, DRIVE_FOLDER_ID)
        print(f"   Uploaded: {path.name} → ID: {file_id}")

    print("✅ Done! Make.com will pick up the files and post to TikTok.")


if __name__ == "__main__":
    main()

"""
Kenn - TikTok Motivation Auto Generator
"""

import os
import json
import textwrap
from pathlib import Path

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont

GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
CANVAS_W, CANVAS_H = 1080, 1920
SLIDES_PER_POST    = 5
OUTPUT_DIR         = Path("latest_slides")

FONT_TITLE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_BODY  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Tiap slide beda tema warna
THEMES = [
    {"name": "Crimson",  "base": (50, 5,  5),  "accent": (200, 0,   0)},
    {"name": "Cobalt",   "base": (5,  10, 50), "accent": (0,   80, 220)},
    {"name": "Forest",   "base": (5,  30, 10), "accent": (0,  160,  60)},
    {"name": "Violet",   "base": (20, 5,  40), "accent": (140,  0, 200)},
    {"name": "Ember",    "base": (40, 15, 0),  "accent": (220, 100,  0)},
]

def generate_quotes():
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
                    "You are a raw, authentic motivational voice. "
                    "Write 5 short, hard-hitting English motivation quotes. "
                    "No fluff. Each quote max 15 words. "
                    "Return ONLY a JSON array of 5 strings, nothing else."
                )
            },
            {"role": "user", "content": "Generate 5 quotes for today."}
        ],
        "temperature": 0.9,
        "max_tokens": 300
    }
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers, json=payload, timeout=30
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    content = content.replace("```json", "").replace("```", "").strip()
    return json.loads(content)

def grunge_texture(w, h, base_color):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    r, g, b = base_color
    for y in range(h):
        ratio = y / h
        arr[y, :, 0] = int(r * ratio + 8)
        arr[y, :, 1] = int(g * ratio + 4)
        arr[y, :, 2] = int(b * ratio + 4)
    noise = np.random.randint(-25, 25, (h, w, 3), dtype=np.int16)
    return np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)

def make_slide(quote, slide_num, total):
    theme  = THEMES[(slide_num - 1) % len(THEMES)]
    img    = Image.fromarray(grunge_texture(CANVAS_W, CANVAS_H, theme["base"]))
    draw   = ImageDraw.Draw(img)
    accent = theme["accent"]

    # Accent lines
    draw.rectangle([80, 160, CANVAS_W-80, 165], fill=accent)
    draw.rectangle([80, CANVAS_H-165, CANVAS_W-80, CANVAS_H-160], fill=accent)

    try:
        font_quote   = ImageFont.truetype(FONT_TITLE, 72)
        font_brand   = ImageFont.truetype(FONT_BODY,  38)
        font_counter = ImageFont.truetype(FONT_BODY,  32)
    except IOError:
        font_quote = font_brand = font_counter = ImageFont.load_default()

    # Quote text
    wrapped = textwrap.fill(quote.upper(), width=18)
    lines   = wrapped.split("\n")
    line_h  = 88
    y_start = (CANVAS_H - len(lines) * line_h) // 2

    for i, line in enumerate(lines):
        bbox   = draw.textbbox((0, 0), line, font=font_quote)
        text_w = bbox[2] - bbox[0]
        x = (CANVAS_W - text_w) // 2
        y = y_start + i * line_h
        # Shadow dengan warna accent gelap
        shadow = tuple(max(0, c - 120) for c in accent)
        draw.text((x+3, y+3), line, font=font_quote, fill=shadow)
        draw.text((x, y),     line, font=font_quote, fill=(255, 255, 255))

    # Branding "KENN"
    brand = "KENN"
    bbox  = draw.textbbox((0, 0), brand, font=font_brand)
    draw.text(((CANVAS_W - (bbox[2]-bbox[0])) // 2, 100),
              brand, font=font_brand, fill=accent)

    # Slide counter
    draw.text((CANVAS_W-100, CANVAS_H-120), f"{slide_num}/{total}",
              font=font_counter, fill=(120, 120, 120))

    return img

def main():
    print("🚀 Kenn - Content Generator starting...")
    OUTPUT_DIR.mkdir(exist_ok=True)

    for old in OUTPUT_DIR.glob("*.jpg"):
        old.unlink()

    print("📝 Generating quotes via Groq...")
    quotes = generate_quotes()
    print(f"   Got {len(quotes)} quotes")

    print("🎨 Rendering slides...")
    for i, quote in enumerate(quotes[:SLIDES_PER_POST], start=1):
        img   = make_slide(quote, i, SLIDES_PER_POST)
        fname = OUTPUT_DIR / f"slide_{i}.jpg"
        img.save(fname, "JPEG", quality=92)
        theme = THEMES[(i-1) % len(THEMES)]
        print(f"   Slide {i} [{theme['name']}]: {fname.name}")

    print("✅ Done!")

if __name__ == "__main__":
    main()

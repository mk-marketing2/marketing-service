"""
Backfill Imagen 4 generated thumbnails for all existing markdown articles.
Saves images to marketing-site-next/public/images/{slug}.png
Updates frontmatter thumbnail field to /images/{slug}.png
"""
import os
import re
import json
import ssl
import base64
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found")
    exit(1)

content_dir = Path("marketing-site-next/src/content")
images_dir = Path("marketing-site-next/public/images")
images_dir.mkdir(parents=True, exist_ok=True)

def generate_imagen4(prompt: str, slug: str) -> str | None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-fast-generate-001:predict?key={GEMINI_API_KEY}"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            body = json.loads(resp.read().decode())
            preds = body.get('predictions', [])
            if preds and 'bytesBase64Encoded' in preds[0]:
                img_bytes = base64.b64decode(preds[0]['bytesBase64Encoded'])
                img_path = images_dir / f"{slug}.png"
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                print(f"  ✅ Image saved: {img_path.name} ({len(img_bytes):,} bytes)")
                return f"/images/{slug}.png"
    except urllib.error.HTTPError as e:
        err = json.loads(e.read().decode())
        print(f"  ❌ API error {e.code}: {err.get('error', {}).get('message', '')[:100]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    return None

for md_file in sorted(content_dir.glob("*.md")):
    slug = md_file.stem
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Skip if already has a local image (not Picsum or blank)
    thumb_match = re.search(r'^thumbnail:\s*"(.*?)"', content, re.MULTILINE)
    current_thumb = thumb_match.group(1) if thumb_match else ""
    if current_thumb.startswith("/images/") and not current_thumb.startswith("/images/test_"):
        print(f"⏭️  Skipping {slug} (already has local image)")
        continue

    # Extract title for building the image prompt
    title_match = re.search(r'^title:\s*"(.*?)"', content, re.MULTILINE)
    title = title_match.group(1) if title_match else slug

    # Generate a relevant English prompt from the title
    image_prompt = (
        f"A professional, photorealistic, cinematic photograph for a Japanese restaurant consulting article titled: "
        f"{title}. Beautiful lighting, modern interior, food industry, high quality, 8k"
    )

    print(f"📷 Generating for: {slug}")
    print(f"   Title: {title[:60]}")

    thumb_path = generate_imagen4(image_prompt, slug)
    if not thumb_path:
        print(f"  ⚠️ Skipping frontmatter update for {slug}")
        continue

    # Update frontmatter
    if thumb_match:
        new_content = re.sub(
            r'^thumbnail:\s*".*?"',
            f'thumbnail: "{thumb_path}"',
            content,
            flags=re.MULTILINE
        )
    else:
        parts = content.split("---", 2)
        if len(parts) >= 3:
            parts[1] = parts[1].rstrip() + f'\nthumbnail: "{thumb_path}"\n'
            new_content = "---".join(parts)
        else:
            new_content = content

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  ✅ Updated frontmatter")

print("\n🎉 Backfill complete!")

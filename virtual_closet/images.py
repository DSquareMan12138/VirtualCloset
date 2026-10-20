import hashlib
import io
import os
from functools import lru_cache
from threading import RLock
from PIL import Image, ImageOps
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 24_000_000
_cutout_lock = RLock()

def read_rgba(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Image exceeds the 20 MB limit.")
    with Image.open(io.BytesIO(raw)) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError("Image exceeds the 24 megapixel limit.")
        return ImageOps.exif_transpose(source).convert("RGBA")

def composite(image, color="#ffffff"):
    rgba = image.convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", rgba.size, color), rgba).convert("RGB")

def read_image(raw):
    return composite(read_rgba(raw))

def image_hash(raw):
    return hashlib.sha256(raw).hexdigest()

def thumbnail_bytes(image):
    thumb = image.copy()
    thumb.thumbnail((1000, 1000))
    buffer = io.BytesIO()
    thumb.save(buffer, format="PNG")
    return buffer.getvalue()

# Lightweight rembg model. Set VIRTUALCLOSET_REMBG_MODEL=u2net to restore
# the larger model when edge accuracy matters more than processing time.
@lru_cache(maxsize=2)
def _session(model_name=None):
    from rembg import new_session
    model_name = model_name or os.environ.get("VIRTUALCLOSET_REMBG_MODEL", "u2netp")
    return new_session(model_name, providers=["CPUExecutionProvider"])

def remove_background(raw):
    from rembg import remove
    image = read_rgba(raw)
    image.thumbnail((1000, 1000))
    with _cutout_lock:
        result = remove(image, session=_session())
    return thumbnail_bytes(result.convert("RGBA"))

def display_image(raw, color="#ffffff"):
    return composite(read_rgba(raw), color)


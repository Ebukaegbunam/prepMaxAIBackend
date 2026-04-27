"""Photo compression utility for AI vision requests."""
import io


def compress_for_ai(image_bytes: bytes, max_edge: int = 1024, quality: int = 75) -> bytes:
    """Resize to max_edge on longest side, re-encode as JPEG at given quality."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")

    w, h = img.size
    if w > max_edge or h > max_edge:
        scale = max_edge / max(w, h)
        new_w = max(1, round(w * scale))
        new_h = max(1, round(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def make_thumbnail(image_bytes: bytes, size: tuple[int, int] = (256, 256)) -> bytes:
    """Create a square thumbnail, cropped to center."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    thumb = ImageOps.fit(img, size, Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()

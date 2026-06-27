"""Multi-modal vision — screen analysis, OCR, webcam capture.

Combines screenshot capture with AI-powered description and OCR.
Falls back through providers (OpenRouter vision → Groq vision).
"""

import base64
import io
import sys
from pathlib import Path

try:
    from PIL import Image, ImageGrab
    _PIL = True
except ImportError:
    _PIL = False

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _capture_screen() -> bytes | None:
    if _PYAUTOGUI:
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    if _PIL:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    return None


def _capture_webcam() -> bytes | None:
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        _, buf = cv2.imencode(".png", frame)
        return buf.tobytes()
    except ImportError:
        return None


def _image_to_b64(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode()


def describe_screen(question: str = "What is on this screen?") -> str:
    img_bytes = _capture_screen()
    if not img_bytes:
        return "Could not capture screen."

    b64 = _image_to_b64(img_bytes)

    try:
        from or_client import client
        response = client.vision(
            prompt=question,
            image_b64=b64,
            mime="image/png",
        )
        return response or "No description generated."
    except Exception as e:
        print(f"[Vision] OpenRouter vision failed: {e}")

    try:
        from memory.config_manager import get_groq_key
        key = get_groq_key()
        if key:
            from groq_client import GroqClient
            gc = GroqClient(api_key=key)
            response = gc.chat(
                system="You are a vision assistant. Describe what you see in detail.",
                messages=[],
                user_msg=question,
            )
            return response or "No description generated."
    except Exception as e:
        print(f"[Vision] Groq vision failed: {e}")

    return "No vision provider available."


def ocr_screen() -> str:
    img_bytes = _capture_screen()
    if not img_bytes:
        return "Could not capture screen."

    try:
        import pytesseract
        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip() or "No text found on screen."
    except ImportError:
        return "pytesseract not installed. Run: pip install pytesseract"
    except Exception as e:
        return f"OCR failed: {e}"


def capture_webcam(question: str = "What do you see?") -> str:
    img_bytes = _capture_webcam()
    if not img_bytes:
        return "Could not access webcam."

    b64 = _image_to_b64(img_bytes)

    try:
        from or_client import client
        response = client.vision(
            prompt=question,
            image_b64=b64,
            mime="image/png",
        )
        return response or "No description generated."
    except Exception as e:
        print(f"[Vision] Webcam vision failed: {e}")
        return f"Webcam capture failed: {e}"

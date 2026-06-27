import sys
import io
from pathlib import Path

try:
    import qrcode
    _QRCODE = True
except ImportError:
    _QRCODE = False

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def qr_tools(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[QR] {action}")

    try:
        if action in ("generate", "create", "make"):
            data = params.get("data", "").strip()
            if not data:
                return "Data/content is required for QR generation."

            if not _QRCODE:
                return "qrcode library not installed. Run: pip install qrcode[pil]"

            save_path = params.get("save_path", "").strip()
            if not save_path:
                save_path = str(_get_base_dir() / "qr_generated.png")

            fill_color = params.get("fill_color", "#00d4ff")
            back_color = params.get("back_color", "#000000")

            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color=fill_color, back_color=back_color)
            img.save(save_path)

            return f"QR code saved to: {save_path}"

        elif action in ("read", "decode", "scan"):
            path = params.get("path", "").strip()
            if not path:
                return "Path to QR image is required."

            if not _PIL:
                return "PIL not installed. Run: pip install Pillow"

            try:
                from pyzbar.pyzbar import decode as pyzbar_decode
                img = Image.open(path)
                results = pyzbar_decode(img)
                if not results:
                    return "No QR code found in image."
                texts = [r.data.decode("utf-8") for r in results]
                return "\n".join(texts)
            except ImportError:
                return "pyzbar not installed. Run: pip install pyzbar"
            except Exception as e:
                return f"Failed to read QR: {e}"

        elif action == "read_screen":
            if not _PIL:
                return "PIL not installed."
            try:
                import pyautogui
                from pyzbar.pyzbar import decode as pyzbar_decode
                screenshot = pyautogui.screenshot()
                results = pyzbar_decode(screenshot)
                if not results:
                    return "No QR code found on screen."
                texts = [r.data.decode("utf-8") for r in results]
                return "\n".join(texts)
            except ImportError as e:
                return f"Missing library: {e}"
            except Exception as e:
                return f"Failed to scan screen: {e}"

        return (
            f"Unknown action: '{action}'. "
            f"Available: generate, read, read_screen"
        )

    except Exception as e:
        return f"qr_tools failed: {e}"

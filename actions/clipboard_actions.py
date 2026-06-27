import pyperclip


def clipboard_read() -> str:
    try:
        text = pyperclip.paste()
        return text if text else "Clipboard is empty."
    except Exception as e:
        return f"Failed to read clipboard: {e}"


def clipboard_write(text: str) -> str:
    try:
        pyperclip.copy(text)
        return f"Copied to clipboard: {text[:80]}"
    except Exception as e:
        return f"Failed to write clipboard: {e}"

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

try:
    import win32com.client
    _WIN32COM = True
except ImportError:
    _WIN32COM = False


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_NOTES_DIR = _get_base_dir() / "notes"
_NOTES_INDEX = _NOTES_DIR / "index.json"


def _ensure_notes_dir():
    _NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if not _NOTES_INDEX.exists():
        _NOTES_INDEX.write_text("[]", encoding="utf-8")


def _load_notes_index() -> list:
    _ensure_notes_dir()
    try:
        return json.loads(_NOTES_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_notes_index(index: list):
    _NOTES_INDEX.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def calendar_notes(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")
    category = params.get("category", "notes").strip().lower()

    if player:
        player.write_log(f"[CalNotes] {action}")

    try:
        if action in ("note", "save_note", "write_note"):
            title = params.get("title", "").strip() or f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            content = params.get("content", "").strip()
            if not content:
                return "Content is required."

            _ensure_notes_dir()
            file_path = _NOTES_DIR / f"{title.replace(' ', '_')}.txt"
            file_path.write_text(content, encoding="utf-8")

            index = _load_notes_index()
            index.append({
                "title": title,
                "file": str(file_path.name),
                "created": datetime.now().isoformat(),
                "category": category,
            })
            _save_notes_index(index)

            return f"Note saved: {file_path.name}"

        elif action in ("list_notes", "notes", "list"):
            index = _load_notes_index()
            if not index:
                return "No notes found."

            if category != "all":
                filtered = [n for n in index if n.get("category") == category]
            else:
                filtered = index

            if not filtered:
                return f"No notes in category '{category}'."

            lines = []
            for n in filtered[-20:]:
                created = n.get("created", "?")[:16].replace("T", " ")
                lines.append(f"{n['title']} ({created}) [{n.get('category','notes')}]")
            return "\n".join(lines)

        elif action in ("read_note", "read"):
            title = params.get("title", "").strip()
            if not title:
                return "Title is required."

            index = _load_notes_index()
            match = None
            for n in index:
                if title.lower() in n["title"].lower():
                    match = n
                    break
            if not match:
                return f"Note not found: {title}"

            file_path = _NOTES_DIR / match["file"]
            if not file_path.exists():
                return f"Note file missing: {match['file']}"

            content = file_path.read_text(encoding="utf-8")
            return f"{match['title']}:\n{content[:1000]}"

        elif action in ("delete_note", "delete"):
            title = params.get("title", "").strip()
            if not title:
                return "Title is required."

            index = _load_notes_index()
            match_idx = None
            for i, n in enumerate(index):
                if title.lower() in n["title"].lower():
                    match_idx = i
                    break
            if match_idx is None:
                return f"Note not found: {title}"

            match = index.pop(match_idx)
            file_path = _NOTES_DIR / match["file"]
            if file_path.exists():
                file_path.unlink()
            _save_notes_index(index)
            return f"Deleted note: {match['title']}"

        elif action in ("calendar", "events", "calendar_events"):
            if not _WIN32COM:
                return "pywin32 required for calendar. Run: pip install pywin32"

            days = int(params.get("days", 7))
            outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            calendar = outlook.GetDefaultFolder(9)
            appointments = calendar.Items

            end_date = datetime.now() + timedelta(days=days)
            appointments.Sort("[Start]")
            appointments.IncludeRecurrences = True

            try:
                restriction = f"[Start] <= '{end_date.strftime('%m/%d/%Y %H:%M %p')}'"
                appointments = appointments.Restrict(restriction)
            except Exception:
                pass

            events = []
            for appt in appointments:
                try:
                    start = appt.Start
                    if isinstance(start, datetime) and start >= datetime.now() - timedelta(days=1):
                        events.append({
                            "subject": appt.Subject or "(No subject)",
                            "start": start.strftime("%a %b %d %I:%M %p"),
                            "duration": f"{appt.Duration}min",
                            "location": appt.Location or "",
                        })
                except Exception:
                    pass
                if len(events) >= 20:
                    break

            if not events:
                return f"No upcoming events in the next {days} day(s)."

            lines = [f"Upcoming {days}d events:"]
            for e in events:
                loc = f" @ {e['location']}" if e["location"] else ""
                lines.append(f"  {e['start']} — {e['subject']}{loc} ({e['duration']})")
            return "\n".join(lines)

        return (
            f"Unknown action: '{action}'. "
            f"Available: note, list_notes, read_note, delete_note, calendar"
        )

    except Exception as e:
        return f"calendar_notes failed: {e}"

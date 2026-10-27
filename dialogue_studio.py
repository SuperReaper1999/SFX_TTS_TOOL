"""Local Kokoro dialogue authoring panel for SFX TTS Tool."""

import atexit
import csv
import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import audio_playback

KOKORO_VOICES = (
    "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "af_heart", "af_bella", "af_nicole", "am_fenrir", "am_michael", "am_onyx",
)
SPEAKER_PROFILES = {
    "Autumn": {"voice": "bf_emma", "notes": "Young adult woman; guarded but compassionate."},
    "Reeves": {"voice": "bm_george", "notes": "Adult man; weary, practical, dry survivor humour."},
    "Summer": {"voice": "bf_isabella", "notes": "Adult woman; reassuring, capable and warm."},
    "Narrator": {"voice": "bm_fable", "notes": "Measured, cinematic post-apocalyptic narration."},
    "Custom": {"voice": "bf_emma", "notes": ""},
}


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_") or "dialogue_line"


LINE_FIELDS = ("speaker", "voice", "line_id", "text", "notes", "speed")


def config_dir() -> Path:
    """Per-user settings folder, shared with the designer's preset favourites."""
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "SfxTtsTool"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "SfxTtsTool"


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_speaker_profiles(path: Path) -> dict[str, dict[str, str]]:
    saved = load_json(path)
    if not isinstance(saved, dict):
        return {name: dict(profile) for name, profile in SPEAKER_PROFILES.items()}
    return {
        str(name): {"voice": str(profile.get("voice")), "notes": str(profile.get("notes", ""))}
        for name, profile in saved.items()
        if isinstance(profile, dict) and profile.get("voice") in KOKORO_VOICES
    }


def next_line_id(line_id: str) -> str:
    """autumn_intro_01 -> autumn_intro_02; IDs without a trailing number gain _02."""
    match = re.search(r"(\d+)$", line_id)
    if not match:
        return f"{line_id}_02"
    return line_id[:match.start()] + str(int(match.group(1)) + 1).zfill(len(match.group(1)))


def parse_script(path: Path, profiles: dict[str, dict[str, str]], default_speaker: str, default_voice: str,
                 default_speed: float, existing: list[dict[str, str]]) -> list[dict[str, str]]:
    """Read dialogue lines from a CSV (header row with at least a "text" column) or a plain-text script.

    Plain-text lines read "Speaker: what they say"; lines without a speaker use the default speaker,
    and blank lines or lines starting with # are skipped. Missing line IDs are numbered per speaker,
    skipping IDs already in ``existing``.
    """
    rows: list[tuple[int, dict[str, str]]] = []
    content = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        reader = csv.DictReader(content.splitlines())
        columns = {name.strip().lower(): name for name in reader.fieldnames or []}
        if "text" not in columns:
            raise ValueError("The CSV needs a header row with a 'text' column (optional: speaker, line_id, voice, speed, notes).")
        for number, record in enumerate(reader, start=2):
            row = {key: (record.get(columns[key]) or "").strip() for key in ("speaker", "line_id", "id", "text", "voice", "speed", "notes") if key in columns}
            if row.get("text"):
                row["line_id"] = row.get("line_id") or row.get("id", "")
                rows.append((number, row))
    else:
        for number, raw in enumerate(content.splitlines(), start=1):
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z][\w .'-]{0,40}):\s+(.+)$", text)
            rows.append((number, {"speaker": match.group(1).strip(), "text": match.group(2).strip()} if match else {"text": text}))

    taken = {(line["speaker"], line["line_id"]) for line in existing}
    seen: set[tuple[str, str]] = set()
    lines: list[dict[str, str]] = []
    for number, row in rows:
        speaker = row.get("speaker") or default_speaker
        profile = profiles.get(speaker, {})
        voice = row.get("voice") or profile.get("voice") or default_voice
        if voice not in KOKORO_VOICES:
            raise ValueError(f"Line {number}: unknown Kokoro voice '{voice}'.")
        try:
            speed = float(row.get("speed") or default_speed)
        except ValueError:
            raise ValueError(f"Line {number}: speed must be a number between 0.5 and 1.5.") from None
        if not 0.5 <= speed <= 1.5:
            raise ValueError(f"Line {number}: speed must be between 0.5 and 1.5.")
        if row.get("line_id"):
            # Explicit IDs replace a queued line with the same speaker and ID, so an edited script can be re-imported.
            line_id = safe_filename(row["line_id"])
            if (speaker, line_id) in seen:
                raise ValueError(f"Line {number}: {speaker} already has a line with ID '{line_id}' in this script.")
        else:
            line_id = f"{safe_filename(speaker).lower()}_01"
            while (speaker, line_id) in taken or (speaker, line_id) in seen:
                line_id = next_line_id(line_id)
        seen.add((speaker, line_id))
        lines.append({"speaker": speaker, "voice": voice, "line_id": line_id, "text": row["text"],
                      "notes": row.get("notes") or profile.get("notes", ""), "speed": str(speed)})
    return lines


def read_manifest_lines(path: Path) -> list[dict[str, str]]:
    """Return the line entries of an existing manifest, or an empty list if it is missing or unreadable."""
    try:
        lines = json.loads(path.read_text(encoding="utf-8")).get("lines", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [line for line in lines if isinstance(line, dict)] if isinstance(lines, list) else []


def kokoro_language_for_voice(voice: str) -> str:
    return "b" if voice.startswith("b") else "a"


KOKORO_NOT_INSTALLED = "Kokoro is not installed. Run Install Local Kokoro TTS.bat (Windows) or install-local-kokoro-tts.sh (Linux) from this tool folder"


class KokoroWorker:
    """Keeps one kokoro_worker.py process running so the model loads once, not once per line."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._replies: "queue.Queue[dict | None]" = queue.Queue()
        self._lock = threading.Lock()
        self._next_id = 0
        self._tool_root = Path(__file__).resolve().parent
        self._log_path = self._tool_root / ".kokoro-cache" / "kokoro_worker.log"

    def _start(self) -> None:
        local_python = self._tool_root / ".python312" / ("python.exe" if os.name == "nt" else "bin/python3")
        python_executable = str(local_python) if local_python.is_file() else sys.executable
        cache_dir = self._tool_root / ".kokoro-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        existing_python_path = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = str(self._tool_root / ".local-tts") + (os.pathsep + existing_python_path if existing_python_path else "")
        environment["HF_HOME"] = str(cache_dir)
        environment["HF_HUB_CACHE"] = str(cache_dir / "huggingface")
        environment["TORCH_HOME"] = str(cache_dir / "torch")
        environment["XDG_CACHE_HOME"] = str(cache_dir)
        environment["PYTHONIOENCODING"] = "utf-8"
        log = self._log_path.open("w", encoding="utf-8")
        try:
            self._process = subprocess.Popen(
                [python_executable, "-u", str(self._tool_root / "kokoro_worker.py")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True, encoding="utf-8", env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as error:
            raise RuntimeError("Python could not be found for the local Kokoro generator.") from error
        finally:
            log.close()
        self._replies = queue.Queue()
        threading.Thread(target=self._read_replies, args=(self._process, self._replies), daemon=True).start()
        ready = self._wait_for_reply(120, "Kokoro took too long to start.")
        if not ready.get("ready"):
            self.stop()
            error = str(ready.get("error", ""))
            raise RuntimeError(KOKORO_NOT_INSTALLED if "kokoro" in error.lower() else f"Kokoro could not start:\n{error}")

    @staticmethod
    def _read_replies(process: subprocess.Popen, replies: "queue.Queue[dict | None]") -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            try:
                replies.put(json.loads(raw))
            except ValueError:
                continue
        replies.put(None)  # The worker exited.

    def _wait_for_reply(self, timeout: float, timeout_message: str) -> dict:
        try:
            message = self._replies.get(timeout=timeout)
        except queue.Empty:
            self.stop()
            raise RuntimeError(timeout_message) from None
        if message is None:
            self.stop()
            raise RuntimeError(f"Kokoro stopped unexpectedly. Details are in {self._log_path}:\n{self._log_tail()}")
        return message

    def _log_tail(self) -> str:
        try:
            return "\n".join(self._log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-8:])
        except OSError:
            return "No details were logged."

    def warm_up(self, voice: str) -> None:
        """Start the worker and load the model ahead of the first line; errors resurface when generating."""
        try:
            self._request({"warm_up": True, "language": kokoro_language_for_voice(voice)})
        except RuntimeError:
            pass

    def generate(self, text: str, voice: str, speed: float, output_path: Path) -> None:
        self._request({"text": text, "voice": voice, "language": kokoro_language_for_voice(voice), "speed": speed, "output": str(output_path)})

    def _request(self, request: dict) -> None:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._start()
            assert self._process is not None and self._process.stdin is not None
            self._next_id += 1
            request = {"id": self._next_id, **request}
            try:
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()
            except OSError:
                pass  # The reader reports the exit with the log details.
            reply = self._wait_for_reply(600, "Kokoro took too long to generate this line.")
            if not reply.get("ok"):
                raise RuntimeError(f"Kokoro generation failed:\n{reply.get('error') or 'No details returned.'}")

    def stop(self) -> None:
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        try:
            assert process.stdin is not None
            process.stdin.close()
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()


_worker = KokoroWorker()
atexit.register(_worker.stop)


def generate_kokoro_wav(text: str, voice: str, speed: float, output_path: Path) -> None:
    if not text.strip():
        raise ValueError("Enter dialogue text before generating speech.")
    if not 0.5 <= speed <= 1.5:
        raise ValueError("Speech speed must be between 0.5 and 1.5.")
    _worker.generate(text, voice, speed, output_path)
    if not output_path.is_file() or output_path.stat().st_size < 44:
        raise RuntimeError("Kokoro did not produce a valid WAV file.")


class DialogueStudio:
    """A Tk panel which queues and exports fully local Kokoro WAV dialogue."""

    def __init__(self, root: tk.Tk, set_status: Callable[[str], None]):
        self.root = root
        self.set_status = set_status
        self.profiles_path = config_dir() / "speaker_profiles.json"
        self.queue_path = config_dir() / "dialogue_queue.json"
        self.profiles = load_speaker_profiles(self.profiles_path)
        saved_queue = load_json(self.queue_path)
        saved_queue = saved_queue if isinstance(saved_queue, dict) else {}
        self.lines: list[dict[str, str]] = [
            {field: str(line.get(field, "")) for field in LINE_FIELDS}
            for line in saved_queue.get("lines", []) if isinstance(line, dict) and line.get("text")
        ] if isinstance(saved_queue.get("lines"), list) else []
        self.output_dir = tk.StringVar(value=str(saved_queue.get("output_dir") or Path.cwd() / "GeneratedDialogue"))
        first_speaker = "Autumn" if "Autumn" in self.profiles else next(iter(self.profiles), "Custom")
        first_profile = self.profiles.get(first_speaker, {"voice": KOKORO_VOICES[0], "notes": ""})
        self.speaker = tk.StringVar(value=first_speaker)
        self.voice = tk.StringVar(value=first_profile["voice"])
        self.line_id = tk.StringVar(value=f"{safe_filename(first_speaker).lower()}_intro_01")
        self.notes = tk.StringVar(value=first_profile["notes"])
        self.speed = tk.StringVar(value="1.0")
        self.tree: ttk.Treeview | None = None
        self.text: tk.Text | None = None
        self.profile_box: ttk.Combobox | None = None
        self.generate_current_button: ttk.Button | None = None
        self.generate_queue_button: ttk.Button | None = None
        self._warmed_up = False
        self.output_dir.trace_add("write", lambda *_arguments: self._save_queue())

    def build(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        parent.bind("<Map>", lambda _event: self._warm_up_once())

        info = ttk.LabelFrame(parent, text="Local Dialogue to WAV", padding=10)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        info.columnconfigure(0, weight=1)
        ttk.Label(
            info,
            text=("Runs Kokoro TTS locally: no API key, account, or per-line cost. The first generated line downloads "
                  "the model files once; later dialogue generation is offline. Character notes are kept in the manifest "
                  "for your authoring reference."),
            justify="left", wraplength=760,
        ).grid(row=0, column=0, sticky="w")

        form = ttk.LabelFrame(parent, text="Line", padding=10)
        form.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for column in (1, 3):
            form.columnconfigure(column, weight=1)

        ttk.Label(form, text="Speaker profile").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.profile_box = ttk.Combobox(form, textvariable=self.speaker, values=tuple(self.profiles), width=18)
        self.profile_box.grid(row=0, column=1, sticky="ew", pady=3)
        self.profile_box.bind("<<ComboboxSelected>>", self._apply_profile)
        ttk.Label(form, text="Kokoro voice").grid(row=0, column=2, sticky="w", padx=(12, 6), pady=3)
        ttk.Combobox(form, textvariable=self.voice, values=KOKORO_VOICES, state="readonly", width=16).grid(row=0, column=3, sticky="ew", pady=3)

        ttk.Label(form, text="Line ID").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(form, textvariable=self.line_id).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Speech speed (0.5–1.5)").grid(row=1, column=2, sticky="w", padx=(12, 6), pady=3)
        ttk.Entry(form, textvariable=self.speed).grid(row=1, column=3, sticky="ew", pady=3)

        ttk.Label(form, text="Character notes").grid(row=2, column=0, sticky="nw", padx=(0, 6), pady=(6, 3))
        ttk.Entry(form, textvariable=self.notes).grid(row=2, column=1, columnspan=3, sticky="ew", pady=(6, 3))
        ttk.Label(form, text="Dialogue text").grid(row=3, column=0, sticky="nw", padx=(0, 6), pady=(6, 3))
        self.text = tk.Text(form, height=5, wrap="word", undo=True)
        self.text.grid(row=3, column=1, columnspan=3, sticky="ew", pady=(6, 3))
        profile_actions = ttk.Frame(form)
        profile_actions.grid(row=4, column=1, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Button(profile_actions, text="Save Profile", command=self._save_profile).pack(side="left")
        ttk.Button(profile_actions, text="Delete Profile", command=self._delete_profile).pack(side="left", padx=6)
        ttk.Label(profile_actions, text="Type a new speaker name to create a profile from the current voice and notes.").pack(side="left", padx=6)

        output = ttk.Frame(parent)
        output.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="Output folder").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(output, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew")
        ttk.Button(output, text="Browse…", command=self._choose_output).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(output, text="Add Current Line", command=self._add_current).grid(row=1, column=0, pady=(8, 0), sticky="w")
        self.generate_current_button = ttk.Button(output, text="Generate Current WAV", command=self._generate_current)
        self.generate_current_button.grid(row=1, column=1, pady=(8, 0), sticky="w")

        queue_frame = ttk.LabelFrame(parent, text="Generation Queue (saved automatically)", padding=8)
        queue_frame.grid(row=3, column=0, sticky="nsew")
        queue_frame.columnconfigure(0, weight=1)
        queue_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(queue_frame, columns=("speaker", "line_id", "voice", "preview"), show="headings", height=9, selectmode="extended")
        for name, heading, width in (("speaker", "Speaker", 120), ("line_id", "Line ID", 190), ("voice", "Voice", 100), ("preview", "Text", 340)):
            self.tree.heading(name, text=heading)
            self.tree.column(name, width=width, stretch=name == "preview")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(queue_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        actions = ttk.Frame(queue_frame)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Import Script…", command=self._import_script).pack(side="left")
        ttk.Button(actions, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Clear Queue", command=self._clear_queue).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Preview Selected WAV", command=self._preview_selected).pack(side="left", padx=6)
        self._refresh_queue()
        ttk.Button(actions, text="Export Manifest", command=self._write_manifest).pack(side="right")
        self.generate_queue_button = ttk.Button(actions, text="Generate Queue", command=self._generate_queue)
        self.generate_queue_button.pack(side="right", padx=(0, 6))

    def _apply_profile(self, _event: object = None) -> None:
        profile = self.profiles.get(self.speaker.get())
        if profile is None:
            return
        self.voice.set(profile["voice"])
        self.notes.set(profile["notes"])
        self.line_id.set(f"{safe_filename(self.speaker.get()).lower()}_line_01")

    def _save_profile(self) -> None:
        name = self.speaker.get().strip()
        if not name:
            messagebox.showwarning("Dialogue Studio", "Type a speaker name before saving a profile."); return
        self.profiles[name] = {"voice": self.voice.get(), "notes": self.notes.get().strip()}
        self._store_profiles()
        self.set_status(f"Saved speaker profile: {name}")

    def _delete_profile(self) -> None:
        name = self.speaker.get().strip()
        if name not in self.profiles:
            messagebox.showwarning("Dialogue Studio", f"There is no saved profile called '{name}'."); return
        if not messagebox.askyesno("Dialogue Studio", f"Delete the speaker profile '{name}'? Queued lines keep their voice."):
            return
        del self.profiles[name]
        self._store_profiles()
        self.set_status(f"Deleted speaker profile: {name}")

    def _store_profiles(self) -> None:
        try:
            save_json(self.profiles_path, self.profiles)
        except OSError as error:
            self.set_status(f"Could not save speaker profiles: {error}")
        if self.profile_box is not None:
            self.profile_box.configure(values=tuple(self.profiles))

    def _save_queue(self) -> None:
        try:
            save_json(self.queue_path, {"version": 1, "output_dir": self.output_dir.get(), "lines": self.lines})
        except OSError as error:
            self.set_status(f"Could not save the dialogue queue: {error}")

    def _warm_up_once(self) -> None:
        if not self._warmed_up:
            self._warmed_up = True
            threading.Thread(target=_worker.warm_up, args=(self.voice.get(),), daemon=True).start()

    def _import_script(self) -> None:
        filename = filedialog.askopenfilename(title="Import dialogue script", filetypes=(
            ("Dialogue scripts", "*.csv *.txt"), ("CSV", "*.csv"), ("Text", "*.txt")))
        if not filename:
            return
        try:
            speed = float(self.speed.get())
        except ValueError:
            speed = 1.0
        try:
            imported = parse_script(Path(filename), self.profiles, self.speaker.get().strip() or "Custom", self.voice.get(),
                                    speed if 0.5 <= speed <= 1.5 else 1.0, self.lines)
        except (OSError, ValueError, csv.Error) as error:
            messagebox.showerror("Dialogue Studio", f"Could not import the script:\n{error}"); return
        positions = {(line["speaker"], line["line_id"]): index for index, line in enumerate(self.lines)}
        replaced = 0
        for line in imported:
            key = (line["speaker"], line["line_id"])
            if key in positions:
                self.lines[positions[key]] = line; replaced += 1
            else:
                positions[key] = len(self.lines); self.lines.append(line)
        self._refresh_queue(); self._save_queue()
        self.set_status(f"Imported {len(imported)} line(s) from {Path(filename).name}" + (f" ({replaced} replaced queued lines)" if replaced else ""))

    def _clear_queue(self) -> None:
        if self.lines and messagebox.askyesno("Dialogue Studio", f"Remove all {len(self.lines)} queued lines? Generated WAV files are kept."):
            self.lines.clear(); self._refresh_queue(); self._save_queue()

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.cwd()))
        if selected:
            self.output_dir.set(selected)

    def _current_line(self) -> dict[str, str]:
        assert self.text is not None
        try:
            speed = float(self.speed.get())
        except ValueError as error:
            raise ValueError("Speech speed must be a number between 0.5 and 1.5.") from error
        if not 0.5 <= speed <= 1.5:
            raise ValueError("Speech speed must be between 0.5 and 1.5.")
        return {
            "speaker": self.speaker.get(), "voice": self.voice.get(), "line_id": safe_filename(self.line_id.get()),
            "text": self.text.get("1.0", "end-1c").strip(), "notes": self.notes.get().strip(), "speed": str(speed),
        }

    def _add_current(self) -> None:
        try:
            line = self._current_line()
        except ValueError as error:
            messagebox.showwarning("Dialogue Studio", str(error)); return
        if not line["text"]:
            messagebox.showwarning("Dialogue Studio", "Enter dialogue text before adding it to the queue."); return
        self.lines.append(line); self._refresh_queue(); self._save_queue()
        self.line_id.set(next_line_id(line["line_id"]))
        assert self.text is not None
        self.text.delete("1.0", "end")
        self.set_status(f"Queued dialogue line: {line['line_id']}")

    def _refresh_queue(self) -> None:
        assert self.tree is not None
        self.tree.delete(*self.tree.get_children())
        for index, line in enumerate(self.lines):
            self.tree.insert("", "end", iid=str(index), values=(line["speaker"], line["line_id"], line["voice"], line["text"].replace("\n", " ")[:70]))

    def _remove_selected(self) -> None:
        assert self.tree is not None
        for index in sorted((int(item) for item in self.tree.selection()), reverse=True): self.lines.pop(index)
        self._refresh_queue(); self._save_queue()

    def _generate_current(self) -> None:
        try:
            line = self._current_line()
        except ValueError as error:
            messagebox.showwarning("Dialogue Studio", str(error)); return
        if not line["text"]:
            messagebox.showwarning("Dialogue Studio", "Enter dialogue text before generating it."); return
        self._start_generation([line])

    def _generate_queue(self) -> None:
        if not self.lines:
            messagebox.showwarning("Dialogue Studio", "Add at least one line to the generation queue."); return
        self._start_generation(list(self.lines))

    def _start_generation(self, lines: list[dict[str, str]]) -> None:
        self._set_busy(True); self.set_status(f"Generating {len(lines)} local Kokoro WAV file(s)…")
        threading.Thread(target=self._generate_worker, args=(lines,), daemon=True).start()

    def _generate_worker(self, lines: list[dict[str, str]]) -> None:
        try:
            directory = Path(self.output_dir.get()).expanduser(); directory.mkdir(parents=True, exist_ok=True)
            generated: list[dict[str, str]] = []
            for index, line in enumerate(lines, start=1):
                self.root.after(0, self.set_status, f"Generating {index}/{len(lines)} locally: {line['line_id']}")
                filename = f"{safe_filename(line['speaker'])}_{safe_filename(line['line_id'])}.wav"
                generate_kokoro_wav(line["text"], line["voice"], float(line["speed"]), directory / filename)
                generated.append({**line, "file": filename})
            self._write_manifest_file(directory, generated)
            self.root.after(0, self._generation_complete, directory, len(generated))
        except Exception as error:
            self.root.after(0, self._generation_failed, str(error))

    def _generation_complete(self, directory: Path, count: int) -> None:
        self._set_busy(False); self.set_status(f"Generated {count} local dialogue WAV file(s) in {directory}")
        messagebox.showinfo("Dialogue Studio", f"Generated {count} WAV file(s).\n\n{directory}")

    def _generation_failed(self, error: str) -> None:
        self._set_busy(False); self.set_status("Local dialogue generation failed."); messagebox.showerror("Dialogue Studio", error)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        if self.generate_current_button is not None: self.generate_current_button.configure(state=state)
        if self.generate_queue_button is not None: self.generate_queue_button.configure(state=state)

    def _write_manifest_file(self, directory: Path, lines: list[dict[str, str]]) -> Path:
        """Merge ``lines`` into the folder's manifest, so generating one line keeps every earlier entry."""
        path = directory / "dialogue_manifest.json"
        merged = read_manifest_lines(path)
        positions = {(line.get("speaker"), line.get("line_id")): index for index, line in enumerate(merged)}
        for line in lines:
            key = (line.get("speaker"), line.get("line_id"))
            if key in positions:
                merged[positions[key]] = {**merged[positions[key]], **line}
            else:
                positions[key] = len(merged)
                merged.append(line)
        path.write_text(json.dumps({"format": "dialogue-manifest-v1", "engine": "kokoro-local", "notes": "Assign each generated WAV to the dialogue line with the matching line ID.", "lines": merged}, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def _write_manifest(self) -> None:
        if not self.lines:
            messagebox.showwarning("Dialogue Studio", "Add dialogue lines before exporting a manifest."); return
        directory = Path(self.output_dir.get()).expanduser(); directory.mkdir(parents=True, exist_ok=True)
        self.set_status(f"Exported dialogue manifest: {self._write_manifest_file(directory, self.lines)}")

    def _preview_selected(self) -> None:
        assert self.tree is not None
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Dialogue Studio", "Select a queued line to preview its generated WAV file."); return
        line = self.lines[int(selected[0])]
        path = Path(self.output_dir.get()) / f"{safe_filename(line['speaker'])}_{safe_filename(line['line_id'])}.wav"
        if not path.is_file():
            messagebox.showwarning("Dialogue Studio", f"No generated WAV found yet for {line['line_id']}."); return
        try:
            if not audio_playback.play_wav(str(path)):
                messagebox.showwarning("Dialogue Studio", audio_playback.unavailable_reason())
        except Exception as error:
            messagebox.showerror("Dialogue Studio", f"Could not preview WAV:\n{error}")

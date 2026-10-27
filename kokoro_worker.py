"""Long-running Kokoro generator used by Dialogue Studio.

Loading Kokoro takes several seconds, so Dialogue Studio starts this once and
keeps it running. It reads one JSON request per line on stdin and answers each
with one JSON line on stdout:

    {"id": 1, "text": "...", "voice": "bf_emma", "language": "b", "speed": 1.0, "output": "/path/line.wav"}
    {"id": 1, "ok": true}   or   {"id": 1, "ok": false, "error": "..."}

A request with "warm_up": true (plus "language") only loads the model and that language's pipeline.

On start it sends {"ready": true}, or {"ready": false, "error": "..."} if Kokoro
cannot be imported. Library output goes to stderr so it cannot corrupt replies.
"""

from __future__ import annotations

import json
import sys
import traceback
import wave

REPO_ID = "hexgrad/Kokoro-82M"
SAMPLE_RATE = 24000


def main() -> int:
    replies = sys.stdout
    sys.stdout = sys.stderr

    def reply(message: dict) -> None:
        replies.write(json.dumps(message) + "\n")
        replies.flush()

    try:
        import numpy as np
        from kokoro import KModel, KPipeline
    except Exception as error:  # Reported to the app, which explains how to install Kokoro.
        reply({"ready": False, "error": f"{type(error).__name__}: {error}"})
        return 1

    model = None
    pipelines: dict[str, KPipeline] = {}
    reply({"ready": True})
    for raw in sys.stdin:
        if not raw.strip():
            continue
        request_id = None
        try:
            request = json.loads(raw)
            request_id = request.get("id")
            if model is None:
                model = KModel(repo_id=REPO_ID).eval()
            language = request["language"]
            if language not in pipelines:
                pipelines[language] = KPipeline(lang_code=language, repo_id=REPO_ID, model=model)
            if request.get("warm_up"):
                reply({"id": request_id, "ok": True})
                continue
            with wave.open(request["output"], "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(SAMPLE_RATE)
                for result in pipelines[language](request["text"], voice=request["voice"], speed=float(request["speed"]), split_pattern=r"\n+"):
                    if result.audio is not None:
                        audio = np.clip(result.audio.numpy(), -1.0, 1.0)
                        output.writeframes((audio * 32767).astype(np.int16).tobytes())
            reply({"id": request_id, "ok": True})
        except Exception as error:
            traceback.print_exc()
            reply({"id": request_id, "ok": False, "error": f"{type(error).__name__}: {error}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())

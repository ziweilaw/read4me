"""TTS providers. Each returns WAV bytes for one sentence. Add Kokoro/cloud providers here."""
from __future__ import annotations

import base64
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import os


def models_dir() -> Path:
    """Packaged app passes READ4ME_MODELS_DIR; in dev they live in sidecar/models."""
    return Path(os.environ.get("READ4ME_MODELS_DIR") or Path(__file__).resolve().parents[1] / "models")


_NOVELTY = {"Albert", "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Deranged", "Good News",
            "Hysterical", "Jester", "Organ", "Superstar", "Trinoids", "Whisper", "Wobble", "Zarvox", "Fred",
            "Junior", "Kathy", "Ralph", "Grandma", "Grandpa", "Eddy", "Flo", "Reed", "Rocko", "Sandy", "Shelley"}


class SystemProvider:
    """macOS `say` (use Premium/Enhanced voices for natural sound). TODO: Windows SAPI via pyttsx3."""
    id = "system"

    def voices(self) -> list[dict]:
        if sys.platform != "darwin":
            return []
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        voices = []
        for line in out.splitlines():
            m = re.match(r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2})\s+#", line)
            if m and m.group(2).startswith("en_"):
                name = m.group(1).strip()
                if name.split(" (")[0] in _NOVELTY:
                    continue
                quality = "premium" if "Premium" in name else "enhanced" if "Enhanced" in name else "standard"
                voices.append({"id": name, "name": name, "lang": m.group(2), "quality": quality})
        order = {"premium": 0, "enhanced": 1, "standard": 2}
        return sorted(voices, key=lambda v: order[v["quality"]])

    def synth(self, text: str, voice: str, wpm: int = 175) -> bytes:
        with tempfile.TemporaryDirectory() as d:
            aiff, wav = Path(d, "a.aiff"), Path(d, "a.wav")
            cmd = ["say", "-r", str(wpm), "-o", str(aiff)]
            if voice:
                cmd += ["-v", voice]
            subprocess.run(cmd + ["--", text], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", str(aiff), str(wav)], check=True)
            return wav.read_bytes()


class KokoroProvider:
    """Local neural TTS (Kokoro-82M via ONNX). Models live in sidecar/models/."""
    id = "kokoro"
    _VOICES = [("af_heart", "Heart (US, female)"), ("af_bella", "Bella (US, female)"), ("af_sarah", "Sarah (US, female)"),
               ("am_michael", "Michael (US, male)"), ("am_fenrir", "Fenrir (US, male)"),
               ("bf_emma", "Emma (UK, female)"), ("bm_george", "George (UK, male)")]
    _model = None

    @staticmethod
    def available() -> bool:
        d = models_dir()
        return (d / "kokoro-v1.0.onnx").exists() and (d / "voices-v1.0.bin").exists()

    def voices(self) -> list[dict]:
        return [{"id": v, "name": n, "lang": "en", "quality": "neural"} for v, n in self._VOICES]

    def synth(self, text: str, voice: str, wpm: int = 175) -> bytes:
        import io
        import soundfile as sf
        from kokoro_onnx import Kokoro
        if KokoroProvider._model is None:
            d = models_dir()
            KokoroProvider._model = Kokoro(str(d / "kokoro-v1.0.onnx"), str(d / "voices-v1.0.bin"))
        samples, sr = KokoroProvider._model.create(text, voice=voice or "af_heart", speed=1.0, lang="en-us")
        buf = io.BytesIO()
        sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
        return buf.getvalue()


PROVIDERS = {"system": SystemProvider()}
if KokoroProvider.available():
    PROVIDERS = {"kokoro": KokoroProvider(), **PROVIDERS}


def voices(provider: str = "kokoro" if "kokoro" in PROVIDERS else "system") -> list[dict]:
    return PROVIDERS[provider].voices()


def speak_b64(text: str, voice: str = "", provider: str = "kokoro" if "kokoro" in PROVIDERS else "system", wpm: int = 175) -> str:
    return base64.b64encode(PROVIDERS[provider].synth(text, voice, wpm)).decode()

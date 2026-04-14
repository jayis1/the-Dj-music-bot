"""
utils/dj.py — Radio DJ mode for MBot.

Generates Text-to-Speech DJ commentary between songs using Microsoft Edge TTS.
The DJ announces songs as they come up and gives transitions between tracks,
like a real radio station.

Requires: pip install edge-tts
"""

import asyncio
import logging
import os
import random
import tempfile

try:
    import edge_tts

    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logging.warning(
        "edge-tts not installed — DJ mode unavailable. Install with: pip install edge-tts"
    )


# ── DJ Message Templates ──────────────────────────────────────────

INTROS = [
    "Up next, {title}!",
    "Here's {title}.",
    "Let's go with {title}.",
    "This one's a great track, {title}.",
    "Coming up, it's {title}.",
    "Alright, next up is {title}.",
    "Get ready for {title}.",
    "And now, {title}.",
    "Turning it up with {title}.",
    "This is {title}, enjoy.",
    "Let's keep the music going with {title}.",
    "You're gonna love this one. {title}.",
]

OUTROS = [
    "That was {title}.",
    "Great track, {title}.",
    "Hope you enjoyed {title}.",
    "That was {title}. Nice one.",
    "And that's {title}.",
]

TRANSITIONS = [
    "That was {prev_title}. Coming up next, {next_title}.",
    "Moving on from {prev_title}. Next up, {next_title}!",
    "Alright, {prev_title} is done. Here comes {next_title}.",
    "Finished with {prev_title}. Let's get into {next_title}.",
    "{prev_title}, what a tune. Up next, {next_title}.",
    "Loved {prev_title}. Now let's bring you {next_title}.",
    "That was {prev_title}. And next up, {next_title}!",
]

OUTROS_FINAL = [
    "That was {title}, and that's all for now!",
    "That wraps things up with {title}. See you next time!",
    "Last one was {title}. The queue's empty, so I'll be right here when you need me.",
    "That was {title}. Nothing left in the queue, just holler when you want more!",
    "And that's the end of our set with {title}. Back whenever you're ready.",
]

STATION_IDS = [
    "You're listening to M Bot Radio.",
    "M Bot, your non-stop music companion.",
    "M Bot Radio, bringing the tunes to you.",
    "This is M Bot, keeping the music alive.",
    "M Bot Radio. All music, all the time.",
]

# ── Message Generation ─────────────────────────────────────────────


def generate_intro(title: str) -> str:
    """Generate a DJ intro message before a song starts."""
    msg = random.choice(INTROS).format(title=title)
    # 20% chance to prepend a station ID
    if random.random() < 0.2:
        msg = random.choice(STATION_IDS) + " " + msg
    return msg


def generate_outro(
    title: str, has_next: bool, next_title: str = None, queue_size: int = 0
) -> str:
    """Generate a DJ outro message after a song ends."""
    if has_next and next_title:
        # Specific transition naming the next track
        msg = random.choice(TRANSITIONS).format(prev_title=title, next_title=next_title)
    elif has_next:
        # Next track exists but title unknown
        msg = random.choice(OUTROS).format(title=title)
        if queue_size > 0:
            msg += f" {queue_size} more coming up."
    else:
        # Last song in queue
        msg = random.choice(OUTROS_FINAL).format(title=title)
    return msg


# ── TTS Generation ─────────────────────────────────────────────────

DEFAULT_VOICE = "en-US-AriaNeural"


async def list_voices(language: str = "en") -> list[dict]:
    """
    Return available TTS voices filtered by language prefix.
    Each entry is a dict with keys: Name, ShortName, Gender, Locale, etc.
    """
    if not EDGE_TTS_AVAILABLE:
        return []
    try:
        voices = await edge_tts.list_voices()
        return [v for v in voices if v["Locale"].startswith(language)]
    except Exception as e:
        logging.error(f"DJ: Failed to list TTS voices: {e}")
        return []


async def generate_tts(text: str, voice: str = DEFAULT_VOICE) -> str | None:
    """
    Generate a TTS audio file and return its path.
    Returns None if edge-tts is unavailable or generation fails.
    **The caller must delete the file after use via cleanup_tts_file().**
    """
    if not EDGE_TTS_AVAILABLE:
        logging.warning("DJ: edge-tts not available, skipping TTS.")
        return None

    if not text or not text.strip():
        return None

    path = None
    try:
        fd, path = tempfile.mkstemp(suffix=".mp3", prefix="dj_")
        os.close(fd)

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(path)

        logging.info(f"DJ: Generated TTS → {path} ({len(text)} chars, voice={voice})")
        return path
    except Exception as e:
        logging.error(f"DJ: Failed to generate TTS: {e}")
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        return None


def cleanup_tts_file(path: str):
    """Delete a generated TTS audio file. Safe to call from sync callbacks."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logging.debug(f"DJ: Cleaned up TTS file: {path}")
        except Exception as e:
            logging.warning(f"DJ: Failed to clean up {path}: {e}")

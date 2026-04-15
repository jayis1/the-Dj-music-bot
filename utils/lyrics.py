"""
utils/lyrics.py — Live lyrics for MBot.

Fetches synced or plain lyrics for the currently playing song.
Primary: syncedlyrics library (supports LRC providers).
Fallback: web scraping from lyricslrc.co and Musixmatch.
"""

import asyncio
import logging
import re
import urllib.parse

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import syncedlyrics

    SYNCED_LYRICS_AVAILABLE = True
except ImportError:
    SYNCED_LYRICS_AVAILABLE = False
    logging.debug(
        "syncedlyrics not installed — lyrics fallback to web scraping. Install with: pip install syncedlyrics"
    )


async def get_lyrics(title: str) -> str | None:
    """
    Fetch lyrics for a song by its title.
    Returns the lyrics text, or None if not found.
    """
    if not title:
        return None

    # Clean the title: remove "(Official Video)", feat., etc.
    clean = re.sub(
        r"\(.*?\)|\[.*?\]|\{.*?\}|feat\.?.*|ft\.?.*|official.*|lyrics?.*|music video.*|hd|4k|remastered.*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    # Primary: syncedlyrics
    if SYNCED_LYRICS_AVAILABLE:
        try:
            result = await _fetch_syncedlyrics(clean)
            if result:
                return result
        except Exception as e:
            logging.debug(f"Lyrics: syncedlyrics failed for '{clean}': {e}")

    # Fallback: web scraping
    if AIOHTTP_AVAILABLE:
        for fetcher in [_fetch_lyricslrcco, _fetch_musixmatch]:
            try:
                result = await fetcher(clean)
                if result:
                    return result
            except Exception as e:
                logging.debug(f"Lyrics: {fetcher.__name__} failed for '{clean}': {e}")
                continue

    return None


async def _fetch_syncedlyrics(query: str) -> str | None:
    """Fetch lyrics using the syncedlyrics library."""
    loop = asyncio.get_event_loop()

    def _sync_fetch():
        try:
            lrc = syncedlyrics.search(query)
            if lrc:
                # Strip LRC timestamps, return plain text
                lines = lrc.strip().split("\n")
                plain = []
                for line in lines:
                    # Remove [mm:ss.xx] timestamps
                    cleaned = re.sub(r"\[.*?\]", "", line).strip()
                    if cleaned:
                        plain.append(cleaned)
                text = "\n".join(plain)
                if len(text) > 20:
                    return text
        except Exception:
            pass
        return None

    result = await loop.run_in_executor(None, _sync_fetch)
    return result


async def _fetch_lyricslrcco(query: str) -> str | None:
    """Fetch from lyricslrc.co (free, no API key needed)."""
    search_url = f"https://lyricslrc.co/api/search?q={urllib.parse.quote(query)}"
    async with aiohttp.ClientSession() as session:
        async with session.get(
            search_url, timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
            if not data or not isinstance(data, list) or len(data) == 0:
                return None
            entry = data[0]
            lyric_url = entry.get("url") or entry.get("api")
            if not lyric_url:
                return None
            if lyric_url.startswith("/"):
                lyric_url = f"https://lyricslrc.co{lyric_url}"
            async with session.get(
                lyric_url, timeout=aiohttp.ClientTimeout(total=8)
            ) as resp2:
                if resp2.status != 200:
                    return None
                lyrics_data = await resp2.json(content_type=None)
                lyrics = (
                    lyrics_data.get("lyrics")
                    or lyrics_data.get("synced")
                    or lyrics_data.get("plain")
                )
                if lyrics and isinstance(lyrics, str) and len(lyrics) > 20:
                    return lyrics
    return None


async def _fetch_musixmatch(query: str) -> str | None:
    """Fetch from Musixmatch's public share pages (no API key)."""
    search_url = f"https://www.musixmatch.com/search/{urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()
            match = re.search(r'href="(/lyrics/[^"]+)"', html)
            if not match:
                return None
            track_url = f"https://www.musixmatch.com{match.group(1)}"
            async with session.get(
                track_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)
            ) as resp2:
                if resp2.status != 200:
                    return None
                html2 = await resp2.text()
                lyrics_match = re.search(
                    r'<p class="mxm-lyrics__content[^"]*">\s*(.*?)\s*</p>',
                    html2,
                    re.DOTALL,
                )
                if lyrics_match:
                    lyrics = lyrics_match.group(1)
                    lyrics = re.sub(r"<[^>]+>", "", lyrics)
                    lyrics = lyrics.replace("...\n\n...\n", "\n")
                    if len(lyrics) > 20:
                        return lyrics
    return None

"""
web/app.py — Mission Control Dashboard for MBot.

A Flask web app that runs alongside the Discord bot, providing:
- Live dashboard with playback controls, queue manager, album art
- DJ line management (add/remove custom lines per category)
- DJ voice picker (dropdown of all edge-tts voices)
- Search-to-queue (paste a URL or search term, bot plays it)
- Interactive volume/speed sliders

The bot instance is passed in at startup so the dashboard can read
and modify bot state directly via the Music cog.
"""

import asyncio
import logging
import urllib.parse

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from utils.custom_lines import (
    LINE_CATEGORIES,
    CATEGORY_LABELS,
    CATEGORY_PLACEHOLDERS,
    add_line,
    load_custom_lines,
    remove_line,
)

app = Flask(__name__)
app.secret_key = "mbot-mission-control"

# ── Bot state (set by bot.py at startup) ──────────────────────────
bot = None


@app.context_processor
def inject_bot_name():
    """Make the bot's name available in all templates."""
    name = bot.user.name if bot and bot.user else "MBot"
    return {"bot_name": name}


def init_dashboard(discord_bot):
    """Called from bot.py to inject the running bot instance."""
    global bot
    bot = discord_bot


def _get_music_cog():
    """Return the Music cog from the running bot, or None."""
    if bot is None:
        return None
    return bot.get_cog("Music")


def _run_async(coro):
    """Submit an async coroutine to the bot's event loop and wait for it.

    This is the bridge between Flask (sync threads) and discord.py (async).
    Returns the coroutine's result, or None if the loop is unavailable.
    """
    if bot is None or bot.loop is None:
        return None
    future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
    try:
        return future.result(timeout=10)
    except Exception as e:
        logging.error(f"Dashboard: async call failed: {e}")
        return None


# ── Dashboard ────────────────────────────────────────────────────


@app.route("/")
def dashboard():
    music = _get_music_cog()
    guilds_data = []

    if bot and bot.guilds:
        for guild in bot.guilds:
            guild_id = guild.id
            voice = guild.voice_client
            current = None
            queue_items = []
            queue_size = 0

            if music:
                current = music.current_song.get(guild_id)
                q = music.song_queues.get(guild_id)
                if q:
                    queue_size = q.qsize()
                    # Peek at up to 50 items without consuming them
                    try:
                        queue_items = list(q._queue)[:50]
                    except Exception:
                        queue_items = []

            guilds_data.append(
                {
                    "id": guild_id,
                    "name": guild.name,
                    "member_count": guild.member_count,
                    "in_voice": voice is not None,
                    "voice_channel": voice.channel.name if voice else None,
                    "playing": voice.is_playing() if voice else False,
                    "paused": voice.is_paused() if voice else False,
                    "current_song": current.title if current else None,
                    "current_song_url": current.webpage_url if current else None,
                    "current_thumbnail": current.thumbnail if current else None,
                    "current_duration": current.duration if current else None,
                    "queue_size": queue_size,
                    "queue_items": [
                        {
                            "title": item.title,
                            "url": getattr(item, "webpage_url", None),
                            "thumbnail": getattr(item, "thumbnail", None),
                            "duration": getattr(item, "duration", None),
                        }
                        for item in queue_items
                    ],
                    "dj_enabled": music.dj_enabled.get(guild_id, False)
                    if music
                    else False,
                    "dj_voice": music.dj_voice.get(guild_id, "") if music else "",
                    "volume": int(music.current_volume.get(guild_id, 1.0) * 100)
                    if music
                    else 100,
                    "looping": music.looping.get(guild_id, False) if music else False,
                    "speed": music.playback_speed.get(guild_id, 1.0) if music else 1.0,
                }
            )

    return render_template(
        "dashboard.html",
        guilds=guilds_data,
        bot_user=str(bot.user) if bot else "Not connected",
        bot_avatar=bot.user.display_avatar.url if bot and bot.user else None,
        guild_count=len(bot.guilds) if bot else 0,
    )


# ── API Endpoints (called via JavaScript from dashboard) ─────────


@app.route("/api/<int:guild_id>/skip", methods=["POST"])
def api_skip(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client or not guild.voice_client.is_playing():
        return jsonify({"error": "Nothing playing"}), 400
    guild.voice_client.stop()
    return jsonify({"ok": True})


@app.route("/api/<int:guild_id>/pause", methods=["POST"])
def api_pause(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client:
        return jsonify({"error": "Not in voice"}), 400
    if guild.voice_client.is_paused():
        guild.voice_client.resume()
        return jsonify({"ok": True, "state": "playing"})
    elif guild.voice_client.is_playing():
        guild.voice_client.pause()
        return jsonify({"ok": True, "state": "paused"})
    return jsonify({"error": "Nothing playing"}), 400


@app.route("/api/<int:guild_id>/stop", methods=["POST"])
def api_stop(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503

    async def _stop():
        queue = await music.get_queue(guild_id)
        while not queue.empty():
            await queue.get()
        guild = bot.get_guild(guild_id)
        if guild and guild.voice_client:
            guild.voice_client.stop()

    _run_async(_stop())
    return jsonify({"ok": True})


@app.route("/api/<int:guild_id>/volume", methods=["POST"])
def api_volume(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503
    vol = request.json.get("volume")
    if vol is None:
        try:
            vol = int(request.form.get("volume", 100))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid volume"}), 400
    vol = max(0, min(200, int(vol)))
    music.current_volume[guild_id] = vol / 100.0
    guild = bot.get_guild(guild_id)
    if guild and guild.voice_client and guild.voice_client.source:
        guild.voice_client.source.volume = vol / 100.0
    return jsonify({"ok": True, "volume": vol})


@app.route("/api/<int:guild_id>/speed", methods=["POST"])
def api_speed(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503
    speed_steps = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
    try:
        speed = float(request.json.get("speed", 1.0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid speed"}), 400
    # Snap to nearest step
    speed = min(speed_steps, key=lambda s: abs(s - speed))
    music.playback_speed[guild_id] = speed
    return jsonify({"ok": True, "speed": speed})


@app.route("/api/<int:guild_id>/dj_toggle", methods=["POST"])
def api_dj_toggle(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503
    from utils.dj import EDGE_TTS_AVAILABLE

    if not EDGE_TTS_AVAILABLE:
        return jsonify({"error": "edge-tts not installed"}), 400
    music.dj_enabled[guild_id] = not music.dj_enabled.get(guild_id, False)
    return jsonify({"ok": True, "dj_enabled": music.dj_enabled[guild_id]})


@app.route("/api/<int:guild_id>/dj_voice", methods=["POST"])
def api_dj_voice(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503
    voice = request.json.get("voice", "")
    if not voice:
        return jsonify({"error": "Voice required"}), 400
    music.dj_voice[guild_id] = voice
    return jsonify({"ok": True, "voice": voice})


@app.route("/api/<int:guild_id>/voices")
def api_voices(guild_id):
    from utils.dj import list_voices, EDGE_TTS_AVAILABLE

    if not EDGE_TTS_AVAILABLE:
        return jsonify({"voices": [], "error": "edge-tts not installed"})
    lang = request.args.get("lang", "en")
    voices = _run_async(list_voices(lang))
    if voices is None:
        voices = []
    return jsonify(
        {
            "voices": [
                {
                    "name": v["ShortName"],
                    "gender": v.get("Gender", "?"),
                    "locale": v.get("Locale", "?"),
                }
                for v in voices
            ]
        }
    )


@app.route("/api/<int:guild_id>/queue/<int:index>", methods=["DELETE"])
def api_queue_remove(guild_id, index):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503

    async def _remove():
        q = await music.get_queue(guild_id)
        if index < 0 or index >= q.qsize():
            return False
        items = []
        while not q.empty():
            items.append(await q.get())
        removed = items.pop(index)
        for item in items:
            await q.put(item)
        return True

    result = _run_async(_remove())
    if result:
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid index"}), 400


@app.route("/api/<int:guild_id>/play", methods=["POST"])
def api_play(guild_id):
    music = _get_music_cog()
    if not music:
        return jsonify({"error": "Music cog not loaded"}), 503
    query = request.json.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400

    async def _play():
        guild = bot.get_guild(guild_id)
        if not guild:
            return "Guild not found"
        # Find a text channel to create a context
        channel = guild.text_channels[0] if guild.text_channels else None
        if not channel:
            return "No text channel"
        # Get a member context (use the bot itself)
        member = guild.me
        from discord.ext import commands

        ctx = (
            await bot.get_context(channel.get_partial_message(channel.last_message_id))
            if channel.last_message_id
            else None
        )
        if ctx is None:
            # Fallback: create a minimal context
            class FakeCtx:
                pass

            ctx = FakeCtx()
            ctx.guild = guild
            ctx.voice_client = guild.voice_client
            ctx.author = member
            ctx.channel = channel
            ctx.bot = bot
            ctx.command = None

        # Join voice if needed
        for member in guild.members:
            if not member.bot and member.voice and member.voice.channel:
                if not guild.voice_client:
                    await member.voice.channel.connect(self_deaf=True)
                elif not guild.voice_client.is_connected():
                    await guild.voice_client.disconnect(force=True)
                    await asyncio.sleep(0.5)
                    await member.voice.channel.connect(self_deaf=True)
                break

        from utils.suno import is_suno_url, get_suno_track
        from cogs.youtube import YTDLSource, YTDL_FORMAT_OPTIONS, PlaceholderTrack

        queue = await music.get_queue(guild_id)

        # Suno URL
        if is_suno_url(query):
            track = await get_suno_track(query)
            if not track:
                return "Could not resolve Suno URL"
            await queue.put(track)
        # YouTube playlist
        elif "playlist" in query or "list=" in query:
            tracks = await PlaceholderTrack.from_playlist_url(
                query, loop=bot.loop, playlist_items="1-25"
            )
            for t in tracks:
                await queue.put(t)
            return f"Added {len(tracks)} songs from playlist"
        else:
            # Single video or search
            result = await YTDLSource.from_url(query, loop=bot.loop)
            for r in result:
                await queue.put(r)

        if not guild.voice_client or not guild.voice_client.is_playing():
            await music.play_next(ctx)

        return "OK"

    result = _run_async(_play())
    if result and "not found" in str(result).lower():
        return jsonify({"error": result}), 404
    return jsonify({"ok": True, "result": str(result)})


# ── DJ Lines ─────────────────────────────────────────────────────


@app.route("/dj-lines")
def dj_lines():
    custom = load_custom_lines()
    categories = []
    for cat in LINE_CATEGORIES:
        built_in = _get_builtin_lines(cat)
        custom_for_cat = custom.get(cat, [])
        categories.append(
            {
                "key": cat,
                "label": CATEGORY_LABELS.get(cat, cat),
                "placeholders": CATEGORY_PLACEHOLDERS.get(cat, []),
                "builtin": built_in,
                "builtin_count": len(built_in),
                "custom": custom_for_cat,
                "custom_count": len(custom_for_cat),
                "total": len(built_in) + len(custom_for_cat),
            }
        )
    return render_template("dj_lines.html", categories=categories)


@app.route("/dj-lines/add", methods=["POST"])
def dj_lines_add():
    category = request.form.get("category", "").strip()
    line = request.form.get("line", "").strip()
    if not category or not line:
        flash("Category and line are required.", "error")
        return redirect(url_for("dj_lines"))
    if category not in LINE_CATEGORIES:
        flash(f"Invalid category: {category}", "error")
        return redirect(url_for("dj_lines"))
    success = add_line(category, line)
    if success:
        flash(
            f'Added to {CATEGORY_LABELS.get(category, category)}: "{line}"', "success"
        )
    else:
        flash("Failed to add line.", "error")
    return redirect(url_for("dj_lines"))


@app.route("/dj-lines/remove", methods=["POST"])
def dj_lines_remove():
    category = request.form.get("category", "").strip()
    index = request.form.get("index", "").strip()
    try:
        index = int(index)
    except ValueError:
        flash("Invalid index.", "error")
        return redirect(url_for("dj_lines"))
    success = remove_line(category, index)
    if success:
        flash(
            f"Removed line from {CATEGORY_LABELS.get(category, category)}.", "success"
        )
    else:
        flash("Failed to remove line. Check the index.", "error")
    return redirect(url_for("dj_lines"))


# ── Helpers ───────────────────────────────────────────────────────


def _get_builtin_lines(category: str) -> list:
    """Return the built-in lines for a category (hardcoded in dj.py)."""
    from utils.dj import (
        INTROS,
        HYPE_INTROS,
        HYPE_INTROS_LOUD,
        OUTROS,
        TRANSITIONS,
        TRANSITIONS_HYPE,
        TRANSITIONS_MELLOW,
        OUTROS_FINAL,
        STATION_IDS,
        CALLOUTS,
    )

    mapping = {
        "intros": INTROS,
        "hype_intros": HYPE_INTROS,
        "hype_intros_loud": HYPE_INTROS_LOUD,
        "outros": OUTROS,
        "transitions": TRANSITIONS,
        "transitions_hype": TRANSITIONS_HYPE,
        "transitions_mellow": TRANSITIONS_MELLOW,
        "outros_final": OUTROS_FINAL,
        "station_ids": STATION_IDS,
        "callouts": CALLOUTS,
    }
    return list(mapping.get(category, []))

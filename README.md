# 🎵 MBot 6.2.0 - The DJ Music Bot

MBot is a self-contained Discord music bot built with Python and `discord.py`. It plays audio from YouTube (URLs, searches, playlists) and Suno (direct song URLs) directly into Discord voice channels. 

## ✨ Features
- Play music directly from YouTube and Suno.com
- DJ Mode with TTS voice commentary between tracks (Detailed below)
- Support for playback of entire YouTube playlists and radio continuous play
- Built-in YouTube search
- Interactive Now Playing UI with button controls (Play/Pause/Skip/Stop/Queue)
- Fully configurable via interactive launcher scripts

---

## 🎙️ DJ Mode

MBot includes a unique **Radio DJ Mode**. When activated, the bot utilizes a Text-to-Speech (TTS) engine to speak between songs, just like a real radio DJ!

**What the DJ does:**
- Introduces the very first song in your session.
- Seamlessly transitions between songs by back-announcing what just played and introducing what's up next.
- Drops station IDs ("You're tuned to MBot Radio") randomly.
- Adapts personality based on the time of day (morning, afternoon, late-night crew).
- Plays a smooth outro when the queue runs out.

**Using DJ Mode:**
- Use `?dj` to toggle DJ Mode on or off for your server.
- The default voice is a female American voice (`en-US-AriaNeural`). 
- Change the DJ's voice anytime using `?djvoice <voice_name>`.
- Use `?djvoices` to browse the extensive list of available AI voices.

---

## 📜 Full Command Reference
*(The default prefix is `?`)*

### 🎧 Music Commands
| Command | Usage | Description |
|---|---|---|
| `?join` | `?join` | Bot joins or moves to your voice channel |
| `?leave` | `?leave` | Disconnects the bot from voice and cleans up |
| `?search` | `?search <query>` | Searches YouTube and shows the top 10 results |
| `?play` | `?play <URL/query>` | Plays audio from YouTube (link or query), Search result number, or Suno URL |
| `?playlist` | `?playlist <URL>` | Queues up to 25 songs from a YouTube playlist |
| `?radio` | `?radio <URL>` | Queues up to 100 songs for long sessions |
| `?queue` | `?queue` | Displays all songs currently in the queue |
| `?skip` | `?skip` | Skips to the next track in the queue |
| `?stop` | `?stop` | Stops playback immediately and clears the entire queue |
| `?pause` | `?pause` | Pauses the current track |
| `?resume` | `?resume` | Resumes paused playback |
| `?clear` | `?clear` | Clears all queued songs (but doesn't stop the current song) |
| `?remove` | `?remove <number>` | Removes a specific song number from your queue |
| `?nowplaying` | `?nowplaying` | Shows the currently playing song with interactive controls |
| `?volume` | `?volume <0-200>` | Adjusts playback volume (100 = normal volume) |
| `?loop` | `?loop` | Toggles looping for the current song |
| `?speedhigher` | `?speedhigher` | Increases the playback speed by one step |
| `?speedlower` | `?speedlower` | Decreases the playback speed by one step |
| `?shuffle` | `?shuffle` | Randomizes the queue order |

### 🎙️ DJ Commands
| Command | Usage | Description |
|---|---|---|
| `?dj` | `?dj` | Toggles the DJ text-to-speech commentary on/off |
| `?djvoice` | `?djvoice [name]` | Shows the current DJ voice, or sets it to `<name>` |
| `?djvoices` | `?djvoices [prefix]`| Lists available voices (e.g. `ja` for Japanese, or no prefix for English) |

### ⚙️ Admin Commands (Bot Owner Only)
| Command | Usage | Description |
|---|---|---|
| `?fetch_and_set_cookies` | `?fetch_and_set_cookies <https URL>` | Fetches cookies from a URL. Great for age-restricted/member YouTube videos. |
| `?shutdown` | `?shutdown` | Safely shuts down the bot |
| `?restart` | `?restart` | Closes the connection (Will automatically reboot if run with launcher scripts) |

---

## 🛠️ Prerequisites
- **Python 3.9+**
- System packages: `ffmpeg`, `libopus-dev`, `screen`, `git`
- Target OS: Recommended on Debian/Ubuntu Linux

## 🚀 Installation & Setup

We recommend using the interactive `start.sh` launcher script as it handles all dependencies, sets up a Python virtual environment, and helps you create your configuration automatically.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jayis1/the-Dj-music-bot.git
   cd the-Dj-music-bot
   ```

2. **Run the interactive setup:**
   ```bash
   bash start.sh
   ```

### ⚙️ Required Configuration Variables
The interactive setup will ask you for these, storing them securely in a `.env` file:
| Variable | Description | Required |
| --- | --- | --- |
| `DISCORD_TOKEN` | Connecting token from the Discord Developer Portal. | **Yes** |
| `YOUTUBE_API_KEY` | Needed if you want to use the `?search` command. | No |
| `LOG_CHANNEL_ID` | A Discord Channel ID where the bot will send logs. | No |
| `BOT_OWNER_ID` | The developer's Discord User ID (to run admin commands). | No |

## 📚 Further Documentation
For detailed insights regarding architecture, cog layout, creating your own modules, or managing yt-dlp cached metadata, please refer directly to the comprehensive [GUIDE.md](GUIDE.md).

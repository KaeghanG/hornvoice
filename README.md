# HornVoice

**Local, offline voice control for Windows.** Hold a key and say what you want, dictate into any text box, or just say *"hey horn…"*. Speech recognition is [Whisper](https://github.com/SYSTRAN/faster-whisper) running on your own PC: **no audio ever leaves your computer, no account, no cloud.**

Built as the voice companion to [Gjallarhorn](https://github.com/KaeghanG/gjallarhorn) (a fire-themed game launcher), but it works on its own for the whole PC.

> "Hey horn, play Elden Ring." · "Open Discord." · "Volume thirty." · "Lock the PC." · *(hold Right Alt)* "Dear team, the build is green." → typed for you.

## Install

**Option 1: one line (recommended, tiny download)**

```powershell
irm https://raw.githubusercontent.com/KaeghanG/hornvoice/main/install.ps1 | iex
```

Add start-with-Windows:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/KaeghanG/hornvoice/main/install.ps1))) -Startup
```

It installs [uv](https://docs.astral.sh/uv/) if missing, puts HornVoice in its own isolated Python environment, and adds a Start menu shortcut. No administrator rights needed.

**Option 2: standalone installer**
Download `HornVoice-Setup-x.y.z.exe` from the [latest release](https://github.com/KaeghanG/hornvoice/releases/latest). No Python needed (it is a larger download). Windows SmartScreen may warn because the installer is not code-signed yet: **More info → Run anyway.**

**Option 3: with pip / uv**

```powershell
uv tool install --python 3.12 git+https://github.com/KaeghanG/hornvoice
hornvoice-gui
```

The first start downloads the speech model (about 500 MB, once). After that everything is offline.

## Use it

| Do this | To |
|---|---|
| Hold **Right Ctrl**, speak, release | Run a voice command |
| Hold **Right Alt**, speak, release | Dictate: the text is typed wherever your cursor is |
| Say **"hey horn …"** | Run a command hands-free (say just "hey horn", then your command a moment later, also works) |
| Tray icon | Turn the wake word on or off, open the settings file or log, quit |

Beeps tell you what happened: high = listening, mid = done, low = didn't understand.

### Commands

| Say | Does |
|---|---|
| "open Discord", "launch Steam", "run notepad" | Opens any Start-menu app (fuzzy matching) |
| "play Elden Ring" | Launches that game through Gjallarhorn if you have it (otherwise says it can't) |
| "volume up / down", "volume 30", "mute" | Volume |
| "pause", "play", "next song", "previous song" | Media keys |
| "lock the PC" | Locks Windows |
| "go to sleep", "shut down", "restart" | Asks you to say **"confirm"** within 12 seconds (or "cancel") |
| "screenshot", "show desktop", "minimize", "maximize", "close window", "switch window", "task manager", "open settings", "file explorer" | Window and system actions |
| "search for …", "open YouTube / Reddit / GitHub / Twitch …" | Browser |
| "type hello world" | Types it |
| "couch mode", "go home", "open the menu", "open friends / downloads / reports / library …" | Controls Gjallarhorn |
| "what time is it", "help" | Info |
| "stop listening" / "start listening" | Turn the wake word off / on |
| "quit voice control" | Exits |

If a phrase doesn't match any of the above, and you have [Ollama](https://ollama.com) running locally, HornVoice asks a small model to rephrase it into one of these commands before giving up - so "can you turn this down a bit" still works as "volume down". See **The brain** below.

### The brain (optional, local, off by default without Ollama)

HornVoice ships with a fixed set of command patterns (the table above). When none of them match, it can hand the phrase to a small model running in [Ollama](https://ollama.com) on your own PC and ask for a one-line rewrite into a command it already knows - nothing more. That rewritten line is run back through the exact same rules, so **the model can never do anything the rules above don't already allow**, and a risky action (sleep, shut down, restart) still needs you to say "confirm" out loud.

- Needs [Ollama](https://ollama.com) installed and running, with a model pulled (default `qwen3.5:9b`: `ollama pull qwen3.5:9b`). HornVoice does not install or manage Ollama for you.
- If Ollama isn't running, this fails in well under a second and HornVoice behaves exactly as it does without it.
- Set `"brain": false` in the config to turn it off entirely, or change `brain_model` to any Ollama model you have pulled.

## Settings

`%APPDATA%\HornVoice\config.json` (restart HornVoice after editing):

| Key | Default | Meaning |
|---|---|---|
| `model` | `small.en` | `tiny.en` (fastest), `base.en`, `small.en`, `medium.en` (most accurate) |
| `device` / `compute_type` | `cpu` / `int8` | CPU keeps GPU memory free for games. `cuda` + `float16` uses an NVIDIA GPU if the CUDA libraries are installed |
| `cpu_threads` | `4` | How many CPU threads Whisper may use |
| `command_key` / `dictation_key` | `right ctrl` / `right alt` | Hold-to-talk keys |
| `wake_word` / `wake_phrases` | `true` / "hey horn", … | Always-on wake word and the phrases that trigger it |
| `brain` | `true` | Ask a local Ollama model to rephrase an unrecognized command (see **The brain** above). No effect if Ollama isn't running |
| `brain_model` / `brain_url` | `qwen3.5:9b` / `http://127.0.0.1:11434` | Which Ollama model and server to use |
| `mic` | `null` | Microphone name or index (default = Windows default) |
| `sounds` | `true` | Beeps |

## Privacy

- Whisper runs locally. Audio is processed in memory and discarded; nothing is recorded to disk or sent anywhere. The only network use is downloading the speech model once from Hugging Face.
- The **wake word listens continuously**, but only speech that starts with "hey horn" (or similar) is acted on; everything else is ignored. Turn it off from the tray icon if you prefer hold-to-talk only.
- Dangerous actions (sleep, shut down, restart) always ask for a spoken confirmation.
- Log: `%APPDATA%\HornVoice\hornvoice.log` (recognized text and actions, no audio).

## Troubleshooting

| Problem | Try |
|---|---|
| "Hey horn" does nothing | Open the log. Lines like `mic ok: noise floor … loudest block …` show the room noise and your loudest speech. If the loudest block barely rises, raise the microphone level in Windows Sound settings. Hold Right Ctrl instead to test the rest of the pipeline. |
| No popup notifications | Windows Focus Assist / Do Not Disturb can hide them. The beeps and log still work. |
| Mis-hearing | Use a bigger model (`medium.en`), speak closer to the mic, or pick the right microphone with `mic`. |
| Slow on first command | The first start loads and warms up the model. Later commands take about a second. |
| Keys do nothing in an admin window | Windows does not let a normal app send keys to an elevated window. Run HornVoice as administrator if you need that. |
| Antivirus warning | The `keyboard` library installs a global key hook, which some antivirus tools dislike. The source is here to read. |

## Build from source

```powershell
git clone https://github.com/KaeghanG/hornvoice
cd hornvoice
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.venv\Scripts\python.exe -m pytest        # command parser tests (dry run, nothing is executed)
.venv\Scripts\python.exe -m hornvoice --say "open discord"   # see what a phrase would do
```

Build the standalone installer locally: `pip install ".[build]"`, `pyinstaller packaging\hornvoice.spec`, then compile `packaging\installer.iss` with [Inno Setup](https://jrsoftware.org/isinfo.php). GitHub Actions does this on every `v*` tag.

## Limits

Windows only (global key hooks, Win32 audio, Start menu index). English models by default. Whisper can mishear unusual game names; the "play …" command asks Gjallarhorn to fuzzy-match your library, which helps.

## License

MIT. Whisper models are released by OpenAI under MIT; [faster-whisper](https://github.com/SYSTRAN/faster-whisper) is MIT.

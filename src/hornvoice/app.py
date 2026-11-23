"""HornVoice: local voice control for Windows.

Hold a key and speak (commands or dictation), or just say "hey horn ...". Speech recognition is Whisper running fully on this PC.
Run:  hornvoice-gui   (tray icon, no console)   or   python -m hornvoice
Test: python -m hornvoice --say "open discord"      (parse and print what it would do, nothing is executed)
      python -m hornvoice --wav some.wav            (transcribe a file, then parse)
"""
import collections, ctypes, datetime, json, os, queue, re, subprocess, sys, threading, time, urllib.parse
import numpy as np

APPDATA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "HornVoice")
os.makedirs(APPDATA, exist_ok=True)
CONFIG = os.path.join(APPDATA, "config.json")
LOG = os.path.join(APPDATA, "hornvoice.log")
DEFAULTS = {
    "model": "small.en",          # tiny.en / base.en are faster, medium.en is more accurate
    "device": "cpu",              # "cuda" uses the GPU (needs the CUDA libraries); CPU keeps VRAM free for games
    "compute_type": "int8",
    "cpu_threads": 4,
    "command_key": "right ctrl",  # hold and speak a command
    "dictation_key": "right alt", # hold and speak text that gets typed wherever the cursor is
    "wake_word": True,            # say "hey horn ..." without touching the keyboard
    "wake_phrases": ["hey horn", "hey gjallarhorn", "okay horn", "ok horn", "gjallarhorn", "horn"],
    "sounds": True,
    "mic": None,                  # device name or index; None = Windows default
}
DRY = False


def cfg_load():
    c = dict(DEFAULTS)
    try:
        c.update(json.load(open(CONFIG, encoding="utf-8")))
    except Exception:
        json.dump(DEFAULTS, open(CONFIG, "w", encoding="utf-8"), indent=2)
    return c


CFG = cfg_load()


def log(msg):
    line = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    if DRY or sys.stdout:
        try:
            print(line)
        except Exception:
            pass


# ---------------------------------------------------------------- Windows actions
user32 = ctypes.windll.user32
VK = {"vol_up": 0xAF, "vol_down": 0xAE, "mute": 0xAD, "play": 0xB3, "next": 0xB0, "prev": 0xB1}


def press_vk(vk, times=1):
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.01)


class KI(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INP(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KI), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def type_text(text):
    """Type text into the focused window as Unicode key events (no clipboard involved)."""
    for ch in text:
        for flags in (0x0004, 0x0004 | 0x0002):  # KEYEVENTF_UNICODE down, then up
            i = INP(type=1)
            i.ki = KI(0, ord(ch), flags, 0, None)
            user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
        time.sleep(0.002)


def hotkey(*keys):
    import keyboard
    keyboard.send("+".join(keys))


def beep(kind):
    if not CFG.get("sounds"):
        return
    try:
        import winsound
        {"start": lambda: winsound.Beep(900, 50), "ok": lambda: winsound.Beep(1200, 60), "bad": lambda: winsound.Beep(300, 160)}[kind]()
    except Exception:
        pass


TRAY = {"icon": None}


def say(msg, title="HornVoice"):
    log(f"[{title}] {msg}")
    ic = TRAY["icon"]
    if ic:
        try:
            ic.notify(msg, title)
        except Exception:
            pass


def run(args, **kw):
    if DRY:
        log(f"DRY run: {args}")
        return
    return subprocess.Popen(args, creationflags=0x08000000, **kw)  # CREATE_NO_WINDOW


# ---------------------------------------------------------------- apps and links
APPS = {"list": [], "t": 0}


def refresh_apps():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json -Compress"], capture_output=True, text=True, timeout=30, creationflags=0x08000000).stdout
        data = json.loads(out)
        APPS["list"] = [(d["Name"], d["AppID"]) for d in (data if isinstance(data, list) else [data]) if d.get("Name")]
        APPS["t"] = time.time()
        log(f"{len(APPS['list'])} apps indexed")
    except Exception as e:
        log(f"app index failed: {e}")


def find_app(name):
    from rapidfuzz import fuzz, process
    if not APPS["list"] or time.time() - APPS["t"] > 900:
        refresh_apps()
    names = [a[0] for a in APPS["list"]]
    if not names:
        return None
    hit = process.extractOne(name, names, scorer=fuzz.WRatio, score_cutoff=82)
    return APPS["list"][hit[2]] if hit else None


def open_link(url):
    if DRY:
        log(f"DRY open: {url}")
        return True
    try:
        os.startfile(url)
        return True
    except Exception as e:
        log(f"open failed {url}: {e}")
        return False


def gj(action, name=""):
    url = f"gjallarhorn://{action}" + (f"?name={urllib.parse.quote(name)}" if name else "")
    ok = open_link(url)
    if not ok:
        say("Gjallarhorn is not installed (or not registered yet): update it, then try again.")
    return ok


SITES = {"youtube": "https://www.youtube.com", "google": "https://www.google.com", "github": "https://github.com", "reddit": "https://www.reddit.com",
         "twitch": "https://www.twitch.tv", "gmail": "https://mail.google.com", "twitter": "https://x.com", "netflix": "https://www.netflix.com"}
GJ_PAGES = {"friends": "friends", "downloads": "downloads", "play reports": "reports", "reports": "reports", "quick access": "quick", "controllers": "pads",
            "power": "power", "library": "library", "store": "store", "search": "search", "retro": "retro", "emulators": "emulators", "deals": "deals", "system": "system"}

# ---------------------------------------------------------------- commands
PENDING = {"fn": None, "label": "", "until": 0}
STATE = {"wake": CFG["wake_word"], "quit": False}


def need_confirm(label, fn):
    PENDING.update(fn=fn, label=label, until=time.time() + 12)
    say(f'{label}? Say "confirm" within 12 seconds, or "cancel".')


def set_volume(n):
    n = max(0, min(100, n))
    if DRY:
        log(f"DRY set volume {n}")
        return
    press_vk(VK["vol_down"], 50)
    press_vk(VK["vol_up"], round(n / 2))


def volume_step(up, steps=5):
    if DRY:
        log(f"DRY volume {'up' if up else 'down'} x{steps}")
        return
    press_vk(VK["vol_up" if up else "vol_down"], steps)


def clean(text):
    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9%' ]+", " ", t)
    t = re.sub(r"\b(please|hey|okay|ok|could you|can you|would you|for me|now)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def act(label, fn):
    log(f"-> {label}")
    if not DRY:
        try:
            fn()
        except Exception as e:
            say(f"{label} failed: {e}")
            beep("bad")
            return True
    beep("ok")
    return True


def handle_command(raw):
    t = clean(raw)
    if not t:
        return False
    log(f'command: "{t}"')

    # pending confirmation
    if PENDING["fn"] and time.time() < PENDING["until"]:
        if re.fullmatch(r"(confirm|yes|yes do it|do it|go ahead)", t):
            fn, PENDING["fn"] = PENDING["fn"], None
            return act("confirmed: " + PENDING["label"], fn)
        if re.fullmatch(r"(cancel|no|never mind|stop)", t):
            PENDING["fn"] = None
            say("Cancelled.")
            return True

    m = re.fullmatch(r"(?:set )?(?:the )?volume (?:to |at )?(\d{1,3})(?: percent)?", t)
    if m:
        return act(f"volume {m.group(1)}", lambda: set_volume(int(m.group(1))))
    if re.search(r"\b(volume up|turn it up|louder|raise the volume)\b", t):
        return act("volume up", lambda: volume_step(True))
    if re.search(r"\b(volume down|turn it down|quieter|lower the volume)\b", t):
        return act("volume down", lambda: volume_step(False))
    if re.search(r"\b(mute|unmute)\b", t):
        return act("mute", lambda: press_vk(VK["mute"]))
    if re.fullmatch(r"(play|pause|resume|play music|pause music|stop music|play pause|resume music)", t):
        return act("play/pause", lambda: press_vk(VK["play"]))
    if re.search(r"\b(next (track|song)|skip( this)?( song| track)?)\b", t):
        return act("next track", lambda: press_vk(VK["next"]))
    if re.search(r"\b(previous (track|song)|last song|go back a song)\b", t):
        return act("previous track", lambda: press_vk(VK["prev"]))
    if re.search(r"\block (the |my )?(pc|computer|screen)\b|^lock it$", t):
        return act("lock", lambda: user32.LockWorkStation())
    if re.search(r"\b(go to sleep|sleep (the )?(pc|computer)|put (the )?(pc|computer) to sleep)\b|^sleep$", t):
        need_confirm("Sleep the PC", lambda: run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]))
        return True
    if re.search(r"\b(shut ?down|turn off) (the )?(pc|computer)\b|^shut ?down$", t):
        need_confirm("Shut down", lambda: run(["shutdown", "/s", "/t", "5"]))
        return True
    if re.search(r"\b(restart|reboot)( the)?( pc| computer)?\b", t):
        need_confirm("Restart", lambda: run(["shutdown", "/r", "/t", "5"]))
        return True
    if re.search(r"\bscreenshot\b", t):
        return act("screenshot", lambda: hotkey("windows", "print screen"))
    if re.search(r"\b(show desktop|minimi[sz]e (everything|all))\b", t):
        return act("show desktop", lambda: hotkey("windows", "d"))
    if re.search(r"\bminimi[sz]e\b", t):
        return act("minimize", lambda: hotkey("windows", "down"))
    if re.search(r"\bmaximi[sz]e\b|\bfull ?screen\b", t):
        return act("maximize", lambda: hotkey("windows", "up"))
    if re.search(r"\bclose (the |this |that )?(window|app)\b", t):
        return act("close window", lambda: hotkey("alt", "f4"))
    if re.search(r"\b(switch|next) window\b|\balt tab\b", t):
        return act("switch window", lambda: hotkey("alt", "tab"))
    if re.search(r"\btask manager\b", t):
        return act("task manager", lambda: hotkey("ctrl", "shift", "esc"))
    if re.search(r"\b(open )?(windows )?settings\b", t) and not re.search(r"gjallarhorn|couch", t):
        return act("settings", lambda: open_link("ms-settings:"))
    if re.search(r"\b(file explorer|explorer)\b", t):
        return act("file explorer", lambda: run(["explorer.exe"]))
    if re.search(r"\bwhat('s| is) the time\b|\bwhat time is it\b", t):
        say(datetime.datetime.now().strftime("It is %I:%M %p"))
        return True
    m = re.search(r"\b(?:search|google)(?: for)? (.+)", t)
    if m:
        return act("search " + m.group(1), lambda: open_link("https://www.google.com/search?q=" + urllib.parse.quote(m.group(1))))
    m = re.search(r"\b(?:type|write|dictate) (.+)", t)
    if m:
        txt = re.sub(r"^(?:type|write|dictate) ", "", raw.strip(), flags=re.I)
        return act("type", lambda: type_text(txt))
    if re.search(r"\b(stop|pause) listening\b|\bmute (yourself|the mic)\b", t):
        STATE["wake"] = False
        say("Wake word off. Hold the command key to talk.")
        return True
    if re.search(r"\bstart listening\b|\bwake word on\b", t):
        STATE["wake"] = True
        say("Wake word on.")
        return True
    if re.search(r"\b(quit|exit) (voice|horn voice|hornvoice)\b", t):
        STATE["quit"] = True
        return True
    if re.fullmatch(r"help|what can you do", t):
        say("Try: open Discord, play Elden Ring, volume 30, mute, next song, lock the PC, go home, open friends, type hello.")
        return True

    # Gjallarhorn
    if re.search(r"\b(couch mode|big picture)\b|^open gjallarhorn$|^gjallarhorn$", t):
        return act("couch mode", lambda: gj("couch"))
    if re.search(r"\b(go home|gjallarhorn home|couch home|take me home)\b", t):
        return act("gjallarhorn home", lambda: gj("home"))
    if re.search(r"\b(game|pause|in game|gjallarhorn) menu\b|^(open )?(the )?menu$", t):
        return act("in-game menu", lambda: gj("menu"))
    m = re.search(r"\b(?:open|show|go to|take me to)(?: the)? (friends|downloads|play reports|reports|quick access|controllers|power|library|store|search|retro|emulators|deals|system)\b", t)
    if m:
        page = GJ_PAGES[m.group(1)]
        return act("gjallarhorn " + page, lambda: gj("page", page))

    # open / launch / play
    m = re.fullmatch(r"(open|launch|start|run|play|load)(?: up)? (?:the )?(.+)", t)
    if m:
        verb, what = m.group(1), m.group(2)
        site = SITES.get(what.replace(" dot com", "").strip())
        if site and verb != "play":
            return act("open " + what, lambda: open_link(site))
        if verb == "play":
            return act("play " + what, lambda: gj("launch", what))
        app = find_app(what)
        if app:
            return act(f"open {app[0]}", lambda: run(["explorer.exe", f"shell:AppsFolder\\{app[1]}"]))
        return act("launch game " + what, lambda: gj("launch", what))

    say(f'Sorry, I did not understand "{raw.strip()}".')
    beep("bad")
    return False


# ---------------------------------------------------------------- speech
MODEL = {"m": None}
PROMPT = "Hey horn, play Elden Ring. Open Discord. Volume up. Gjallarhorn couch mode. Open friends. Lock the PC."


def load_model():
    from faster_whisper import WhisperModel
    t0 = time.time()
    MODEL["m"] = WhisperModel(CFG["model"], device=CFG["device"], compute_type=CFG["compute_type"], cpu_threads=int(CFG["cpu_threads"]))
    log(f"model {CFG['model']} ({CFG['device']}/{CFG['compute_type']}) ready in {time.time() - t0:.1f}s")


def transcribe(audio):
    segs, _ = MODEL["m"].transcribe(audio, language="en", beam_size=1, vad_filter=True, condition_on_previous_text=False,
                                    no_speech_threshold=0.6, initial_prompt=PROMPT)
    return " ".join(s.text.strip() for s in segs).strip()


def strip_wake(text):
    t = clean(text)
    for p in sorted(CFG["wake_phrases"], key=len, reverse=True):
        pc = clean(p)
        if t == pc:
            return ""
        if t.startswith(pc + " "):
            return t[len(pc) + 1:]
    # Whisper often mishears the made-up word: accept near matches ("horne", "orn", "horn's", "hoarn") as the first word.
    from rapidfuzz import fuzz
    words = t.split(" ")
    if words and words[0] and fuzz.ratio(words[0], "horn") >= 70 or (words and fuzz.ratio(words[0], "gjallarhorn") >= 70):
        return " ".join(words[1:])
    return None


def process(audio, mode):
    text = transcribe(audio)
    if not text or len(text) < 2:
        return
    log(f"heard [{mode}]: {text}")
    if mode == "dictation":
        low = text.strip().lower().strip(" .")
        if low in ("you", "thank you", "thanks for watching"):  # typical Whisper hallucinations on near-silence
            return
        beep("ok")
        if not DRY:
            type_text(text + " ")
        return
    if mode == "wake":
        rest = strip_wake(text)
        if rest is None:
            if time.time() < STATE.get("await", 0):  # "hey horn" was said alone a moment ago: this is the command
                STATE["await"] = 0
                rest = clean(text)
            else:
                return
        elif not rest:
            STATE["await"] = time.time() + 7
            beep("start")
            say("Listening... say a command", "HornVoice")
            return
        text = rest
        say(f'Heard: "{text}"')
    handle_command(text)


# ---------------------------------------------------------------- audio loop
SR = 16000
BLOCK = 512


def audio_loop(jobs):
    while not STATE["quit"]:
        try:
            _audio_loop(jobs)
        except Exception as e:  # never let the microphone thread die silently
            log(f"audio loop crashed: {e!r}; restarting in 3 s")
            time.sleep(3)


def _audio_loop(jobs):
    import sounddevice as sd, keyboard
    q = queue.Queue()
    held = {"command": False, "dictation": False}

    def mark(mode, down):
        if down and not held[mode]:
            held[mode] = True
        elif not down:
            held[mode] = False

    keyboard.on_press_key(CFG["command_key"], lambda e: mark("command", True))
    keyboard.on_release_key(CFG["command_key"], lambda e: mark("command", False))
    keyboard.on_press_key(CFG["dictation_key"], lambda e: mark("dictation", True))
    keyboard.on_release_key(CFG["dictation_key"], lambda e: mark("dictation", False))

    def cb(indata, frames, t, status):
        q.put(indata[:, 0].copy())

    pre = collections.deque(maxlen=int(0.5 * SR / BLOCK))
    buf, cap_mode = [], None
    seg, in_speech, speech_n, silence_n, noise = [], False, 0, 0, 0.004
    lv = [0.0, time.time()]
    dev = CFG["mic"]
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", blocksize=BLOCK, callback=cb, device=dev):
        log("listening")
        while not STATE["quit"]:
            try:
                blk = q.get(timeout=0.5)
            except queue.Empty:
                continue
            mode = "dictation" if held["dictation"] else "command" if held["command"] else None
            if mode:
                if cap_mode is None:
                    cap_mode = mode
                    buf = list(pre)
                    beep("start")
                buf.append(blk)
                continue
            if cap_mode is not None:  # key released: transcribe what was held
                audio = np.concatenate(buf) if buf else None
                m, cap_mode, buf = cap_mode, None, []
                if audio is not None and len(audio) > SR * 0.3:
                    jobs.put((audio, m))
                continue
            pre.append(blk)
            if not STATE["wake"]:
                in_speech, seg = False, []
                continue
            rms = float(np.sqrt(np.mean(blk * blk)))
            thr = max(0.012, noise * 2.6)  # speech must stand out from the room noise
            lv[0] = max(lv[0], rms)
            if time.time() - lv[1] > 30:
                log(f"mic ok: noise floor {noise:.4f}, trigger {thr:.4f}, loudest block {lv[0]:.3f}")
                lv[0], lv[1] = 0.0, time.time()
            if rms > thr:
                speech_n += 1
                silence_n = 0
                if not in_speech and speech_n >= 3:
                    in_speech, seg = True, list(pre)
                if in_speech:
                    seg.append(blk)
            else:
                if not in_speech:
                    noise = 0.97 * noise + 0.03 * rms
                    speech_n = 0
                else:
                    silence_n += 1
                    seg.append(blk)
                    if silence_n > int(0.8 * SR / BLOCK) or len(seg) > int(9 * SR / BLOCK):
                        audio = np.concatenate(seg)
                        in_speech, seg, speech_n, silence_n = False, [], 0, 0
                        if len(audio) > SR * 0.6 and jobs.qsize() < 2:
                            jobs.put((audio, "wake"))


def worker(jobs):
    while not STATE["quit"]:
        try:
            audio, mode = jobs.get(timeout=0.5)
        except queue.Empty:
            continue
        while MODEL["m"] is None and not STATE["quit"]:  # the model is still loading on first start
            time.sleep(0.3)
        try:
            process(audio, mode)
        except Exception as e:
            log(f"error: {e!r}")


def make_icon():
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, 60, 60), fill=(20, 24, 40, 255), outline=(240, 200, 105, 255), width=4)
    d.polygon([(16, 44), (46, 14), (52, 22), (24, 50)], fill=(240, 200, 105, 255))
    return im


def tray():
    import pystray
    def toggle_wake(icon, item):
        STATE["wake"] = not STATE["wake"]
    def quit_(icon, item):
        STATE["quit"] = True
        icon.stop()
    menu = pystray.Menu(
        pystray.MenuItem("Wake word (say 'hey horn')", toggle_wake, checked=lambda i: STATE["wake"]),
        pystray.MenuItem("Open settings file", lambda i, it: os.startfile(CONFIG)),
        pystray.MenuItem("Open log", lambda i, it: os.startfile(LOG)),
        pystray.MenuItem("Quit", quit_),
    )
    icon = pystray.Icon("HornVoice", make_icon(), "HornVoice: hold Right Ctrl to talk", menu)
    TRAY["icon"] = icon
    icon.run()


def main():
    global DRY
    a = sys.argv[1:]
    if "--say" in a:
        DRY = True
        i = a.index("--say")
        refresh_apps()
        handle_command(" ".join(a[i + 1:]))
        return
    if "--wav" in a:
        DRY = True
        import wave
        w = wave.open(a[a.index("--wav") + 1])
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        refresh_apps()
        load_model()
        text = transcribe(pcm)
        log(f"transcript: {text}")
        rest = strip_wake(text)
        handle_command(rest if rest else text)
        return
    if "--version" in a:
        from . import __version__
        print(__version__)
        return
    # One copy at a time (Start menu + start-with-Windows would otherwise run two microphones).
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\HornVoiceSingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return
    log("starting")
    jobs = queue.Queue()
    threading.Thread(target=lambda: (say("Starting. The first run downloads the speech model (about 500 MB); this can take a few minutes.") if not os.path.isdir(os.path.expanduser("~/.cache/huggingface/hub")) else None, load_model(), say("Ready. Hold Right Ctrl to talk, or say 'hey horn'."), refresh_apps()), daemon=True).start()
    threading.Thread(target=worker, args=(jobs,), daemon=True).start()
    threading.Thread(target=audio_loop, args=(jobs,), daemon=True).start()
    tray()


if __name__ == "__main__":
    main()

# Changelog

## Unreleased

- **The "brain":** when a phrase doesn't match any built-in command, HornVoice can now ask a small local model (via [Ollama](https://ollama.com), default `qwen3.5:9b`) to rewrite it into a known command ("can you crank the volume please" &rarr; "volume up"). It only ever proposes plain text from the same fixed list of commands you already have - that text is run back through the normal rules, so it can't do anything the rules don't already allow, and a risky action (sleep, shut down, restart) still needs your spoken "confirm". It fails silently in well under a second if Ollama isn't running. Toggle it with `brain` in the config file.

## 0.1.0

- Hold-to-talk commands (Right Ctrl), dictation typed into any window (Right Alt) and an always-on "hey horn" wake word
- Fully local speech recognition with faster-whisper (default `small.en`, CPU int8)
- Commands: apps, games through Gjallarhorn, volume, media keys, lock, sleep / shut down / restart with spoken confirmation, window actions, search, typing, Gjallarhorn pages
- Tray icon, beeps, log, single-instance guard
- One-line installer, standalone Windows installer, `pip` / `uv` package

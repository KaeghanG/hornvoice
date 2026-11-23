"""Command parser tests. They run in dry-run mode: nothing is launched, typed or pressed."""
import time

import pytest

from hornvoice import app


@pytest.fixture(autouse=True)
def dry(monkeypatch):
    monkeypatch.setattr(app, "DRY", True)
    monkeypatch.setattr(app, "beep", lambda kind: None)
    monkeypatch.setattr(app, "refresh_apps", lambda: None)
    app.APPS["list"] = [("Discord", "Discord.App"), ("Notepad", "Notepad.App")]
    app.APPS["t"] = time.time()
    app.PENDING.update(fn=None, label="", until=0)
    app.CFG["brain"] = False  # keep the default test run fully offline; brain tests below turn it on and mock the network call


@pytest.mark.parametrize("phrase", [
    "volume up", "turn it down", "volume 30", "set the volume to 55 percent", "mute", "next song", "previous track", "pause",
    "lock the pc", "screenshot", "show desktop", "minimize", "close window", "task manager", "open settings", "file explorer",
    "search for cheap keyboards", "open youtube", "open discord", "play elden ring", "type hello world",
    "couch mode", "go home", "open the menu", "open friends", "open downloads", "what time is it", "help",
])
def test_known_commands_are_understood(phrase):
    assert app.handle_command(phrase) is True


def test_gibberish_is_rejected():
    assert app.handle_command("purple monkey dishwasher") is False


def test_unknown_app_falls_back_to_a_game(monkeypatch):
    seen = []
    monkeypatch.setattr(app, "DRY", False)  # let the action run, but with Gjallarhorn stubbed out
    monkeypatch.setattr(app, "gj", lambda action, name="": seen.append((action, name)) or True)
    assert app.handle_command("launch hollow knight") is True
    assert seen == [("launch", "hollow knight")]


def test_dangerous_actions_need_confirmation():
    ran = []
    assert app.handle_command("shut down") is True
    assert app.PENDING["fn"] is not None  # waiting for "confirm", nothing has run
    app.PENDING["fn"] = lambda: ran.append(1)
    app.PENDING["until"] = time.time() + 5
    assert app.handle_command("cancel") is True
    assert app.PENDING["fn"] is None and not ran


def test_wake_phrase_is_stripped():
    assert app.strip_wake("Hey horn, play Elden Ring") == "play elden ring"
    assert app.strip_wake("Hey horn") == ""
    assert app.strip_wake("Hey horne open discord") == "open discord"  # common mishearing
    assert app.strip_wake("what is the weather like") is None


# ---------------------------------------------------------------- the "brain" (local Ollama fallback)
# These never touch the network: brain_rewrite is mocked, so they only check that handle_command uses its
# output correctly and safely - never that a real model is running.

def test_brain_rewrite_is_fed_back_through_the_real_rules(monkeypatch):
    app.CFG["brain"] = True
    monkeypatch.setattr(app, "brain_rewrite", lambda raw: "volume up")
    assert app.handle_command("can you crank it please") is True


def test_brain_off_is_never_called(monkeypatch):
    app.CFG["brain"] = False
    called = []
    monkeypatch.setattr(app, "brain_rewrite", lambda raw: called.append(raw) or "volume up")
    assert app.handle_command("gibberish nonsense phrase") is False
    assert called == []


def test_brain_none_falls_through_to_sorry(monkeypatch):
    app.CFG["brain"] = True
    monkeypatch.setattr(app, "brain_rewrite", lambda raw: None)
    assert app.handle_command("gibberish nonsense phrase") is False


def test_brain_cannot_bypass_the_sleep_confirmation(monkeypatch):
    # The brain only proposes text; handle_command still runs it through the same rules, so a risky action
    # still needs a spoken "confirm" - the brain can't skip that step.
    app.CFG["brain"] = True
    monkeypatch.setattr(app, "brain_rewrite", lambda raw: "go to sleep")
    ran = []
    monkeypatch.setattr(app, "run", lambda *a, **k: ran.append(a))
    assert app.handle_command("put this thing to bed") is True
    assert app.PENDING["fn"] is not None
    assert ran == []


def test_brain_failure_does_not_crash(monkeypatch):
    app.CFG["brain"] = True

    def boom(url, timeout=3, **kw):
        raise OSError("connection refused")
    monkeypatch.setattr(app.urllib.request, "urlopen", boom)
    assert app.handle_command("gibberish nonsense phrase") is False

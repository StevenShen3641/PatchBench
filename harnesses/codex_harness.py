"""Runs Codex through ``codex exec``."""

import json
import os
import shutil
import subprocess
import threading

from pathlib import Path

from agent_base import AGENT_HOME, AgentHarness, AgentUnavailable, main
from constants import MODEL_PRICING

#: How often the rollout logs are re-read for a spend estimate.
POLL_INTERVAL_SECONDS = 15
#: How long codex gets to shut down cleanly when stopped at the budget.
STOP_GRACE_SECONDS = 10


class CodexHarness(AgentHarness):
    name = "codex"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pricing = MODEL_PRICING[self.model_name]
        self.codex_home = Path(AGENT_HOME) / ".codex"
        self._changed: set[str] = set()
        self._changed_lock = threading.Lock()

    def _install_config(self) -> None:
        """Copy ``codex_config/config.toml`` into the agent's codex home."""
        source = Path(__file__).parent / "codex_config" / "config.toml"
        home = Path(self.on_disk(self.codex_home))
        home.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy(source, home / "config.toml")
        else:
            print(f"note: no codex config at {source}", flush=True)

    # -- running the agent --------------------------------------------------

    def invoke(self, prompt: str) -> None:
        """Log in, then run ``codex exec`` while polling its spend."""
        self._install_config()
        key = os.environ.get("OPENAI_API_KEY", "")
        env = self.agent_env(CODEX_HOME=str(self.codex_home), OPENAI_API_KEY=key)
        login = subprocess.run(["codex", "login", "--with-api-key"], input=key, text=True,
                               env=env, check=False, **self.as_agent())
        if login.returncode:
            raise AgentUnavailable("login unsuccessful")

        print(prompt)
        command = [
            "codex",
            "--ask-for-approval", "never",
            "exec",
            "--json",
            "--model", self.model_name,
            "--config", 'model_reasoning_effort="medium"',
            "--config", 'web_search="disabled"',
            "--cd", self.repo_folder,
            "--sandbox", "danger-full-access",
            prompt,
        ]

        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True,
                                errors="ignore", env=env, **self.as_agent())
        stop = threading.Event()
        reader = threading.Thread(target=self._read_events, args=(proc,), daemon=True)
        monitor = threading.Thread(target=self._watch_spend, args=(proc, stop),
                                   daemon=True)
        reader.start()
        monitor.start()
        try:
            proc.wait()
        finally:
            stop.set()
            monitor.join()
            reader.join(timeout=30)
            self._save_rollouts()

    def _read_events(self, proc) -> None:
        """Collect edited paths while codex is still running, for snapshots."""
        for line in proc.stdout:
            paths = self._paths_in_event(line)
            if paths:
                with self._changed_lock:
                    self._changed.update(paths)

    def _watch_spend(self, proc, stop: threading.Event) -> None:
        """Price the latest token usage and kill codex at the budget."""
        while not stop.is_set() and proc.poll() is None:
            usage = self._latest_token_usage()
            if usage is None:
                print("Conversation not started yet; usage $0", flush=True)
            else:
                p = self.pricing
                uncached = usage["input_tokens"] - usage["cached_input_tokens"]
                spend = (uncached * p["input"]
                         + usage["cached_input_tokens"] * p["cached_input"]
                         + usage["output_tokens"] * p["output"]) / 1e6
                if self.note_spend(spend):
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=STOP_GRACE_SECONDS)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                    return
            if stop.wait(POLL_INTERVAL_SECONDS):
                return

    # -- rollout logs -------------------------------------------------------

    @property
    def _sessions_dir(self) -> str:
        return str(self.codex_home / "sessions")

    def _rollout_paths(self) -> list[str]:
        if not os.path.isdir(self._sessions_dir):
            return []
        found = subprocess.run(["find", self._sessions_dir, "-type", "f",
                                "-name", "rollout*.jsonl", "-print0"],
                               check=False, capture_output=True)
        return [p.decode("utf-8") for p in found.stdout.split(b"\0") if p]

    def _latest_token_usage(self):
        """The most recent ``token_count`` record from any rollout log."""
        for path in self._rollout_paths():
            with open(path, encoding="utf-8") as handle:
                lines = handle.readlines()
            for raw in reversed(lines):
                raw = raw.strip()
                if not raw:
                    continue
                record = json.loads(raw)
                payload = record.get("payload", {})
                if payload.get("type") == "token_count":
                    return payload["info"]["total_token_usage"]
        return None

    def _save_rollouts(self) -> None:
        """Copy the rollout logs into the log directory."""
        for path in self._rollout_paths():
            subprocess.run(["cp", path, str(self.log_dir)], check=False)

    # -- changed files ------------------------------------------------------

    @staticmethod
    def _paths_in_event(line: str) -> list[str]:
        """Paths named by one JSON event line, if it reports a file change."""
        line = line.strip()
        if not line:
            return []
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            # Anything non-JSON that leaks into stdout is not an event.
            return []
        if event.get("type") != "item.completed":
            return []
        item = event.get("item", {})
        if item.get("type") != "file_change":
            return []
        return [change.get("path", "") for change in item.get("changes", [])]

    def changed_files(self) -> list[str]:
        """Paths named by the ``file_change`` events codex printed."""
        with self._changed_lock:
            return sorted(p for p in self._changed if p)


if __name__ == "__main__":
    main(CodexHarness)

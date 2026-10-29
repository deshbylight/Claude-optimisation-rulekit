#!/usr/bin/env python3
"""Install the rulekit into a project in one command; safe to re-run.

    python install.py [TARGET] [--lang Russian] [--user] [--keep-powershell] [--force] [--dry-run]

TARGET defaults to the current directory. What it does:
  1. Copies kit files (rules, output style, skill, hooks, measurement tools, adaptation prompt).
     An existing file with different content is kept and reported (`--force`: overwrite, old copy
     saved as `<file>.rulekit-bak`).
  2. CLAUDE.md: absent → written from the template with detected values filled in; present → the
     template goes to `CLAUDE.rulekit.md` for the adaptation step to merge (CLAUDE.md is untouched);
     a previous install (manifest present) → not touched.
  3. `.claude/settings.json`: merged, never clobbered. Kit keys are added only when absent (a
     different existing value is reported); deny lists and skill overrides are unioned; kit hooks are
     appended unless the same command is already wired.
  4. Windows with Git Bash available: denies the PowerShell tool (~3.7k tokens per call) unless
     `--keep-powershell`.
  5. `.gitignore`: adds the kit's local-only entries.
  6. `--user`: merges `user/settings.json` into `~/.claude/settings.json` the same way (absent keys
     only), after saving `settings.json.rulekit-bak`.
  7. Writes `.claude/rulekit/manifest.json` (kit version, installed files with hashes) and prints the
     one prompt that finishes the adaptation inside Claude Code.
  8. Hook commands use `python` when it is a working Python 3, else `python3` (macOS/Linux).
`--uninstall` removes the kit files that are unchanged since install and the kit hooks; it leaves
CLAUDE.md, other settings keys and .gitignore entries and lists them for review.
Exit 1 on an unparsable existing settings file (nothing is written then).
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
VERSION = "0.4.0"

# kit path -> target path; directories are copied file by file.
FILES = [
    ".claude/output-styles/lean.md",
    ".claude/reference-rules",
    ".claude/skills/handoff",
    ".claude/rulekit/ADAPT.md",
    "Tools/claude_read_guard.py",
    "Tools/claude_topic_gate.py",
    "Tools/claude_session_length.py",
    "Tools/claude_reply_language.py",
    "Tools/claude_session_grep.py",
    "Tools/ctx_stats.py",
    "Docs/Review/OpenDefects.md",
    "Docs/plans/_TEMPLATE.md",
]
GITIGNORE = [".claude/handoff/", ".claude/settings.local.json", "*.rulekit-bak"]
HOOK_SCRIPT_RE = re.compile(r"Tools/[\w.-]+\.py")
MANIFEST = ".claude/rulekit/manifest.json"
ADAPT_PROMPT = "Read .claude/rulekit/ADAPT.md and follow it."


class Installer:
    def __init__(self, target: str, dry_run: bool, force: bool):
        self.target, self.dry_run, self.force = target, dry_run, force
        self.done, self.kept, self.installed = [], [], {}
        self.python = "python"

    def _write(self, rel: str, text: str):
        path = os.path.join(self.target, rel)
        if not self.dry_run:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

    def _backup(self, path: str):
        if not self.dry_run:
            shutil.copy2(path, path + ".rulekit-bak")

    # 1. files
    def copy(self, rel: str):
        src = os.path.join(KIT, rel)
        if os.path.isdir(src):
            for dirpath, _, names in os.walk(src):
                for name in names:
                    if name != "__pycache__" and not name.endswith(".pyc"):
                        self.copy(os.path.relpath(os.path.join(dirpath, name), KIT).replace("\\", "/"))
            return
        with open(src, encoding="utf-8") as f:
            text = f.read()
        dst = os.path.join(self.target, rel)
        if os.path.isfile(dst):
            with open(dst, encoding="utf-8", errors="replace") as f:
                if f.read() == text:
                    self.installed[rel] = digest(text)
                    return
            if not self.force:
                self.kept.append(f"{rel}: exists with different content, kept (--force overwrites)")
                return
            self._backup(dst)
        self._write(rel, text)
        self.installed[rel] = digest(text)
        self.done.append(f"wrote {rel}")

    # 2. CLAUDE.md
    def claude_md(self, lang: str):
        if os.path.isfile(os.path.join(self.target, MANIFEST)):
            self.kept.append("CLAUDE.md: kit already installed here (manifest found), not touched")
            return
        with open(os.path.join(KIT, "template", "CLAUDE.md"), encoding="utf-8") as f:
            text = fill_template(f.read(), self.target, lang)
        if self.python != "python":
            text = text.replace("`python Tools/", f"`{self.python} Tools/")
        if os.path.isfile(os.path.join(self.target, "CLAUDE.md")):
            self._write("CLAUDE.rulekit.md", text)
            self.done.append("CLAUDE.md exists: template written to CLAUDE.rulekit.md (merged by the adaptation step)")
        else:
            self._write("CLAUDE.md", text)
            self.done.append("wrote CLAUDE.md from the template")

    # 3/6. settings
    def merge_settings(self, path: str, kit_settings: dict, label: str, backup: bool) -> bool:
        current = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    current = json.load(f)
            except ValueError as e:
                print(f"error: {path} is not plain JSON ({e}); fix or merge it by hand", file=sys.stderr)
                return False
        notes = merge(current, kit_settings)
        self.kept += [f"{label}: {n}" for n in notes if n.startswith("kept")]
        changes = [n for n in notes if not n.startswith("kept")]
        if changes:
            if backup and os.path.isfile(path):
                self._backup(path)
            if not self.dry_run:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(current, f, indent=2, ensure_ascii=False)
                    f.write("\n")
            self.done += [f"{label}: {n}" for n in changes]
        return True

    def uninstall(self) -> int:
        path = os.path.join(self.target, MANIFEST)
        if not os.path.isfile(path):
            print(f"error: no {MANIFEST} in {self.target}: nothing installed by this kit", file=sys.stderr)
            return 1
        with open(path, encoding="utf-8") as f:
            files = json.load(f).get("files") or {}
        if isinstance(files, list):  # 0.3.0 manifests had no hashes: treat every file as modified
            files = {rel: "" for rel in files}
        for rel, sha in sorted(files.items()):
            full = os.path.join(self.target, rel)
            if not os.path.isfile(full):
                continue
            with open(full, encoding="utf-8", errors="replace") as f:
                same = digest(f.read()) == sha
            if same or self.force:
                if not self.dry_run:
                    os.remove(full)
                self.done.append(f"removed {rel}")
            else:
                self.kept.append(f"{rel}: changed since install, kept (--force removes)")
        settings_path = os.path.join(self.target, ".claude", "settings.json")
        if os.path.isfile(settings_path):
            with open(settings_path, encoding="utf-8") as f:
                current = json.load(f)
            scripts = {hook_key(f"Tools/{os.path.basename(r)}") for r in files if r.startswith("Tools/")}
            removed = unwire_hooks(current.get("hooks", {}), scripts)
            if removed:
                if not current["hooks"]:
                    del current["hooks"]
                if not self.dry_run:
                    with open(settings_path, "w", encoding="utf-8", newline="\n") as f:
                        json.dump(current, f, indent=2, ensure_ascii=False)
                        f.write("\n")
                self.done += [f".claude/settings.json: removed hook {r}" for r in removed]
        if not self.dry_run:
            os.remove(path)
            for rel in sorted({os.path.dirname(r) for r in files} | {os.path.dirname(MANIFEST)}, key=len, reverse=True):
                full = os.path.join(self.target, rel)
                while rel and os.path.isdir(full) and not os.listdir(full):
                    os.rmdir(full)
                    rel = os.path.dirname(rel)
                    full = os.path.join(self.target, rel)
        self.done.append(f"removed {MANIFEST}")
        self.kept.append("CLAUDE.md, other .claude/settings.json keys and .gitignore entries are left as they are: "
                         "review them (the install backup is .claude/settings.json.rulekit-bak)")
        return 0

    # 5. .gitignore
    def gitignore(self):
        path = os.path.join(self.target, ".gitignore")
        lines = []
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        missing = [g for g in GITIGNORE if g not in lines]
        if missing and not self.dry_run:
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                if lines and lines[-1].strip():
                    f.write("\n")
                f.write("# rulekit\n" + "\n".join(missing) + "\n")
        if missing:
            self.done.append(".gitignore: added " + ", ".join(missing))


def merge(current: dict, kit: dict, prefix: str = "") -> list:
    """Adds kit keys missing from `current` in place; returns one note per change or conflict."""
    notes = []
    for key, value in kit.items():
        name = prefix + key
        if key == "$schema":
            current.setdefault(key, value)
        elif key not in current:
            current[key] = value
            notes.append(f"set {name}")
        elif key == "hooks":
            notes += merge_hooks(current[key], value)
        elif isinstance(value, list) and isinstance(current[key], list):
            added = [v for v in value if v not in current[key]]
            current[key] += added
            if added:
                notes.append(f"{name}: added {', '.join(map(str, added))}")
        elif isinstance(value, dict) and isinstance(current[key], dict):
            notes += merge(current[key], value, name + ".")
        elif current[key] != value:
            notes.append(f"kept {name} = {json.dumps(current[key])} (kit suggests {json.dumps(value)})")
    return notes


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def unwire_hooks(hooks: dict, scripts: set) -> list:
    removed = []
    for event in list(hooks):
        for group in list(hooks[event]):
            keep = [h for h in group.get("hooks", []) if hook_key(h.get("command")) not in scripts]
            removed += [hook_key(h.get("command")) for h in group.get("hooks", []) if h not in keep]
            if keep:
                group["hooks"] = keep
            else:
                hooks[event].remove(group)
        if not hooks[event]:
            del hooks[event]
    return removed


def hook_key(command: str) -> str:
    """The script a hook command runs, so `python x.py` and `python3 x.py` count as the same hook."""
    m = HOOK_SCRIPT_RE.search(command or "")
    return m.group(0) if m else command


def merge_hooks(current: dict, kit: dict) -> list:
    notes = []
    wired = {hook_key(h.get("command")) for groups in current.values() for g in groups for h in g.get("hooks", [])}
    for event, groups in kit.items():
        for group in groups:
            new = [h for h in group.get("hooks", []) if hook_key(h.get("command")) not in wired]
            if new:
                current.setdefault(event, []).append(dict(group, hooks=new))
                notes += [f"hooks.{event}: added {h['command'].split('/')[-1].strip(chr(34))}" for h in new]
    return notes


def python_command() -> str:
    """`python` when it is a working Python 3 (not a store stub), else `python3`; hooks use this name."""
    for name in ("python", "python3"):
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            out = subprocess.run([exe, "-c", "import sys; print(sys.version_info[0])"],
                                 capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if out == "3":
            return name
    return "python3"


def set_python(settings: dict, python: str):
    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                if hook.get("command", "").startswith("python "):
                    hook["command"] = python + hook["command"][len("python"):]


def git_bash_available() -> bool:
    """Claude Code on Windows uses Git Bash for its Bash tool (WSL bash does not count)."""
    configured = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if configured and os.path.isfile(configured):
        return True
    git = shutil.which("git")
    if not git:
        return False
    # git.exe sits in <Git>/cmd, <Git>/bin or <Git>/mingw64/bin; bash.exe in <Git>/bin.
    root = os.path.dirname(os.path.realpath(git))
    for _ in range(3):
        root = os.path.dirname(root)
        if os.path.isfile(os.path.join(root, "bin", "bash.exe")) and os.path.isfile(os.path.join(root, "git-bash.exe")):
            return True
    return False


def detect(target: str) -> dict:
    """Best-effort stack and commands from manifest files; empty values stay placeholders."""
    has = lambda name: os.path.isfile(os.path.join(target, name))
    top = os.listdir(target)
    found = {"stack": [], "build": "", "test": ""}
    if has("package.json"):
        try:
            with open(os.path.join(target, "package.json"), encoding="utf-8") as f:
                scripts = (json.load(f).get("scripts") or {})
        except ValueError:
            scripts = {}
        runner = "pnpm" if has("pnpm-lock.yaml") else "yarn" if has("yarn.lock") else "npm run"
        found["stack"].append("Node.js" + (" + TypeScript" if has("tsconfig.json") else ""))
        found["build"] = found["build"] or (f"{runner} build" if "build" in scripts else "")
        found["test"] = found["test"] or (("npm test" if runner == "npm run" else f"{runner} test")
                                          if "test" in scripts else "")
    if has("pyproject.toml") or has("setup.py") or has("requirements.txt"):
        found["stack"].append("Python")
        if os.path.isdir(os.path.join(target, "tests")) or has("pytest.ini") or has("conftest.py"):
            found["test"] = found["test"] or "pytest -q"
    if has("Cargo.toml"):
        found["stack"].append("Rust")
        found["build"], found["test"] = found["build"] or "cargo build", found["test"] or "cargo test"
    if has("go.mod"):
        found["stack"].append("Go")
        found["build"], found["test"] = found["build"] or "go build ./...", found["test"] or "go test ./..."
    if has("CMakeLists.txt"):
        found["stack"].append("C/C++ (CMake)")
        found["build"] = found["build"] or "cmake --build build"
        found["test"] = found["test"] or "ctest --test-dir build"
    if any(n.endswith((".sln", ".csproj")) for n in top):
        found["stack"].append(".NET")
        found["build"], found["test"] = found["build"] or "dotnet build", found["test"] or "dotnet test"
    if any(n.endswith(".uproject") for n in top):
        found["stack"].append("Unreal Engine")
    if has("Makefile"):
        with open(os.path.join(target, "Makefile"), encoding="utf-8", errors="replace") as f:
            targets = {line.split(":")[0] for line in f if ":" in line and not line.startswith(("\t", " "))}
        found["build"] = found["build"] or ("make build" if "build" in targets else "")
        found["test"] = found["test"] or ("make test" if "test" in targets else "")
    return found


def fill_template(text: str, target: str, lang: str) -> str:
    d = detect(target)
    name = os.path.basename(os.path.abspath(target))
    text = text.replace("# <ProjectName>", f"# {name}", 1)
    text = text.replace("<every reply to the user is in LANGUAGE; code, identifiers, commands and log text stay as-is>",
                        f"every reply to the user is in {lang or 'English'}; code, identifiers, commands and log text stay as-is")
    if d["stack"]:
        text = text.replace("<one line: what it is, stack, main entry points>",
                            f"<one line: what it is, main entry points>; stack: {', '.join(d['stack'])}")
    for key, holder in (("build", "<build command>"), ("test", "<test command>")):
        if d[key]:
            text = text.replace(f"`{holder}`", f"`{d[key]}`")
    if d["build"]:
        text = text.replace("- Build: `<command>`", f"- Build: `{d['build']}`")
    if d["test"]:
        text = text.replace("Tests: `<command>`", f"Tests: `{d['test']}`")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target", nargs="?", default=os.getcwd())
    ap.add_argument("--lang", default="", help="chat language, e.g. Russian (default English)")
    ap.add_argument("--user", action="store_true", help="also merge user/settings.json into ~/.claude/settings.json")
    ap.add_argument("--keep-powershell", action="store_true", help="do not deny the PowerShell tool on Windows")
    ap.add_argument("--force", action="store_true", help="overwrite kit files that differ (backups kept)")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove unchanged kit files and kit hooks recorded in the manifest")
    ap.add_argument("--dry-run", action="store_true", help="print what would change, write nothing")
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        print(f"error: {target} is not a directory", file=sys.stderr)
        return 1
    if os.path.samefile(target, KIT):
        print("error: target is the kit itself", file=sys.stderr)
        return 1
    inst = Installer(target, args.dry_run, args.force)
    if args.uninstall:
        code = inst.uninstall()
        if code == 0:
            print(("DRY RUN — nothing written\n" if args.dry_run else "") + f"rulekit uninstalled from {target}")
            for line in inst.done:
                print("  - " + line)
            for line in inst.kept:
                print("  = " + line)
        return code

    with open(os.path.join(KIT, ".claude", "settings.json"), encoding="utf-8") as f:
        kit_settings = json.load(f)
    inst.python = python_command()
    set_python(kit_settings, inst.python)
    if args.lang:
        kit_settings["env"]["RULEKIT_REPLY_LANG"] = args.lang
    else:
        kit_settings["env"].pop("RULEKIT_REPLY_LANG", None)
        if not kit_settings["env"]:
            del kit_settings["env"]
    deny_ps = platform.system() == "Windows" and not args.keep_powershell and git_bash_available()
    if deny_ps:
        kit_settings["permissions"]["deny"].append("PowerShell")
    if not inst.merge_settings(os.path.join(target, ".claude", "settings.json"), kit_settings,
                               ".claude/settings.json", backup=True):
        return 1
    if args.user:
        with open(os.path.join(KIT, "user", "settings.json"), encoding="utf-8") as f:
            user_settings = json.load(f)
        if not inst.merge_settings(os.path.join(os.path.expanduser("~"), ".claude", "settings.json"),
                                   user_settings, "~/.claude/settings.json", backup=True):
            return 1

    for rel in FILES:
        inst.copy(rel)
    inst.claude_md(args.lang)
    inst.gitignore()
    manifest = {"version": VERSION, "files": dict(sorted(inst.installed.items()))}
    inst._write(MANIFEST, json.dumps(manifest, indent=2) + "\n")

    print(("DRY RUN — nothing written\n" if args.dry_run else "") + f"rulekit {VERSION} -> {target}")
    for line in inst.done:
        print("  + " + line)
    for line in inst.kept:
        print("  = " + line)
    if not inst.done:
        print("  (already up to date)")
    if platform.system() == "Windows" and not deny_ps:
        print("  ! PowerShell tool left enabled (" + ("--keep-powershell" if args.keep_powershell
              else "Git Bash not found") + ")")
    print(f"\nNext: open Claude Code in {target} and send:\n\n    {ADAPT_PROMPT}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

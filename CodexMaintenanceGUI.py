import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk


APP_TITLE = "AI管理大师"


class CodexMaintenanceGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1040x700")
        self.root.minsize(920, 620)

        self.tool_dir = Path(__file__).resolve().parent
        self.repair_script = self.tool_dir / "repair_codex_desktop_history.py"
        self.python_exe = self.find_console_python()
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_threadripper_status: dict[str, object] = {}

        self.codex_home_var = StringVar()
        self.status_var = StringVar(value="请选择或确认 Codex 数据目录")
        self.feature_var = StringVar(value="历史恢复")

        self.include_archived = BooleanVar(value=False)
        self.allow_missing_cwd = BooleanVar(value=False)
        self.allow_empty_cwd = BooleanVar(value=False)
        self.allow_missing_session = BooleanVar(value=False)
        self.unarchive_selected = BooleanVar(value=False)
        self.sync_provider = BooleanVar(value=False)
        self.install_threadripper = BooleanVar(value=False)
        self.advanced_visible = False

        self.detected_homes = self.detect_codex_homes()
        if self.detected_homes:
            self.codex_home_var.set(str(self.detected_homes[0]))

        self.build_ui()
        self.validate_codex_home()
        self.root.after(100, self.drain_output_queue)

    def find_console_python(self) -> str:
        current = Path(sys.executable)
        if current.name.lower() == "pythonw.exe":
            python_exe = current.with_name("python.exe")
            if python_exe.exists():
                return str(python_exe)

        bundled = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "python.exe"
        if bundled.exists():
            return str(bundled)
        return sys.executable

    def detect_codex_homes(self) -> list[Path]:
        candidates: list[Path] = []

        env_home = os.environ.get("CODEX_HOME")
        if env_home:
            candidates.append(Path(env_home))

        candidates.append(Path.home() / ".codex")
        candidates.append(self.tool_dir.parent)

        migration_root = Path.home() / "Documents" / "Codex"
        if migration_root.exists():
            for child in migration_root.glob("*"):
                if child.is_dir():
                    candidates.append(child)

        seen: set[str] = set()
        result: list[Path] = []
        for candidate in candidates:
            try:
                resolved = candidate.expanduser().resolve()
            except OSError:
                resolved = candidate.expanduser()
            key = str(resolved).lower()
            if key not in seen:
                seen.add(key)
                result.append(resolved)
        return result

    def build_ui(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self.root, padding=(12, 14))
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.columnconfigure(0, weight=1)

        title = ttk.Label(sidebar, text=APP_TITLE, font=("Microsoft YaHei UI", 13, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 18))

        features = ["历史恢复", "历史诊断", "脏数据清理", "聊天导出", "备份恢复"]
        for index, name in enumerate(features, start=1):
            text = name if name == "历史恢复" else f"{name}（后续）"
            label = ttk.Label(sidebar, text=text)
            label.grid(row=index, column=0, sticky="w", pady=7)

        main = ttk.Frame(self.root, padding=(16, 14))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)

        path_frame = ttk.LabelFrame(main, text="自动检测到的 Codex 数据目录", padding=10)
        path_frame.grid(row=0, column=0, sticky="ew")
        path_frame.columnconfigure(0, weight=1)

        values = [str(path) for path in self.detected_homes]
        self.home_combo = ttk.Combobox(path_frame, textvariable=self.codex_home_var, values=values)
        self.home_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.home_combo.bind("<<ComboboxSelected>>", lambda _event: self.validate_codex_home())
        self.home_combo.bind("<FocusOut>", lambda _event: self.validate_codex_home())

        browse_button = ttk.Button(path_frame, text="找不到再点...", command=self.browse_codex_home)
        browse_button.grid(row=0, column=1)

        status = ttk.Label(path_frame, textvariable=self.status_var)
        status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        header = ttk.Frame(main)
        header.grid(row=1, column=0, sticky="ew", pady=(14, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="一键搜索聊天记录", font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="小白模式会自动使用安全规则：不恢复归档、不恢复已删除工作区、不恢复空工作区。",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(
            header,
            text="正常不用管登录方式和提供商。工具会自动搜索所有来源的聊天；恢复时也会自动检查是否需要修复隐藏聊天识别。",
            wraplength=760,
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

        self.summary_frame = ttk.Frame(main)
        self.summary_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        for column in range(4):
            self.summary_frame.columnconfigure(column, weight=1)
        self.summary_labels: dict[str, StringVar] = {}
        self.create_summary_card(0, "总线程", "待预览")
        self.create_summary_card(1, "可恢复", "待预览")
        self.create_summary_card(2, "已跳过", "待预览")
        self.create_summary_card(3, "Provider", "待预览")

        actions = ttk.Frame(main, padding=(0, 6))
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(2, weight=1)

        self.search_button = ttk.Button(actions, text="搜索聊天记录", command=self.search_chat_history)
        self.search_button.grid(row=0, column=0, sticky="w", ipadx=28, ipady=12, padx=(0, 8))
        self.preview_button = self.search_button

        self.quick_repair_button = ttk.Button(actions, text="恢复聊天记录", command=self.run_repair)
        self.quick_repair_button.grid(row=0, column=1, sticky="w", ipadx=28, ipady=12, padx=(0, 12))

        ttk.Label(actions, text="先搜索确认数量，再关闭 Codex Desktop 后恢复。").grid(row=0, column=2, sticky="w")
        self.advanced_button = ttk.Button(actions, text="高级设置", command=self.toggle_advanced)
        self.advanced_button.grid(row=0, column=3, sticky="e")

        self.advanced_container = ttk.LabelFrame(main, text="高级设置", padding=10)
        self.advanced_container.grid(row=4, column=0, sticky="ew", pady=(4, 8))
        self.advanced_container.grid_remove()
        options = self.advanced_container
        for column in range(3):
            options.columnconfigure(column, weight=1)

        self.add_option(options, 0, 0, "包含归档", self.include_archived, "会把已归档聊天也列入搜索/恢复结果。默认关闭。")
        self.add_option(options, 0, 1, "允许已删除工作区", self.allow_missing_cwd, "会显示原工作目录已不存在的聊天，可能回到旧项目分组。")
        self.add_option(options, 0, 2, "允许空工作区", self.allow_empty_cwd, "会显示目录存在但为空的聊天，可能出现空项目。")
        self.add_option(options, 1, 0, "允许缺失 session", self.allow_missing_session, "会显示找不到会话文件的记录，可能无法打开完整内容。")
        self.add_option(options, 1, 1, "取消所选归档标记", self.unarchive_selected, "正式恢复时会把选中的归档聊天改成未归档。")
        self.add_option(options, 1, 2, "强制修复隐藏聊天识别", self.sync_provider, "默认会在检测到不匹配时自动尝试。勾选后会在恢复时强制执行一次。")
        self.add_option(options, 2, 0, "允许安装 threadripper", self.install_threadripper, "会通过 npm 安装辅助工具，需要联网。")

        advanced_actions = ttk.Frame(options)
        advanced_actions.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.repair_button = ttk.Button(advanced_actions, text="执行修复", command=self.run_repair)
        self.repair_button.grid(row=0, column=0)

        log_frame = ttk.LabelFrame(main, text="搜索日志", padding=8)
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = ttk.Treeview(log_frame, columns=("message",), show="headings", height=14)
        self.log.heading("message", text="输出")
        self.log.column("message", width=780, stretch=True)
        self.log.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

    def create_summary_card(self, column: int, title: str, initial: str) -> None:
        frame = ttk.LabelFrame(self.summary_frame, text=title, padding=8)
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        value = StringVar(value=initial)
        self.summary_labels[title] = value
        ttk.Label(frame, textvariable=value, font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")

    def add_option(self, parent: ttk.Frame, row: int, column: int, text: str, variable: BooleanVar, help_text: str) -> None:
        frame = ttk.Frame(parent, padding=(0, 2))
        frame.grid(row=row, column=column, sticky="new", padx=(0, 12), pady=3)
        frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(frame, text=text, variable=variable).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text=help_text, wraplength=250, foreground="#555555").grid(row=1, column=0, sticky="w", pady=(2, 0))

    def select_feature(self, name: str) -> None:
        self.feature_var.set(name)
        if name != "历史恢复":
            self.append_log(f"{name} 还没有实现，后续可以作为独立模块接入。")

    def toggle_advanced(self) -> None:
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced_container.grid()
            self.advanced_button.configure(text="收起高级")
        else:
            self.advanced_container.grid_remove()
            self.advanced_button.configure(text="高级设置")

    def browse_codex_home(self) -> None:
        selected = filedialog.askdirectory(title="选择 Codex 数据目录")
        if selected:
            self.codex_home_var.set(selected)
            current_values = list(self.home_combo.cget("values"))
            if selected not in current_values:
                current_values.insert(0, selected)
                self.home_combo.configure(values=current_values)
            self.validate_codex_home()

    def validate_codex_home(self) -> bool:
        codex_home = Path(self.codex_home_var.get()).expanduser()
        missing = []
        if not (codex_home / "state_5.sqlite").exists():
            missing.append("state_5.sqlite")
        if not (codex_home / ".codex-global-state.json").exists():
            missing.append(".codex-global-state.json")

        if missing:
            self.status_var.set("无效目录，缺少：" + ", ".join(missing))
            return False

        self.status_var.set("有效 Codex 数据目录")
        return True

    def base_repair_args(self, dry_run: bool) -> list[str]:
        args = [
            self.python_exe,
            "-X",
            "utf8",
            str(self.repair_script),
            "--codex-home",
            self.codex_home_var.get(),
            "--projectless-mode",
            "none",
        ]
        if dry_run:
            args.append("--dry-run")
        if self.include_archived.get():
            args.append("--include-archived")
        if self.allow_missing_cwd.get():
            args.append("--allow-missing-cwd")
        if self.allow_empty_cwd.get():
            args.append("--allow-empty-cwd")
        if self.allow_missing_session.get():
            args.append("--allow-missing-session")
        if self.unarchive_selected.get():
            args.append("--unarchive-selected")
        return args

    def preview_repair(self) -> None:
        if not self.ensure_ready("预览"):
            return
        commands = []
        if self.threadripper_command():
            commands.append(["__THREADRIPPER_STATUS__"])
        elif self.sync_provider.get():
            self.append_log("codex-threadripper 未安装，跳过隐藏聊天识别检查。")
        commands.append(self.base_repair_args(dry_run=True))
        self.run_commands(commands, "预览恢复")

    def search_chat_history(self) -> None:
        self.sync_provider.set(False)
        self.preview_repair()

    def run_repair(self) -> None:
        if not self.ensure_ready("修复"):
            return
        confirmed = messagebox.askyesno(
            "确认执行修复",
            "请先关闭 Codex Desktop，再继续。\n\n默认不会恢复归档、已删除工作区或空工作区。\n正式运行会创建备份。是否继续？",
        )
        if not confirmed:
            return

        commands = []
        if self.threadripper_command():
            commands.append(["__THREADRIPPER_STATUS__"])
            commands.append(["__AUTO_THREADRIPPER_SYNC__"])
        elif self.install_threadripper.get():
            npm = shutil.which("npm")
            if npm:
                commands.append([npm, "i", "-g", "codex-threadripper"])
                commands.append(["__THREADRIPPER_STATUS__"])
                commands.append(["__AUTO_THREADRIPPER_SYNC__"])
            else:
                self.append_log("npm 未安装，无法安装隐藏聊天识别修复工具。将只做基础恢复。")
        else:
            self.append_log("未检测到隐藏聊天识别修复工具，将只做基础恢复。")
        commands.append(self.base_repair_args(dry_run=False))
        self.run_commands(commands, "执行修复")

    def ensure_ready(self, action: str) -> bool:
        if self.feature_var.get() != "历史恢复":
            messagebox.showinfo("功能未实现", "当前只实现了“历史恢复”。")
            return False
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在运行", "已有任务正在运行，请等待完成。")
            return False
        if not self.validate_codex_home():
            messagebox.showerror("目录无效", "请选择有效的 Codex 数据目录。")
            return False
        if not self.repair_script.exists():
            messagebox.showerror("脚本缺失", f"找不到修复脚本：{self.repair_script}")
            return False
        self.append_log(f"开始{action}...")
        return True

    def run_commands(self, commands: list[list[str]], label: str) -> None:
        self.preview_button.configure(state="disabled")
        self.quick_repair_button.configure(state="disabled")
        self.repair_button.configure(state="disabled")
        self.worker = threading.Thread(target=self.command_worker, args=(commands, label), daemon=True)
        self.worker.start()

    def command_worker(self, commands: list[list[str]], label: str) -> None:
        try:
            for command in commands:
                if command == ["__THREADRIPPER_STATUS__"]:
                    threadripper = self.threadripper_command()
                    if not threadripper:
                        self.output_queue.put("未找到隐藏聊天识别修复工具，跳过状态检查。")
                        continue
                    command = [threadripper, "--codex-home", self.codex_home_var.get(), "status"]
                elif command == ["__AUTO_THREADRIPPER_SYNC__"]:
                    threadripper = self.threadripper_command()
                    if not threadripper:
                        self.output_queue.put("隐藏聊天识别修复工具安装后仍未找到，跳过自动修复。")
                        continue
                    rows = int(self.last_threadripper_status.get("rows_needing_reconcile") or 0)
                    if rows <= 0 and not self.sync_provider.get():
                        self.output_queue.put("隐藏聊天识别已经对齐，跳过自动修复。")
                        continue
                    command = [threadripper, "--codex-home", self.codex_home_var.get(), "sync"]
                self.output_queue.put("> " + " ".join(command))
                process = subprocess.run(
                    command,
                    cwd=str(self.tool_dir),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    **self.subprocess_window_options(),
                )
                if process.stdout:
                    self.output_queue.put(process.stdout)
                if process.stderr:
                    self.output_queue.put(process.stderr)
                if process.returncode != 0:
                    self.output_queue.put(f"{label}失败，退出码：{process.returncode}")
                    return
                if command[-1] == "status":
                    parsed = self.parse_threadripper_status(process.stdout)
                    if parsed:
                        self.output_queue.put("__THREADRIPPER_STATUS__" + json.dumps(parsed, ensure_ascii=False))
                self.try_update_summary(process.stdout)
            self.output_queue.put(f"{label}完成。")
        except FileNotFoundError as exc:
            self.output_queue.put(f"命令不存在：{exc.filename}")
        except Exception as exc:
            self.output_queue.put(f"运行失败：{exc}")
        finally:
            self.output_queue.put("__TASK_DONE__")

    def subprocess_window_options(self) -> dict:
        if os.name != "nt":
            return {}

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        return {
            "startupinfo": startupinfo,
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        }

    def try_update_summary(self, text: str) -> None:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return
        self.output_queue.put("__SUMMARY__" + json.dumps(data, ensure_ascii=False))

    def threadripper_command(self) -> str | None:
        return shutil.which("codex-threadripper")

    def parse_threadripper_status(self, text: str) -> dict[str, object]:
        parsed: dict[str, object] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("Target provider:"):
                parsed["target_provider"] = line.split(":", 1)[1].strip()
            elif line.startswith("Rows needing reconcile:"):
                match = re.search(r"(\d+)$", line)
                if match:
                    parsed["rows_needing_reconcile"] = int(match.group(1))
        return parsed

    def drain_output_queue(self) -> None:
        try:
            while True:
                item = self.output_queue.get_nowait()
                if item == "__TASK_DONE__":
                    self.preview_button.configure(state="normal")
                    self.quick_repair_button.configure(state="normal")
                    self.repair_button.configure(state="normal")
                elif item.startswith("__SUMMARY__"):
                    data = json.loads(item.removeprefix("__SUMMARY__"))
                    self.update_summary(data)
                elif item.startswith("__THREADRIPPER_STATUS__"):
                    data = json.loads(item.removeprefix("__THREADRIPPER_STATUS__"))
                    self.last_threadripper_status = data
                    rows = int(data.get("rows_needing_reconcile") or 0)
                    target = data.get("target_provider") or "未知"
                    if rows > 0:
                        self.append_log(f"检测到隐藏聊天识别不匹配：{rows} 条需要修复，当前目标来源是 {target}。")
                    else:
                        self.append_log(f"隐藏聊天识别已对齐，当前目标来源是 {target}。")
                else:
                    for line in item.splitlines():
                        self.append_log(line)
        except queue.Empty:
            pass
        self.root.after(100, self.drain_output_queue)

    def update_summary(self, data: dict) -> None:
        self.summary_labels["总线程"].set(str(data.get("threads_total", "未知")))
        self.summary_labels["可恢复"].set(str(data.get("threads_selected", "未知")))
        self.summary_labels["已跳过"].set(str(data.get("threads_skipped", "未知")))
        providers = data.get("providers") or {}
        provider_text = ", ".join(f"{key}:{value}" for key, value in providers.items()) or "未知"
        self.summary_labels["Provider"].set(provider_text)

    def append_log(self, message: str) -> None:
        if not message:
            return
        self.log.insert("", "end", values=(message,))
        children = self.log.get_children()
        if len(children) > 1000:
            self.log.delete(children[0])
        self.log.yview_moveto(1.0)


def main() -> int:
    root = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass
    CodexMaintenanceGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

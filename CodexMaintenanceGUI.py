import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from collections import deque
import tkinter as tk
from tkinter import BooleanVar, Canvas, StringVar, Tk, Toplevel, filedialog, messagebox, simpledialog
from tkinter import ttk
from datetime import datetime

from prelaunch_manager import (
    ProviderProfile,
    collect_prelaunch_evidence,
    configure_provider_for_launch,
    find_codex_desktop_exe,
    launch_codex_desktop,
    parse_threadripper_status,
    prepare_codex_takeover,
    threadripper_command,
)
import repair_codex_desktop_history as history_repair


APP_TITLE = "AI Strategist"
APP_SUBTITLE = "Codex Prelaunch Console"
FONT_FAMILY = "Microsoft YaHei UI"

COLOR_BG = "#0f1117"
COLOR_SURFACE = "#161922"
COLOR_PANEL = "#1d212b"
COLOR_PANEL_ALT = "#222631"
COLOR_BORDER = "#303644"
COLOR_TEXT = "#eef1f7"
COLOR_MUTED = "#9aa3b2"
COLOR_ACCENT = "#5e6ad2"
COLOR_ACCENT_DARK = "#4148a8"
COLOR_SUCCESS = "#36b37e"
COLOR_BTN_BG = "#ffffff"
COLOR_BTN_TEXT = "#0b0d12"
COLOR_BTN_MUTED = "#495162"
COLOR_BTN_BORDER = "#d7dde8"

MODULE_LOGIN = "login"
MODULE_RESTORE = "restore"
MODULE_CLEANUP = "cleanup"


class ToolTip:
    def __init__(self, widget: ttk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._on_enter, add=True)
        widget.bind("<Leave>", self._on_leave, add=True)
        widget.bind("<ButtonPress>", self._on_leave, add=True)

    def _on_enter(self, _event=None) -> None:
        # small delay prevents flicker when moving across widgets
        self._after_id = self.widget.after(450, self.show)

    def _on_leave(self, _event=None) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.hide()

    def show(self) -> None:
        if self.tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 14
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except Exception:
            return

        tip = Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.geometry(f"+{x}+{y}")

        frame = ttk.Frame(tip, padding=(10, 8))
        frame.grid()
        label = ttk.Label(frame, text=self.text, justify="left", wraplength=420)
        label.grid()
        self.tip = tip

    def hide(self) -> None:
        if self.tip is None:
            return
        try:
            self.tip.destroy()
        except Exception:
            pass
        self.tip = None


class CodexMaintenanceGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1120x760")
        self.root.minsize(980, 640)
        self.root.configure(bg=COLOR_BG)

        self.tool_dir = Path(__file__).resolve().parent
        self.repair_script = self.tool_dir / "repair_codex_desktop_history.py"
        self.python_exe = self.find_console_python()
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_threadripper_status: dict[str, object] = {}
        self.last_prelaunch_evidence: dict[str, object] = {}
        self.log_buffer: deque[str] = deque(maxlen=4000)
        self.log_summary: deque[str] = deque(maxlen=3)
        self.log_summary_var = StringVar(value="")
        self.auth_status_var = StringVar(value="待检查")
        self.channel_status_var = StringVar(value="待检查")
        self.reconcile_status_var = StringVar(value="待检查")
        self.plugin_status_var = StringVar(value="待检查")
        self.current_state_var = StringVar(value="等待启动前检查")
        self.current_report_dir: Path | None = None
        self.current_report_meta: dict[str, object] = {}
        self.latest_report_dir_var = StringVar(value="")

        self.codex_home_var = StringVar()
        self.status_var = StringVar(value="请选择或确认 Codex 数据目录")
        self.feature_var = StringVar(value="历史恢复")
        self.launch_mode = StringVar(value="official")
        self.launch_mode_help_var = StringVar()
        self.launch_action_var = StringVar(value="配置并启动 Codex")
        self.module_var = StringVar(value=MODULE_LOGIN)
        self.tools_open = BooleanVar(value=False)
        self.tools_toggle_label_var = StringVar(value="更多工具 ▸")
        self.issue_hint_var = StringVar(value="")
        self.provider_key_var = StringVar(value="cliproxy")
        self.provider_name_var = StringVar(value="CLIProxyAPI")
        self.provider_base_url_var = StringVar(value="http://127.0.0.1:8317/v1")
        self.provider_wire_api_var = StringVar(value="responses")
        self.provider_env_key_var = StringVar(value="OPENAI_API_KEY")
        self.provider_bearer_token_var = StringVar(value="")
        self.provider_requires_auth = BooleanVar(value=False)

        self.history_root_var = StringVar(value=str(Path.home() / "Documents" / "Codex"))
        self.include_archived = BooleanVar(value=True)
        self.allow_missing_cwd = BooleanVar(value=True)
        self.allow_empty_cwd = BooleanVar(value=True)
        self.allow_missing_session = BooleanVar(value=False)
        self.unarchive_selected = BooleanVar(value=True)
        self.sync_provider = BooleanVar(value=False)
        self.install_threadripper = BooleanVar(value=False)
        self.advanced_visible = False
        self.keep_latest_backups = StringVar(value="10")

        self.detected_homes = self.detect_codex_homes()
        if self.detected_homes:
            self.codex_home_var.set(str(self.detected_homes[0]))

        self.configure_styles()
        self.build_ui()
        self.validate_codex_home()
        self.root.after(100, self.drain_output_queue)
        self.root.after(200, self.startup_preflight)

    def configure_styles(self) -> None:
        style = ttk.Style()
        style.configure(".", font=(FONT_FAMILY, 10))
        style.configure("TFrame", background=COLOR_BG)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        style.configure("TCheckbutton", background=COLOR_BG, foreground=COLOR_TEXT)
        style.configure("TRadiobutton", background=COLOR_BG, foreground=COLOR_TEXT)
        style.configure("App.TFrame", background=COLOR_BG)
        style.configure("Sidebar.TFrame", background=COLOR_SURFACE)
        style.configure("Main.TFrame", background=COLOR_BG)
        style.configure("Panel.TFrame", background=COLOR_PANEL)
        style.configure("Card.TFrame", background=COLOR_PANEL_ALT)
        style.configure("App.TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        style.configure("Panel.TLabel", background=COLOR_PANEL, foreground=COLOR_TEXT)
        style.configure("Card.TLabel", background=COLOR_PANEL_ALT, foreground=COLOR_TEXT)
        style.configure("Muted.TLabel", background=COLOR_PANEL, foreground=COLOR_MUTED)
        style.configure("SidebarTitle.TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT, font=(FONT_FAMILY, 15, "bold"))
        style.configure("SidebarMuted.TLabel", background=COLOR_SURFACE, foreground=COLOR_MUTED, font=(FONT_FAMILY, 9))
        style.configure("NavActive.TLabel", background=COLOR_ACCENT, foreground="#ffffff", font=(FONT_FAMILY, 10, "bold"), padding=(10, 7))
        style.configure("NavMuted.TLabel", background=COLOR_SURFACE, foreground=COLOR_MUTED, padding=(10, 7))
        style.configure("NavHint.TLabel", background=COLOR_SURFACE, foreground=COLOR_MUTED, font=(FONT_FAMILY, 9), padding=(10, 6))
        style.configure("PageTitle.TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=(FONT_FAMILY, 18, "bold"))
        style.configure("PageSubtitle.TLabel", background=COLOR_BG, foreground=COLOR_MUTED)
        style.configure("MetricTitle.TLabel", background=COLOR_PANEL_ALT, foreground=COLOR_MUTED, font=(FONT_FAMILY, 9))
        style.configure("MetricValue.TLabel", background=COLOR_PANEL_ALT, foreground=COLOR_TEXT, font=(FONT_FAMILY, 13, "bold"))
        style.configure("StatusGood.TLabel", background=COLOR_PANEL_ALT, foreground=COLOR_SUCCESS, font=(FONT_FAMILY, 9, "bold"))
        style.configure("Hero.TFrame", background=COLOR_PANEL)
        style.configure("HeroTitle.TLabel", background=COLOR_PANEL, foreground=COLOR_TEXT, font=(FONT_FAMILY, 16, "bold"))
        style.configure("HeroMuted.TLabel", background=COLOR_PANEL, foreground=COLOR_MUTED)
        style.configure("HeroState.TLabel", background=COLOR_PANEL, foreground=COLOR_SUCCESS, font=(FONT_FAMILY, 10, "bold"))
        style.configure("Mode.TFrame", background=COLOR_PANEL_ALT)
        style.configure("ModeActive.TFrame", background=COLOR_ACCENT_DARK)
        style.configure("ModeActive.TLabel", background=COLOR_ACCENT_DARK, foreground="#ffffff")
        style.configure("ModeActiveMuted.TLabel", background=COLOR_ACCENT_DARK, foreground="#e5e7ff")
        style.configure("ModeTitle.TLabel", background=COLOR_PANEL_ALT, foreground=COLOR_TEXT, font=(FONT_FAMILY, 11, "bold"))
        style.configure("ModeMuted.TLabel", background=COLOR_PANEL_ALT, foreground=COLOR_MUTED)

        # White button-style cards for mode selection (better affordance for non-technical users).
        style.configure("ModeBtn.TFrame", background=COLOR_BTN_BG)
        style.configure("ModeBtnTitle.TLabel", background=COLOR_BTN_BG, foreground=COLOR_BTN_TEXT, font=(FONT_FAMILY, 11, "bold"))
        style.configure("ModeBtnMuted.TLabel", background=COLOR_BTN_BG, foreground=COLOR_BTN_MUTED)
        style.configure("ModeBtnActive.TFrame", background=COLOR_BTN_BG)
        style.configure("ModeBtnActiveTitle.TLabel", background=COLOR_BTN_BG, foreground=COLOR_BTN_TEXT, font=(FONT_FAMILY, 11, "bold"))
        style.configure("ModeBtnActiveMuted.TLabel", background=COLOR_BTN_BG, foreground=COLOR_BTN_MUTED)
        style.configure("Section.TLabel", background=COLOR_BG, foreground=COLOR_MUTED, font=(FONT_FAMILY, 10, "bold"))
        style.configure("TLabelframe", background=COLOR_BG, bordercolor=COLOR_BORDER)
        style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_MUTED, font=(FONT_FAMILY, 10, "bold"))
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        # Keep tab label color stable (selected/unselected) to avoid white-on-white on Windows themes.
        style.configure("TNotebook.Tab", padding=(16, 8), font=(FONT_FAMILY, 10), foreground=COLOR_BTN_TEXT)
        style.map("TNotebook.Tab", foreground=[("selected", COLOR_BTN_TEXT), ("!selected", COLOR_BTN_TEXT)])
        style.configure("Treeview", background=COLOR_PANEL, fieldbackground=COLOR_PANEL, foreground=COLOR_TEXT, rowheight=26)
        style.configure("Treeview.Heading", font=(FONT_FAMILY, 10, "bold"))

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
        self.root.columnconfigure(0, minsize=220)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self.root, padding=(16, 18), style="Sidebar.TFrame")
        sidebar.configure(width=220)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.columnconfigure(0, weight=1)
        sidebar.grid_propagate(False)

        title = ttk.Label(sidebar, text=APP_TITLE, style="SidebarTitle.TLabel")
        title.grid(row=0, column=0, sticky="w")
        ttk.Label(sidebar, text=APP_SUBTITLE, style="SidebarMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 20))

        self._nav_labels = {}
        self._tool_nav_labels = {}

        login_label = ttk.Label(sidebar, text="登录选择")
        login_label.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        try:
            login_label.configure(cursor="hand2")
        except Exception:
            pass
        login_label.bind("<Button-1>", lambda _e: self.select_module(MODULE_LOGIN), add=True)
        self._nav_labels[MODULE_LOGIN] = login_label

        tools_toggle = ttk.Label(sidebar, textvariable=self.tools_toggle_label_var)
        tools_toggle.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        try:
            tools_toggle.configure(cursor="hand2")
        except Exception:
            pass
        tools_toggle.bind("<Button-1>", lambda _e: self.toggle_tools_section(), add=True)

        restore_label = ttk.Label(sidebar, text="信息恢复")
        restore_label.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        try:
            restore_label.configure(cursor="hand2")
        except Exception:
            pass
        restore_label.bind("<Button-1>", lambda _e: self.select_module(MODULE_RESTORE), add=True)
        self._nav_labels[MODULE_RESTORE] = restore_label
        self._tool_nav_labels[MODULE_RESTORE] = restore_label

        cleanup_label = ttk.Label(sidebar, text="系统清理")
        cleanup_label.grid(row=5, column=0, sticky="ew", pady=(0, 4))
        try:
            cleanup_label.configure(cursor="hand2")
        except Exception:
            pass
        cleanup_label.bind("<Button-1>", lambda _e: self.select_module(MODULE_CLEANUP), add=True)
        self._nav_labels[MODULE_CLEANUP] = cleanup_label
        self._tool_nav_labels[MODULE_CLEANUP] = cleanup_label

        ttk.Label(sidebar, text=" ", style="SidebarMuted.TLabel").grid(row=10, column=0, sticky="ew")
        ttk.Label(sidebar, text="提示：右侧只显示当前模块", style="NavHint.TLabel").grid(row=11, column=0, sticky="ew")

        ttk.Separator(sidebar, orient="horizontal").grid(row=20, column=0, sticky="ew", pady=(18, 12))
        ttk.Label(sidebar, text="基础版", style="SidebarMuted.TLabel").grid(row=21, column=0, sticky="w")
        ttk.Label(sidebar, text="三模块分区", style="SidebarMuted.TLabel").grid(row=22, column=0, sticky="w", pady=(3, 0))
        ttk.Label(sidebar, textvariable=self.latest_report_dir_var, style="SidebarMuted.TLabel").grid(
            row=23, column=0, sticky="w", pady=(10, 0)
        )

        # Main area: notebook tabs instead of a split pane.
        # Tab 1 (Launch): always keeps the core flow visible on small windows.
        # Tab 2 (Logs): full log viewer.
        main = ttk.Frame(self.root, padding=(18, 18), style="Main.TFrame")
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        controls_host = ttk.Frame(self.notebook, style="Main.TFrame")
        controls_host.columnconfigure(0, weight=1)
        controls_host.rowconfigure(0, weight=1)
        self.notebook.add(controls_host, text="启动台")

        controls_canvas = Canvas(
            controls_host,
            bg=COLOR_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        controls_canvas.grid(row=0, column=0, sticky="nsew")
        controls_scrollbar = ttk.Scrollbar(controls_host, orient="vertical", command=controls_canvas.yview)
        controls_scrollbar.grid(row=0, column=1, sticky="ns")
        controls_canvas.configure(yscrollcommand=controls_scrollbar.set)

        controls = ttk.Frame(controls_canvas, padding=(18, 16), style="Main.TFrame")
        controls.columnconfigure(0, weight=1)
        controls_window = controls_canvas.create_window((0, 0), window=controls, anchor="nw")

        def update_controls_scrollregion(_event=None) -> None:
            controls_canvas.configure(scrollregion=controls_canvas.bbox("all"))

        def fit_controls_width(event) -> None:
            controls_canvas.itemconfigure(controls_window, width=event.width)

        controls.bind("<Configure>", update_controls_scrollregion)
        controls_canvas.bind("<Configure>", fit_controls_width)
        controls_canvas.bind_all(
            "<MouseWheel>",
            lambda event: controls_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"),
        )

        log_host = ttk.Frame(self.notebook, padding=(18, 16), style="Main.TFrame")
        log_host.columnconfigure(0, weight=1)
        log_host.rowconfigure(0, weight=1)
        self.notebook.add(log_host, text="运行日志")

        self._module_frames: dict[str, ttk.Frame] = {}

        module_login = ttk.Frame(controls, style="Main.TFrame")
        module_login.grid(row=0, column=0, sticky="ew")
        module_login.columnconfigure(0, weight=1)
        self._module_frames[MODULE_LOGIN] = module_login

        module_restore = ttk.Frame(controls, style="Main.TFrame")
        module_restore.grid(row=0, column=0, sticky="ew")
        module_restore.columnconfigure(0, weight=1)
        self._module_frames[MODULE_RESTORE] = module_restore

        module_cleanup = ttk.Frame(controls, style="Main.TFrame")
        module_cleanup.grid(row=0, column=0, sticky="ew")
        module_cleanup.columnconfigure(0, weight=1)
        self._module_frames[MODULE_CLEANUP] = module_cleanup

        # -------------------------
        # Module: 登录选择
        # -------------------------
        ttk.Label(module_login, text="登录选择", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))

        launch_frame = ttk.Frame(module_login, padding=(0, 0), style="Main.TFrame")
        launch_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for column in range(4):
            launch_frame.columnconfigure(column, weight=1)

        self._launch_mode_buttons: dict[str, tk.Button] = {}

        mode_bar = ttk.Frame(launch_frame, style="Main.TFrame")
        mode_bar.grid(row=0, column=0, columnspan=4, sticky="ew")
        mode_bar.columnconfigure(3, weight=1)

        def make_mode_button(label: str, value: str, col: int) -> None:
            btn = tk.Button(
                mode_bar,
                text=label,
                command=lambda v=value: self.set_launch_mode(v),
                bg=COLOR_BTN_BG,
                fg=COLOR_BTN_TEXT,
                activebackground=COLOR_BTN_BG,
                activeforeground=COLOR_BTN_TEXT,
                font=(FONT_FAMILY, 10, "bold"),
                relief="raised",
                bd=1,
                highlightthickness=0,
                padx=14,
                pady=10,
            )
            btn.grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 10, 0))
            self._launch_mode_buttons[value] = btn

        make_mode_button("官方账号", "official", 0)
        make_mode_button("API 供应商", "api", 1)
        make_mode_button("混合模式", "hybrid", 2)

        # Short inline description (keeps the UI compact)
        self.launch_mode_desc_var = StringVar(value="")
        ttk.Label(
            launch_frame,
            textvariable=self.launch_mode_desc_var,
            style="PageSubtitle.TLabel",
            wraplength=900,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))

        status_bar = ttk.Frame(launch_frame)
        status_bar.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.launch_mode_help_var, wraplength=900).grid(row=0, column=0, sticky="w")

        self.issue_hint_frame = ttk.LabelFrame(module_login, text="提示", padding=10)
        self.issue_hint_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.issue_hint_frame.columnconfigure(0, weight=1)
        ttk.Label(self.issue_hint_frame, textvariable=self.issue_hint_var, wraplength=900).grid(row=0, column=0, sticky="w")
        hint_actions = ttk.Frame(self.issue_hint_frame)
        hint_actions.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(hint_actions, text="去信息恢复", command=lambda: self.select_module(MODULE_RESTORE)).grid(row=0, column=0, sticky="w")
        ttk.Button(hint_actions, text="去系统清理", command=lambda: self.select_module(MODULE_CLEANUP)).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.issue_hint_frame.grid_remove()

        self.api_frame = ttk.LabelFrame(module_login, text="Provider", padding=10)
        self.api_frame.grid(row=3, column=0, sticky="ew", pady=(10, 10))
        for column in range(4):
            self.api_frame.columnconfigure(column, weight=1)

        k_frame, k_label, self.provider_key_entry = self.add_labeled_entry(self.api_frame, 0, 0, "provider_key", self.provider_key_var)
        n_frame, n_label, self.provider_name_entry = self.add_labeled_entry(self.api_frame, 0, 1, "name", self.provider_name_var)
        b_frame, b_label, self.provider_base_url_entry = self.add_labeled_entry(self.api_frame, 0, 2, "base_url", self.provider_base_url_var)
        w_frame, w_label, self.provider_wire_api_entry = self.add_labeled_entry(self.api_frame, 0, 3, "wire_api", self.provider_wire_api_var)
        e_frame, e_label, self.provider_env_key_entry = self.add_labeled_entry(self.api_frame, 1, 0, "env_key", self.provider_env_key_var)

        self.provider_requires_auth_check = ttk.Checkbutton(
            self.api_frame,
            text="requires_openai_auth",
            variable=self.provider_requires_auth,
            command=self.refresh_launch_mode,
        )
        self.provider_requires_auth_check.grid(row=1, column=1, sticky="w", pady=(22, 0))

        token_frame, token_label, self.provider_bearer_token_entry = self.add_labeled_entry(
            self.api_frame, 1, 2, "experimental_bearer_token", self.provider_bearer_token_var
        )
        self.token_status_var = StringVar(value="")
        ttk.Label(token_frame, textvariable=self.token_status_var, foreground="#555555", wraplength=240).grid(row=2, column=0, sticky="w", pady=(2, 0))
        self.provider_bearer_token_var.trace_add("write", lambda *_: self.update_token_status())
        self.update_token_status()

        # Tooltips: what it is / where to get / when required
        ToolTip(
            k_label,
            "provider_key：内部代号（会写入 model_provider 并作为 [model_providers.<key>] 段名）。\n"
            "哪里拿：自己定，建议全小写无空格，例如 cliproxy / relay / codexzh。\n"
            "必填：API 中转 / 混合模式。",
        )
        ToolTip(
            n_label,
            "name：显示名称。\n哪里拿：自己写即可。\n必填：API 中转 / 混合模式。",
        )
        ToolTip(
            b_label,
            "base_url：请求发送到的地址（中转/供应商的 OpenAI 兼容地址）。\n"
            "哪里拿：你的中转服务地址或供应商文档/控制台给的 Endpoint。\n"
            "必填：API 中转 / 混合模式。",
        )
        ToolTip(
            w_label,
            "wire_api：协议类型。通常保持 responses。\n"
            "哪里拿：默认就是 responses，除非你的中转/供应商明确要求其它值。",
        )
        ToolTip(
            e_label,
            "env_key：API Key 环境变量名。\n"
            "哪里拿：一般是 OPENAI_API_KEY（或你自己设的环境变量名）。\n"
            "必填：仅 API 中转 且未勾 requires_openai_auth 时需要。\n"
            "可忽略：混合模式。",
        )
        ToolTip(
            token_label,
            "experimental_bearer_token：混合模式下 relay 的 bearer token。\n"
            "哪里拿：relay/中转服务控制台或你已有 token（常见 sk-... 或 cpa-...）。\n"
            "必填：仅混合模式。\n"
            "可忽略：API 中转模式。",
        )
        ToolTip(
            self.provider_requires_auth_check,
            "requires_openai_auth：表示该 provider 走官方登录态鉴权。\n"
            "混合模式必须勾选；API 中转可选（不勾时走 env_key）。",
        )

        launch_actions = ttk.Frame(module_login)
        launch_actions.grid(row=4, column=0, sticky="ew", pady=(2, 10))
        self.launch_button = ttk.Button(
            launch_actions,
            textvariable=self.launch_action_var,
            command=self.configure_and_launch_codex,
        )
        self.launch_button.grid(row=0, column=0, sticky="w", ipadx=18, ipady=8)
        ttk.Label(
            launch_actions,
            text="启动前会检查登录态、provider、threadripper 和聊天数据库归属。",
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))

        ttk.Label(controls, text="维护操作", style="Section.TLabel").grid(row=4, column=0, sticky="w", pady=(4, 6))

        # -------------------------
        # Module: 信息恢复
        # -------------------------
        ttk.Label(module_restore, text="信息恢复", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))

        repair_panel = ttk.LabelFrame(module_restore, text="聊天恢复", padding=12)
        repair_panel.grid(row=1, column=0, sticky="ew")
        repair_panel.columnconfigure(3, weight=1)

        self.search_button = ttk.Button(repair_panel, text="搜索聊天记录", command=self.search_chat_history)
        self.search_button.grid(row=0, column=0, sticky="w", ipadx=18, ipady=10, padx=(0, 8))
        self.preview_button = self.search_button

        self.quick_repair_button = ttk.Button(repair_panel, text="安全恢复聊天", command=self.run_repair)
        self.quick_repair_button.grid(row=0, column=1, sticky="w", ipadx=18, ipady=10, padx=(0, 8))

        self.advanced_button = ttk.Button(repair_panel, text="高级选项", command=self.toggle_advanced)
        self.advanced_button.grid(row=0, column=2, sticky="w", ipadx=12, ipady=10)

        ttk.Label(repair_panel, text="账号无关恢复：迁移到当前 provider，坏工作区归并到汇总目录，不重复建立空文件夹。").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )

        # -------------------------
        # Module: 系统清理
        # -------------------------
        ttk.Label(module_cleanup, text="系统清理", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))

        cleanup_panel = ttk.LabelFrame(module_cleanup, text="清理", padding=12)
        cleanup_panel.grid(row=1, column=0, sticky="ew")
        cleanup_panel.columnconfigure(4, weight=1)

        self.cleanup_button = ttk.Button(cleanup_panel, text="脏数据清理", command=self.run_cleanup_dirty_data)
        self.cleanup_button.grid(row=0, column=0, sticky="w", ipadx=12, ipady=10, padx=(0, 8))

        self.delete_archived_button = ttk.Button(cleanup_panel, text="删除归档聊天", command=self.run_delete_archived_chats)
        self.delete_archived_button.grid(row=0, column=1, sticky="w", ipadx=12, ipady=10, padx=(0, 8))

        ttk.Label(cleanup_panel, text="保留最近备份数").grid(row=0, column=2, sticky="w", padx=(6, 0))
        ttk.Entry(cleanup_panel, textvariable=self.keep_latest_backups, width=6).grid(row=0, column=3, sticky="w", padx=(8, 0))
        ttk.Label(cleanup_panel, text="仅清理本工具生成的备份目录。删除归档聊天会自动备份。").grid(
            row=1, column=0, columnspan=5, sticky="w", pady=(8, 0)
        )

        self.advanced_container = ttk.LabelFrame(module_restore, text="恢复选项", padding=10)
        self.advanced_container.grid(row=2, column=0, sticky="ew", pady=(10, 8))
        self.advanced_container.grid_remove()
        options = self.advanced_container
        for column in range(3):
            options.columnconfigure(column, weight=1)

        ttk.Label(options, text="历史汇总目录").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Entry(options, textvariable=self.history_root_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 6))

        self.add_option(options, 1, 0, "包含归档", self.include_archived, "会把已归档聊天也列入搜索/恢复结果。默认开启。")
        self.add_option(options, 1, 1, "纳入已删除工作区", self.allow_missing_cwd, "会恢复聊天，但不会重建旧目录；统一挂到历史汇总目录。")
        self.add_option(options, 1, 2, "纳入空工作区", self.allow_empty_cwd, "会恢复聊天，但不会保留空项目；统一挂到历史汇总目录。")
        self.add_option(options, 2, 0, "允许缺失 session", self.allow_missing_session, "会显示找不到会话文件的记录，可能无法打开完整内容。")
        self.add_option(options, 2, 1, "取消所选归档标记", self.unarchive_selected, "正式恢复时会把选中的归档聊天改成未归档。")
        self.add_option(options, 2, 2, "强制修复隐藏聊天识别", self.sync_provider, "默认会在检测到不匹配时自动尝试。勾选后会在恢复时强制执行一次。")
        self.add_option(options, 3, 0, "允许安装 threadripper", self.install_threadripper, "会通过 npm 安装辅助工具，需要联网。")

        advanced_actions = ttk.Frame(options)
        advanced_actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.repair_button = ttk.Button(advanced_actions, text="执行安全恢复", command=self.run_repair)
        self.repair_button.grid(row=0, column=0)

        # Launch tab: compact summary of the last few log lines.
        summary_frame = ttk.LabelFrame(module_login, text="Activity", padding=10)
        summary_frame.grid(row=5, column=0, sticky="ew", pady=(6, 8))
        summary_frame.columnconfigure(0, weight=1)
        ttk.Label(summary_frame, textvariable=self.log_summary_var, justify="left", wraplength=900).grid(row=0, column=0, sticky="ew")
        summary_actions = ttk.Frame(summary_frame)
        summary_actions.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(summary_actions, text="查看日志", command=lambda: self.notebook.select(1)).grid(row=0, column=0, sticky="w")
        ttk.Button(summary_actions, text="复制全部日志", command=self.copy_full_log).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.summary_frame = ttk.Frame(module_login)
        self.summary_frame.grid(row=6, column=0, sticky="ew", pady=(14, 10))
        for column in range(4):
            self.summary_frame.columnconfigure(column, weight=1)
        self.summary_labels: dict[str, StringVar] = {}
        self.create_summary_card(0, "登录态", "待检查", self.auth_status_var)
        self.create_summary_card(1, "模型通道", "待检查", self.channel_status_var)
        self.create_summary_card(2, "聊天归属", "待检查", self.reconcile_status_var)
        self.create_summary_card(3, "插件", "待检查", self.plugin_status_var)

        path_frame = ttk.LabelFrame(module_login, text="Workspace", padding=12)
        path_frame.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        path_frame.columnconfigure(0, weight=1)

        values = [str(path) for path in self.detected_homes]
        self.home_combo = ttk.Combobox(path_frame, textvariable=self.codex_home_var, values=values)
        self.home_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.home_combo.bind("<<ComboboxSelected>>", lambda _event: self.validate_codex_home())
        self.home_combo.bind("<FocusOut>", lambda _event: self.validate_codex_home())

        browse_button = ttk.Button(path_frame, text="更换目录", command=self.browse_codex_home)
        browse_button.grid(row=0, column=1)

        status = ttk.Label(path_frame, textvariable=self.status_var)
        status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.refresh_module_visibility()
        self.update_tools_section_visibility()

        # Logs tab: full log viewer.
        log_frame = ttk.LabelFrame(log_host, text="完整日志", padding=8)
        log_frame.grid(row=0, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = ttk.Treeview(log_frame, columns=("message",), show="headings", height=14)
        self.log.heading("message", text="输出")
        self.log.column("message", width=780, stretch=True)
        self.log.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)
        self.refresh_launch_mode()

    def create_summary_card(self, column: int, title: str, initial: str, variable: StringVar | None = None) -> None:
        frame = ttk.Frame(self.summary_frame, padding=(12, 10), style="Card.TFrame")
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        frame.columnconfigure(0, weight=1)
        value = variable or StringVar(value=initial)
        self.summary_labels[title] = value
        ttk.Label(frame, text=title, style="MetricTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, textvariable=value, style="MetricValue.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 0))

    def start_hybrid_launch(self) -> None:
        self.set_launch_mode("hybrid")
        self.configure_and_launch_codex()

    def set_launch_mode(self, mode: str) -> None:
        self.launch_mode.set(mode)
        self.refresh_launch_mode()

    def select_module(self, module_key: str) -> None:
        if module_key not in (MODULE_LOGIN, MODULE_RESTORE, MODULE_CLEANUP):
            return
        if module_key in (MODULE_RESTORE, MODULE_CLEANUP):
            self.tools_open.set(True)
            self.update_tools_section_visibility()
        self.module_var.set(module_key)
        self.refresh_module_visibility()

    def toggle_tools_section(self) -> None:
        self.tools_open.set(not bool(self.tools_open.get()))
        self.update_tools_section_visibility()

    def update_tools_section_visibility(self) -> None:
        is_open = bool(self.tools_open.get())
        self.tools_toggle_label_var.set("更多工具 ▾" if is_open else "更多工具 ▸")
        for key, label in getattr(self, "_tool_nav_labels", {}).items():
            try:
                if is_open:
                    label.grid()
                else:
                    label.grid_remove()
            except Exception:
                pass

    def refresh_module_visibility(self) -> None:
        active = self.module_var.get()
        for key, label in getattr(self, "_nav_labels", {}).items():
            try:
                label.configure(style="NavActive.TLabel" if key == active else "NavMuted.TLabel")
            except Exception:
                pass
        for key, frame in getattr(self, "_module_frames", {}).items():
            try:
                if key == active:
                    frame.grid()
                else:
                    frame.grid_remove()
            except Exception:
                pass

    def add_option(self, parent: ttk.Frame, row: int, column: int, text: str, variable: BooleanVar, help_text: str) -> None:
        frame = ttk.Frame(parent, padding=(0, 2))
        frame.grid(row=row, column=column, sticky="new", padx=(0, 12), pady=3)
        frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(frame, text=text, variable=variable).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text=help_text, wraplength=250).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def add_labeled_entry(self, parent: ttk.Frame, row: int, column: int, label: str, variable: StringVar):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="ew", padx=(0, 10), pady=4)
        frame.columnconfigure(0, weight=1)
        label_widget = ttk.Label(frame, text=label)
        label_widget.grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=1, column=0, sticky="ew")
        return frame, label_widget, entry

    def update_token_status(self) -> None:
        token = (self.provider_bearer_token_var.get() or "").strip()
        if not token:
            self.token_status_var.set("empty")
            return
        prefix = token[:4]
        self.token_status_var.set(f"set ({prefix}..., len={len(token)})")

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

    def refresh_launch_mode(self) -> None:
        mode = self.launch_mode.get()
        api_like = mode in ("api", "hybrid")

        # Highlight selected mode button.
        for value, btn in getattr(self, "_launch_mode_buttons", {}).items():
            active = value == mode
            try:
                btn.configure(
                    relief="sunken" if active else "raised",
                    bd=2 if active else 1,
                    bg=COLOR_BTN_BG,
                    fg=COLOR_BTN_TEXT,
                )
            except Exception:
                pass

        if hasattr(self, "launch_mode_desc_var"):
            if mode == "official":
                self.launch_mode_desc_var.set("官方模型通道，插件可用。")
            elif mode == "api":
                self.launch_mode_desc_var.set("请求走第三方或本地 relay，插件通常不可用。")
            else:
                self.launch_mode_desc_var.set("推荐。插件可用，同时把 model_provider 指向 relay/API 通道。")

        if api_like:
            self.api_frame.grid()
            self.set_widget_state(self.api_frame, "normal")
            if mode == "hybrid":
                # Hybrid forces openai-auth and bearer token; env_key becomes irrelevant.
                self.provider_requires_auth.set(True)
                try:
                    self.provider_requires_auth_check.configure(state="disabled")
                except Exception:
                    pass
                try:
                    self.provider_env_key_entry.configure(state="disabled")
                except Exception:
                    pass
                try:
                    self.provider_bearer_token_entry.configure(state="normal")
                except Exception:
                    pass
                self.launch_mode_help_var.set(
                    "当前入口：混合模式（插件 + 中转）。工具会写入 Relay provider（requires_openai_auth + bearer token），"
                    "并要求你已完成官方账号登录态，否则插件仍不可用。Relay Token 可用 sk-... 或 cpa-...。"
                )
                self.launch_action_var.set("使用混合模式启动 Codex（插件可用）")
            else:
                try:
                    self.provider_requires_auth_check.configure(state="normal")
                except Exception:
                    pass
                # In API mode, bearer token is ignored.
                try:
                    self.provider_bearer_token_entry.configure(state="disabled")
                except Exception:
                    pass
                # env_key is needed only when requires_openai_auth is off.
                try:
                    self.provider_env_key_entry.configure(
                        state="disabled" if self.provider_requires_auth.get() else "normal"
                    )
                except Exception:
                    pass
                self.launch_mode_help_var.set(
                    "当前入口：API 供应商登录。填写 provider 信息后，工具会按这个通道写入配置、检查聊天归属、必要时自动 reconcile，然后启动 Codex。"
                )
                self.launch_action_var.set("使用 API 供应商启动 Codex")
        else:
            self.api_frame.grid_remove()
            self.set_widget_state(self.api_frame, "disabled")
            try:
                self.provider_requires_auth_check.configure(state="normal")
            except Exception:
                pass
            self.launch_mode_help_var.set(
                "当前入口：官方账号登录。工具会先切回官方通道、检查聊天归属、必要时自动 reconcile，再启动 Codex。"
            )
            self.launch_action_var.set("使用官方账号启动 Codex")

    def set_widget_state(self, parent: ttk.Widget, state: str) -> None:
        for child in parent.winfo_children():
            try:
                child.configure(state=state)
            except Exception:
                pass
            self.set_widget_state(child, state)

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
            "--history-root",
            self.history_root_var.get(),
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

    def startup_preflight(self) -> None:
        if not self.validate_codex_home():
            return
        if self.worker and self.worker.is_alive():
            return
        self.worker = threading.Thread(
            target=self.command_worker,
            args=([["__COLLECT_PRELAUNCH_EVIDENCE__"]], "启动检查", False),
            daemon=True,
        )
        self.worker.start()

    def configure_and_launch_codex(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在运行", "已有任务正在运行，请等待完成。")
            return
        if not self.validate_codex_home():
            messagebox.showerror("目录无效", "请选择有效的 Codex 数据目录。")
            return
        if not self.prepare_codex_takeover_for_user_action("配置并启动"):
            messagebox.showwarning("请先退出 Codex", "无法自动结束残留 Codex Desktop 进程，请手动完全退出后再试。")
            return
        if self.is_codex_or_cli_running():
            messagebox.showwarning("请先退出 Codex", "切换登录模式并恢复聊天前，请先完全退出 Codex Desktop 和 codex CLI。")
            return

        # Plugin constraint: apikey auth mode typically cannot use Codex plugins.
        # We warn early so users know "API provider login" does not imply plugins will work under apikey.
        try:
            evidence = collect_prelaunch_evidence(Path(self.codex_home_var.get()))
            auth_mode = str(evidence.to_dict().get("auth_mode") or "")
        except Exception:
            auth_mode = ""
        if auth_mode.lower() == "apikey" and self.launch_mode.get() != "official":
            messagebox.showwarning(
                "插件不可用（需要官方登录）",
                "检测到当前 Codex 处于 apikey 登录模式。\n\n"
                "在 apikey 模式下，Codex 的插件功能通常不可用。\n"
                "如果你需要插件，请先用官方账号在 Codex Desktop 完成登录（切到 chatgpt 登录态），"
                "再回到工具里继续走 API 供应商/中转启动流程。",
            )
        if self.launch_mode.get() in ("api", "hybrid"):
            missing = []
            if not self.provider_key_var.get().strip():
                missing.append("provider 键")
            if not self.provider_name_var.get().strip():
                missing.append("显示名称")
            if not self.provider_base_url_var.get().strip():
                missing.append("base_url")
            if not self.provider_wire_api_var.get().strip():
                missing.append("wire_api")
            if self.launch_mode.get() == "hybrid":
                if not self.provider_bearer_token_var.get().strip():
                    missing.append("experimental_bearer_token")
            else:
                if not self.provider_requires_auth.get() and not self.provider_env_key_var.get().strip():
                    missing.append("env_key")
            if missing:
                messagebox.showerror("信息不完整", "请补全：" + "、".join(missing))
                return
            if self.launch_mode.get() == "hybrid":
                token = self.provider_bearer_token_var.get().strip()
                if token and not (token.startswith("sk-") or token.startswith("cpa-")):
                    proceed = messagebox.askyesno(
                        "Relay Token 看起来不常见",
                        "你填写的 experimental_bearer_token 不是以 sk- 或 cpa- 开头。\n"
                        "如果这是你确定可用的 relay token，可以继续。\n\n继续吗？",
                    )
                    if not proceed:
                        return

        confirmed = messagebox.askyesno(
            "确认配置并启动",
            (
                "官方账号模式会先切回官方通道；"
                if self.launch_mode.get() == "official"
                else "API 模式会先写入当前 provider 信息；"
            )
            + "然后工具会自动检查聊天归属、必要时修复隐藏聊天识别，再启动 Codex Desktop。继续吗？",
        )
        if not confirmed:
            return

        self.append_log("开始准备启动 Codex...")
        commands: list[list[str]] = [["__COLLECT_PRELAUNCH_EVIDENCE__"], ["__CONFIGURE_PROVIDER__"], ["__COLLECT_PRELAUNCH_EVIDENCE__"]]
        if self.threadripper_command():
            commands.append(["__THREADRIPPER_STATUS__"])
            commands.append(["__AUTO_THREADRIPPER_SYNC__"])
        elif self.install_threadripper.get():
            npm = shutil.which("npm")
            if npm:
                commands.append([npm, "i", "-g", "codex-threadripper"])
                commands.append(["__THREADRIPPER_STATUS__"])
                commands.append(["__AUTO_THREADRIPPER_SYNC__"])
        commands.append(self.base_repair_args(dry_run=False))
        commands.append(["__LAUNCH_CODEX__"])
        self.run_commands(commands, "配置并启动")

    def run_repair(self) -> None:
        if not self.ensure_ready("修复"):
            return
        if not self.prepare_codex_takeover_for_user_action("恢复聊天"):
            messagebox.showwarning("请先退出 Codex", "无法自动结束残留 Codex Desktop 进程，请手动完全退出后再试。")
            return
        if self.is_codex_or_cli_running():
            messagebox.showwarning("请先退出 Codex", "恢复聊天前，请先完全退出 Codex Desktop 和 codex CLI。")
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

    def run_cleanup_dirty_data(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在运行", "已有任务正在运行，请等待完成。")
            return
        if not self.validate_codex_home():
            messagebox.showerror("目录无效", "请选择有效的 Codex 数据目录。")
            return
        try:
            keep_latest = int((self.keep_latest_backups.get() or "10").strip())
        except ValueError:
            keep_latest = 10
        keep_latest = max(0, min(200, keep_latest))
        if self.is_codex_or_cli_running():
            messagebox.showwarning("请先退出 Codex", "检测到 Codex Desktop 或 codex CLI 仍在运行。请先完全退出后再清理。")
            return
        confirmed = messagebox.askyesno(
            "确认脏数据清理",
            f"将清理工具产生的旧备份目录（desktop_history_repair_backups），保留最近 {keep_latest} 份。\n\n继续吗？",
        )
        if not confirmed:
            return
        self.prepare_report_dir(kind="cleanup-dirty-data", mode="cleanup")
        self.append_log("开始脏数据清理...")
        self.run_commands([["__CLEANUP_DIRTY_DATA__", str(keep_latest)]], "脏数据清理")

    def run_delete_archived_chats(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在运行", "已有任务正在运行，请等待完成。")
            return
        if not self.validate_codex_home():
            messagebox.showerror("目录无效", "请选择有效的 Codex 数据目录。")
            return
        if self.is_codex_or_cli_running():
            messagebox.showwarning("请先退出 Codex", "检测到 Codex Desktop 或 codex CLI 仍在运行。请先完全退出后再删除归档聊天。")
            return
        preview = history_repair.preview_delete_archived_threads(Path(self.codex_home_var.get()))
        if not preview.get("ok"):
            messagebox.showerror("预览失败", str(preview.get("error") or preview))
            return
        total = int(preview.get("archived_total") or 0)
        if total <= 0:
            messagebox.showinfo("无需操作", "没有检测到归档聊天（archived=1）。")
            return
        confirmed = messagebox.askyesno(
            "危险操作：删除归档聊天",
            f"将永久删除 {total} 条归档聊天，并清理索引引用。\n"
            f"按 provider 统计：{preview.get('provider_counts')}\n\n"
            "操作前会自动创建备份。\n\n继续吗？",
        )
        if not confirmed:
            return
        token = simpledialog.askstring("二次确认", "请输入 DELETE 才会继续删除：", parent=self.root)
        if (token or "").strip() != "DELETE":
            messagebox.showinfo("已取消", "未输入 DELETE，操作已取消。")
            return
        self.prepare_report_dir(kind="delete-archived", mode="cleanup")
        self.append_log("开始删除归档聊天（将自动备份）...")
        self.run_commands([["__DELETE_ARCHIVED_THREADS__"]], "删除归档聊天")

    def is_codex_or_cli_running(self) -> bool:
        # Best-effort check on Windows. Avoids extra deps like psutil.
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Codex.exe"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                **self.subprocess_window_options(),
            )
            if "Codex.exe" in (result.stdout or ""):
                return True
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq codex.exe"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                **self.subprocess_window_options(),
            )
            if "codex.exe" in (result.stdout or ""):
                return True
        except Exception:
            pass
        return False

    def prepare_codex_takeover_for_user_action(self, action: str) -> bool:
        try:
            result = prepare_codex_takeover()
        except Exception as exc:
            self.append_log(f"{action}: Codex Desktop 接管检查失败：{exc}")
            return False

        if not bool(result.get("ok")):
            self.append_log(
                f"{action}: 无法结束残留 Codex Desktop 进程，remaining={result.get('remaining') or []}"
            )
            return False

        if not bool(result.get("skipped")):
            self.append_log(
                f"{action}: 已清理残留 Codex Desktop 进程，killed={len(result.get('killed') or [])}"
            )
        return True

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

    def run_commands(self, commands: list[list[str]], label: str, notify: bool = True) -> None:
        # Prepare a report dir for user-triggered operations that don't already have one.
        if self.current_report_dir is None:
            self.prepare_report_dir(kind=label.replace(" ", "_"), mode=self.launch_mode.get() or None)
        self.preview_button.configure(state="disabled")
        self.quick_repair_button.configure(state="disabled")
        self.repair_button.configure(state="disabled")
        self.cleanup_button.configure(state="disabled")
        self.delete_archived_button.configure(state="disabled")
        self.worker = threading.Thread(target=self.command_worker, args=(commands, label, notify), daemon=True)
        self.worker.start()

    def command_worker(self, commands: list[list[str]], label: str, notify: bool = True) -> None:
        ok = True
        error_message = ""
        latest_threadripper_status = dict(self.last_threadripper_status or {})
        try:
            for command in commands:
                if command == ["__COLLECT_PRELAUNCH_EVIDENCE__"]:
                    evidence = collect_prelaunch_evidence(Path(self.codex_home_var.get()))
                    self.output_queue.put("__PRELAUNCH_EVIDENCE__" + json.dumps(evidence.to_dict(), ensure_ascii=False))
                    continue
                if command == ["__CONFIGURE_PROVIDER__"]:
                    result = self.configure_provider_for_launch()
                    self.output_queue.put(
                        "__CONFIG_RESULT__" + json.dumps(result, ensure_ascii=False)
                    )
                    continue
                if command and command[0] == "__CLEANUP_DIRTY_DATA__":
                    try:
                        keep_latest = int(command[1]) if len(command) > 1 else 10
                    except ValueError:
                        keep_latest = 10
                    payload = history_repair.cleanup_dirty_data(Path(self.codex_home_var.get()), keep_latest=keep_latest)
                    self.output_queue.put("__MAINT_RESULT__" + json.dumps({"kind": "cleanup", "payload": payload}, ensure_ascii=False))
                    continue
                if command == ["__DELETE_ARCHIVED_THREADS__"]:
                    payload = history_repair.delete_archived_threads(Path(self.codex_home_var.get()))
                    self.output_queue.put("__MAINT_RESULT__" + json.dumps({"kind": "delete_archived", "payload": payload}, ensure_ascii=False))
                    continue
                elif command == ["__THREADRIPPER_STATUS__"]:
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
                    rows = int(latest_threadripper_status.get("rows_needing_reconcile") or 0)
                    if rows <= 0 and not self.sync_provider.get():
                        self.output_queue.put("隐藏聊天识别已经对齐，跳过自动修复。")
                        continue
                    command = [threadripper, "--codex-home", self.codex_home_var.get(), "sync"]
                elif command == ["__LAUNCH_CODEX__"]:
                    result = launch_codex_desktop()
                    if not result.get("ok"):
                        self.output_queue.put("未能自动启动 Codex Desktop：" + str(result.get("error") or "unknown error"))
                        continue
                    if result.get("method") == "exe":
                        self.output_queue.put("Codex Desktop 已启动（exe）。")
                    else:
                        self.output_queue.put("Codex Desktop 已启动（AppID）。")
                    continue
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
                    ok = False
                    error_message = f"退出码：{process.returncode}"
                    break
                if command[-1] == "status":
                    parsed = self.parse_threadripper_status(process.stdout)
                    if parsed:
                        latest_threadripper_status = parsed
                        self.last_threadripper_status = parsed
                        self.output_queue.put("__THREADRIPPER_STATUS__" + json.dumps(parsed, ensure_ascii=False))
                self.try_update_summary(process.stdout)
        except FileNotFoundError as exc:
            self.output_queue.put(f"命令不存在：{exc.filename}")
            ok = False
            error_message = f"命令不存在：{exc.filename}"
        except Exception as exc:
            self.output_queue.put(f"运行失败：{exc}")
            ok = False
            error_message = str(exc)
        finally:
            if ok:
                self.output_queue.put(f"{label}完成。")
            self.output_queue.put(
                "__TASK_RESULT__" + json.dumps(
                    {"label": label, "ok": ok, "notify": notify, "error": error_message},
                    ensure_ascii=False,
                )
            )
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

    def config_path(self) -> Path:
        return Path(self.codex_home_var.get()).expanduser() / "config.toml"

    def configure_provider_for_launch(self) -> dict[str, object]:
        if self.launch_mode.get() == "official":
            result = configure_provider_for_launch(
                Path(self.codex_home_var.get()),
                "official",
            )
        else:
            profile = ProviderProfile(
                key=self.provider_key_var.get().strip(),
                name=self.provider_name_var.get().strip(),
                base_url=self.provider_base_url_var.get().strip(),
                wire_api=self.provider_wire_api_var.get().strip(),
                env_key=self.provider_env_key_var.get().strip(),
                requires_openai_auth=self.provider_requires_auth.get(),
                experimental_bearer_token=self.provider_bearer_token_var.get().strip(),
            )
            result = configure_provider_for_launch(
                Path(self.codex_home_var.get()),
                "hybrid" if self.launch_mode.get() == "hybrid" else "api",
                profile=profile,
            )
        return {
            "config_path": result.config_path,
            "backup_path": result.backup_path,
            "mode": result.mode,
            "target_model_provider": result.target_model_provider,
            "verified_model_provider": result.verified_model_provider,
        }

    def find_codex_desktop_exe(self) -> str | None:
        return find_codex_desktop_exe()

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
        return threadripper_command()

    def parse_threadripper_status(self, text: str) -> dict[str, object]:
        return parse_threadripper_status(text)

    def drain_output_queue(self) -> None:
        try:
            while True:
                item = self.output_queue.get_nowait()
                if item == "__TASK_DONE__":
                    self.preview_button.configure(state="normal")
                    self.quick_repair_button.configure(state="normal")
                    self.repair_button.configure(state="normal")
                    self.cleanup_button.configure(state="normal")
                    self.delete_archived_button.configure(state="normal")
                    self.current_report_dir = None
                    self.current_report_meta = {}
                elif item.startswith("__TASK_RESULT__"):
                    data = json.loads(item.removeprefix("__TASK_RESULT__"))
                    self.current_report_meta["finished_at"] = datetime.now().astimezone().isoformat()
                    self.current_report_meta["status"] = "ok" if data.get("ok") else "error"
                    if data.get("error"):
                        self.current_report_meta["error"] = data.get("error")
                    self.flush_report_meta()
                    if data.get("notify"):
                        if data.get("ok"):
                            messagebox.showinfo("完成", f"{data.get('label')}已完成。")
                        else:
                            messagebox.showerror("失败", f"{data.get('label')}失败：{data.get('error') or '请查看日志'}")
                elif item.startswith("__MAINT_RESULT__"):
                    data = json.loads(item.removeprefix("__MAINT_RESULT__"))
                    kind = data.get("kind")
                    payload = data.get("payload") or {}
                    if kind == "cleanup":
                        removed = payload.get("removed")
                        kept = payload.get("kept")
                        root = payload.get("backups_root")
                        self.append_log(f"脏数据清理完成：removed={removed} kept={kept} root={root}")
                        if payload.get("errors"):
                            self.append_log(f"脏数据清理警告：{payload.get('errors')}")
                    elif kind == "delete_archived":
                        if payload.get("ok"):
                            self.append_log(f"归档聊天删除完成：deleted={payload.get('deleted')} backup_dir={payload.get('backup_dir')}")
                        else:
                            self.append_log(f"归档聊天删除失败：{payload.get('error') or payload}")
                elif item.startswith("__CONFIG_RESULT__"):
                    data = json.loads(item.removeprefix("__CONFIG_RESULT__"))
                    self.current_report_meta["provider_config"] = data
                    self.flush_report_meta()
                    self.append_log(
                        f'已写入 provider 配置：mode={data.get("mode")} target={data.get("target_model_provider")} verified={data.get("verified_model_provider")}'
                    )
                    self.append_log(f'配置文件：{data.get("config_path")}')
                    self.append_log(f'配置备份：{data.get("backup_path")}')
                elif item.startswith("__PRELAUNCH_EVIDENCE__"):
                    data = json.loads(item.removeprefix("__PRELAUNCH_EVIDENCE__"))
                    self.last_prelaunch_evidence = data
                    # Keep a small timeline of evidence snapshots.
                    timeline = self.current_report_meta.get("evidence") or []
                    if not isinstance(timeline, list):
                        timeline = []
                    timeline.append({"at": datetime.now().astimezone().isoformat(), "snapshot": data})
                    self.current_report_meta["evidence"] = timeline
                    self.flush_report_meta()
                    self.handle_prelaunch_evidence(data)
                elif item.startswith("__SUMMARY__"):
                    data = json.loads(item.removeprefix("__SUMMARY__"))
                    self.current_report_meta["restore_summary"] = data
                    self.flush_report_meta()
                    self.update_summary(data)
                elif item.startswith("__THREADRIPPER_STATUS__"):
                    data = json.loads(item.removeprefix("__THREADRIPPER_STATUS__"))
                    self.last_threadripper_status = data
                    self.current_report_meta["threadripper_status"] = data
                    self.flush_report_meta()
                    rows = int(data.get("rows_needing_reconcile") or 0)
                    target = data.get("target_provider") or "未知"
                    self.channel_status_var.set(str(target))
                    self.reconcile_status_var.set("已对齐" if rows <= 0 else f"需修复 {rows}")
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
        providers = data.get("providers") or {}
        provider_text = ", ".join(f"{key}:{value}" for key, value in providers.items()) or "未知"
        self.channel_status_var.set(provider_text)

    def handle_prelaunch_evidence(self, data: dict[str, object]) -> None:
        model_provider = data.get("config_model_provider") or "未知"
        auth_mode = data.get("auth_mode") or "未知"
        target_provider = data.get("threadripper_target_provider") or "未知"
        rows = data.get("rows_needing_reconcile")
        distribution = data.get("provider_distribution") or {}
        if isinstance(distribution, dict):
            provider_text = ", ".join(f"{key}:{value}" for key, value in distribution.items()) or "未知"
        else:
            provider_text = "未知"
        self.auth_status_var.set(str(auth_mode))
        self.channel_status_var.set(str(model_provider))
        if rows is None:
            self.reconcile_status_var.set("未检测")
        else:
            self.reconcile_status_var.set("已对齐" if int(rows) <= 0 else f"需修复 {rows}")
        if str(auth_mode).lower() == "chatgpt":
            self.plugin_status_var.set("已解锁")
        elif str(auth_mode).lower() == "apikey":
            self.plugin_status_var.set("不可用")
        else:
            self.plugin_status_var.set("未知")
        self.current_state_var.set(
            "混合模式就绪" if str(auth_mode).lower() == "chatgpt" and str(model_provider) != "openai" else "需要确认通道"
        )
        self.append_log(
            f"启动前检查：auth_mode={auth_mode}，config model_provider={model_provider}，threadripper 目标={target_provider}。"
        )
        self.append_log(f"threads provider 分布：{provider_text}")
        if rows is None:
            if not data.get("threadripper_available"):
                self.append_log("启动前检查：未检测到 codex-threadripper。")
        elif int(rows) > 0:
            self.append_log(f"启动前检查：发现 {rows} 条 provider 需要 reconcile。")

        hint_parts: list[str] = []
        if rows is not None and int(rows) > 0:
            hint_parts.append(f"检测到隐藏聊天识别需要修复：{rows} 条需要 reconcile。")
        if str(auth_mode).lower() == "apikey" and self.launch_mode.get() in ("api", "hybrid"):
            hint_parts.append("当前 auth_mode=apikey，插件可能不可用。若要插件，请先完成官方登录态。")
        hint_text = " ".join(hint_parts).strip()
        self.issue_hint_var.set(hint_text)
        try:
            if hint_text:
                self.issue_hint_frame.grid()
            else:
                self.issue_hint_frame.grid_remove()
        except Exception:
            pass

    def append_log(self, message: str) -> None:
        if not message:
            return
        self.log_buffer.append(message)
        self.append_report_log_line(message)
        for line in str(message).splitlines():
            line = line.strip("\r")
            if not line:
                continue
            self.log_summary.append(line)
        self.log_summary_var.set("\n".join(self.log_summary))
        self.log.insert("", "end", values=(message,))
        children = self.log.get_children()
        if len(children) > 1000:
            self.log.delete(children[0])
        self.log.yview_moveto(1.0)

    def copy_full_log(self) -> None:
        text = "\n".join(self.log_buffer)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            self.append_log("已复制全部日志到剪贴板。")
        except Exception as exc:
            self.append_log(f"复制失败：{exc}")

    def prepare_report_dir(self, *, kind: str, mode: str | None = None) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_mode = (mode or "unknown").replace(" ", "_")
        root = self.tool_dir / "reports"
        root.mkdir(parents=True, exist_ok=True)
        report_dir = root / f"{stamp}-{kind}-{safe_mode}"
        report_dir.mkdir(parents=True, exist_ok=True)
        self.current_report_dir = report_dir
        self.current_report_meta = {
            "started_at": datetime.now().astimezone().isoformat(),
            "kind": kind,
            "mode": mode,
            "codex_home": self.codex_home_var.get(),
        }
        self.latest_report_dir_var.set(f"报告：{report_dir}")
        self.flush_report_meta()

    def flush_report_meta(self) -> None:
        if not self.current_report_dir:
            return
        path = self.current_report_dir / "run.json"
        try:
            path.write_text(
                json.dumps(self.current_report_meta, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            # never break the UI on report write failure
            pass

    def append_report_log_line(self, message: str) -> None:
        if not self.current_report_dir:
            return
        path = self.current_report_dir / "run.log.txt"
        try:
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(message.rstrip("\n") + "\n")
        except Exception:
            pass


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

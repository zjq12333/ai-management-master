use tauri::menu::{Menu, MenuBuilder, MenuItem};
use tauri::{AppHandle, Wry};

const TRAY_ID: &str = "main";
const OPEN_MAIN_ID: &str = "tray_open_main";
const QUIT_ID: &str = "tray_quit";

pub fn create_bootstrap_tray_menu(app: &AppHandle) -> Result<Menu<Wry>, String> {
    let labels = TrayLabels::for_system_language();

    MenuBuilder::new(app)
        .item(
            &MenuItem::with_id(app, OPEN_MAIN_ID, labels.open_main, true, None::<&str>)
                .map_err(|e| e.to_string())?,
        )
        .separator()
        .item(
            &MenuItem::with_id(app, QUIT_ID, labels.quit, true, None::<&str>)
                .map_err(|e| e.to_string())?,
        )
        .build()
        .map_err(|e| e.to_string())
}

pub fn create_tray_menu(app: &AppHandle) -> Result<Menu<Wry>, String> {
    create_bootstrap_tray_menu(app)
}

pub fn refresh_tray_menu(app: &AppHandle) {
    let Ok(menu) = create_tray_menu(app) else {
        return;
    };

    if let Some(tray) = app.tray_by_id(TRAY_ID) {
        let _ = tray.set_menu(Some(menu));
    }
}

pub fn handle_tray_menu_event(app: &AppHandle, event_id: &str) {
    if event_id == OPEN_MAIN_ID {
        let _ = crate::commands::hotspot::focus_main_window(app.clone());
        return;
    }

    if event_id == QUIT_ID {
        app.exit(0);
    }
}

struct TrayLabels {
    open_main: &'static str,
    quit: &'static str,
}

impl TrayLabels {
    fn for_system_language() -> Self {
        if is_system_language_chinese() {
            Self {
                open_main: "打开 AI Strategist",
                quit: "退出",
            }
        } else {
            Self {
                open_main: "Open AI Strategist",
                quit: "Quit",
            }
        }
    }
}

fn is_system_language_chinese() -> bool {
    #[cfg(target_os = "windows")]
    {
        return windows_primary_language_id() == 0x04;
    }

    #[cfg(not(target_os = "windows"))]
    {
        std::env::var("LANGUAGE")
            .or_else(|_| std::env::var("LC_ALL"))
            .or_else(|_| std::env::var("LC_MESSAGES"))
            .or_else(|_| std::env::var("LANG"))
            .map(|locale| locale.to_ascii_lowercase().starts_with("zh"))
            .unwrap_or(false)
    }
}

#[cfg(target_os = "windows")]
fn windows_primary_language_id() -> u16 {
    use windows_sys::Win32::Globalization::GetUserDefaultUILanguage;

    // LANGID layout: low 10 bits are the primary language id. Chinese is 0x04.
    unsafe { GetUserDefaultUILanguage() & 0x03ff }
}

use tauri::Manager;

#[tauri::command]
pub fn window_control(app: tauri::AppHandle, action: String) -> Result<(), String> {
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;

    match action.as_str() {
        "minimize" => window.minimize().map_err(|error| error.to_string()),
        "toggleMaximize" => {
            if window.is_maximized().map_err(|error| error.to_string())? {
                window.unmaximize().map_err(|error| error.to_string())
            } else {
                window.maximize().map_err(|error| error.to_string())
            }
        }
        "hide" => {
            window.hide().map_err(|error| error.to_string())?;
            #[cfg(target_os = "macos")]
            crate::platform::dock::set_dock_visible(false);
            Ok(())
        }
        other => Err(format!("unsupported window action: {other}")),
    }
}

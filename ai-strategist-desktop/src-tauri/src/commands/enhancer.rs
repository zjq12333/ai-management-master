use crate::core::models::EnhancerSettingsPayload;
use crate::core::repository::Repository;
use std::sync::Mutex;
use tauri::State;

#[tauri::command]
pub fn get_enhancer_settings(
    repo: State<'_, Mutex<Repository>>,
) -> Result<EnhancerSettingsPayload, String> {
    let repo = repo.lock().map_err(|e| e.to_string())?;
    Ok(repo.get_enhancer_settings())
}

#[tauri::command]
pub fn set_chat_info_move_enabled(
    repo: State<'_, Mutex<Repository>>,
    enabled: bool,
) -> Result<EnhancerSettingsPayload, String> {
    let repo = repo.lock().map_err(|e| e.to_string())?;
    repo.set_chat_info_move_enabled(enabled)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn set_one_click_handoff_enabled(
    repo: State<'_, Mutex<Repository>>,
    enabled: bool,
) -> Result<EnhancerSettingsPayload, String> {
    let repo = repo.lock().map_err(|e| e.to_string())?;
    repo.set_one_click_handoff_enabled(enabled)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn set_hide_official_quota_notice_enabled(
    repo: State<'_, Mutex<Repository>>,
    enabled: bool,
) -> Result<EnhancerSettingsPayload, String> {
    let repo = repo.lock().map_err(|e| e.to_string())?;
    repo.set_hide_official_quota_notice_enabled(enabled)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn set_must_install_plugins_enabled(
    repo: State<'_, Mutex<Repository>>,
    enabled: bool,
) -> Result<EnhancerSettingsPayload, String> {
    let repo = repo.lock().map_err(|e| e.to_string())?;
    repo.set_must_install_plugins_enabled(enabled)
        .map_err(|e| e.to_string())
}

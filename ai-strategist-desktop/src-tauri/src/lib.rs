pub mod commands;
pub mod core;
pub mod platform;

use core::repository::Repository;
use image::ImageReader;
use platform::paths::CodexPaths;
use std::cell::RefCell;
use std::io::Cursor;
use std::io::Write;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use tauri::image::Image;
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, RunEvent};

pub fn run() {
    append_app_log("run_start");
    let shared_paths = Arc::new(CodexPaths::new());

    let single_instance_guard = match platform::single_instance::acquire(&shared_paths) {
        Ok(guard) => guard,
        Err(error) => {
            append_app_log(&format!("single_instance_exit error={error}"));
            eprintln!("[AI Strategist] another instance is already running; exiting: {error}");
            let activated = platform::single_instance::request_existing_instance_activation();
            if !activated {
                append_app_log("single_instance_activation_failed");
                eprintln!("[AI Strategist] failed to activate the running instance");
            }
            return;
        }
    };
    let single_instance_guard = Rc::new(RefCell::new(Some(single_instance_guard)));

    // NOTE: Updater plugin requires a fully-populated config in tauri.conf.json.
    // The open-source snapshot of this repo does not ship that config, so enabling
    // the updater causes a runtime panic during app bootstrap.
    // Disable updater in this clone so the UI can run for 1:1 review.

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        // .plugin(updater_plugin_updater.build())
        .manage(Mutex::new(Repository::new()))
        .setup(|app| {
            configure_main_window(app.handle());
            let repo_state: tauri::State<'_, Mutex<Repository>> = app.state();
            let hotspot_enabled = repo_state
                .lock()
                .map(|r| r.get_hotspot_enabled())
                .unwrap_or(false);
            eprintln!("[AI Strategist] startup: hotspot_enabled={hotspot_enabled}");
            commands::hotspot::register_hotspot_relayout_observers(app.handle());
            if hotspot_enabled && platform::screen::has_notch_screen() {
                if let Err(e) = commands::hotspot::create_hotspot_window(app.handle()) {
                    eprintln!("[AI Strategist] failed to create hotspot window at startup: {e}");
                }
            }

            let tray_menu = commands::tray_menu::create_bootstrap_tray_menu(app.handle())
                .map_err(|e| -> Box<dyn std::error::Error> { e.into() })?;
            let tray_icon = load_tray_template_icon()
                .map_err(|e| -> Box<dyn std::error::Error> { e.into() })?;

            TrayIconBuilder::with_id("main")
                .icon(tray_icon)
                .icon_as_template(false)
                .tooltip("AI Strategist")
                .menu(&tray_menu)
                .on_menu_event(|app, event| {
                    commands::tray_menu::handle_tray_menu_event(app, &event.id.0);
                })
                .show_menu_on_left_click(true)
                .build(app)?;

            platform::audio_feedback::restore_volume_at_startup();
            schedule_startup_main_window_reveal(app.handle());

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::mcp::load_mcp_servers,
            commands::codex_plus::codex_plus_upstream_snapshot,
            commands::mcp::upsert_mcp_server,
            commands::mcp::set_mcp_server_enabled,
            commands::mcp::remove_mcp_server,
            commands::prelaunch::prelaunch_status,
            commands::prelaunch::prelaunch_environment,
            commands::prelaunch::prelaunch_runtime_status,
            commands::prelaunch::prelaunch_stop_runtime,
            commands::prelaunch::prelaunch_launch,
            commands::prelaunch::prelaunch_enhanced_launch,
            commands::prelaunch::prelaunch_repair,
            commands::lac::lac_control_space_status,
            commands::model_gateway::model_gateway_snapshot,
            commands::model_gateway::save_model_provider,
            commands::model_gateway::delete_model_provider,
            commands::model_gateway::set_default_model_provider,
            commands::model_gateway::save_model_route,
            commands::model_gateway::delete_model_route,
            commands::model_gateway::list_upstream_models,
            commands::model_gateway::check_model_provider_health,
            commands::model_relay::model_relay_status,
            commands::model_relay::save_model_relay_config,
            commands::model_relay::start_model_relay,
            commands::model_relay::stop_model_relay,
            commands::model_relay::restart_model_relay,
            commands::model_relay::model_relay_logs,
            commands::skills::load_installed_skills,
            commands::skills::load_skill_translations,
            commands::skills::translate_skill_summaries,
            commands::skills::load_skill_backups,
            commands::skills::import_skill,
            commands::skills::remove_skill,
            commands::skills::restore_skill_backup,
            commands::skills::delete_skill_backup,
            commands::enhancer::get_enhancer_settings,
            commands::enhancer::set_chat_info_move_enabled,
            commands::enhancer::set_one_click_handoff_enabled,
            commands::enhancer::set_hide_official_quota_notice_enabled,
            commands::system::clean,
            commands::system::cleanup_desktop_history_backups,
            commands::system::rebuild_registry,
            commands::system::set_auto_switch,
            commands::system::configure_auto_switch,
            commands::system::set_api_proxy_config,
            commands::system::test_api_proxy_config,
            commands::system::detect_api_proxy_config,
            commands::system::get_usage_refresh_interval,
            commands::system::set_usage_refresh_interval,
            commands::system::run_daemon_once,
            commands::system::diagnose,
            commands::system::restart_codex,
            commands::system::graceful_restart_for_update,
            commands::system::check_update_installability,
            commands::system::load_bootstrap_state,
            commands::system::first_run_self_check,
            commands::system::export_diagnostics_bundle,
            commands::system::open_path,
            commands::system::get_system_info,
            commands::hotspot::has_notch,
            commands::hotspot::get_hotspot_enabled,
            commands::hotspot::set_hotspot_enabled,
            commands::hotspot::focus_main_window,
            commands::hotspot::hotspot_ready,
            commands::window_control::window_control,
        ])
        .build(tauri::generate_context!())
        .unwrap_or_else(|error| {
            append_app_log(&format!("build_failed error={error}"));
            panic!("error while building AI Strategist: {error}");
        });
    append_app_log("build_success");

    let activation_watcher_guard = platform::single_instance::start_activation_watcher({
        let handle = app.handle().clone();
        move || commands::hotspot::force_reveal_main_window(&handle)
    })
    .map_err(|error| {
        append_app_log(&format!("activation_watcher_failed error={error}"));
        eprintln!("[AI Strategist] failed to start single-instance activation watcher: {error}");
        error
    })
    .ok();
    let activation_watcher_guard = Rc::new(RefCell::new(activation_watcher_guard));
    let single_instance_guard_for_exit = Rc::clone(&single_instance_guard);
    let activation_watcher_guard_for_exit = Rc::clone(&activation_watcher_guard);

    app.run(move |_app_handle, event| {
        if matches!(event, RunEvent::Exit) {
            append_app_log("run_event_exit");
            append_app_log("run_event_exit_preserve_external_codex_runtime");
            let _ = activation_watcher_guard_for_exit.borrow_mut().take();
            let _ = single_instance_guard_for_exit.borrow_mut().take();
        }

        #[cfg(target_os = "macos")]
        if let RunEvent::Reopen { .. } = event {
            commands::hotspot::force_reveal_main_window(_app_handle);
        }
    });
    append_app_log("run_returned");
}

fn configure_main_window(app: &tauri::AppHandle) {
    let Some(window) = app.get_webview_window("main") else {
        append_app_log("main_window_missing");
        return;
    };
    if let Err(error) = window.set_title("AI Strategist") {
        append_app_log(&format!("main_window_set_title_failed error={error}"));
    }
    if let Err(error) = window.show() {
        append_app_log(&format!("main_window_show_failed error={error}"));
    }
    if let Err(error) = window.unminimize() {
        append_app_log(&format!("main_window_unminimize_failed error={error}"));
    }
    if let Err(error) = window.set_focus() {
        append_app_log(&format!("main_window_focus_failed error={error}"));
    }
    append_app_log("main_window_configured");
}

fn append_app_log(message: &str) {
    let Some(local_app_data) = std::env::var_os("LOCALAPPDATA") else {
        return;
    };
    let log_dir = std::path::PathBuf::from(local_app_data)
        .join("AI-Strategist")
        .join("logs");
    if std::fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    let log_path = log_dir.join("app.log");
    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
    {
        let _ = writeln!(file, "[{timestamp}] {message}");
    }
}

pub fn run_daemon_once_cli() -> Result<(), String> {
    // Open-source build: the full background daemon is not shipped.
    // Keep the CLI entrypoint to satisfy the binary's arg contract.
    Ok(())
}

fn load_tray_template_icon() -> Result<Image<'static>, String> {
    let reader = ImageReader::new(Cursor::new(include_bytes!("../../assets/app-icon.png")))
        .with_guessed_format()
        .map_err(|e| format!("failed to guess tray icon format: {e}"))?;
    let decoded = reader
        .decode()
        .map_err(|e| format!("failed to decode tray icon png: {e}"))?
        .to_rgba8();
    let (width, height) = decoded.dimensions();
    Ok(Image::new_owned(decoded.into_raw(), width, height))
}

fn schedule_startup_main_window_reveal(app: &tauri::AppHandle) {
    let handle = app.clone();
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(180));
        commands::hotspot::reveal_main_window(&handle);
    });
}

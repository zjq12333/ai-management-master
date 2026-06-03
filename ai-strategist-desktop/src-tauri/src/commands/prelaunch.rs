use super::prelaunch_bridge::{
    bridge_command, bridge_command_with_mode, bridge_command_with_recovery_options, bridge_exe_path,
    bridge_program_path, bridge_script_path, RecoveryOptions,
};
use super::prelaunch_provider::{
    provider_json_for_launch, read_model_provider_from_codex_config, reusable_hybrid_provider_key,
};
use super::model_relay::start_model_relay;
use serde_json::{json, Value};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

fn codex_home_exists(codex_home: &Path) -> bool {
    codex_home.exists() && codex_home.is_dir()
}

fn path_status(path: &Path) -> Value {
    json!({
        "path": path.display().to_string(),
        "exists": path.exists(),
    })
}

fn run_bridge_launch(
    codex_home: &str,
    mode: Option<&str>,
    provider_json: Option<&str>,
    hide_official_quota_notice: bool,
    restore_history: bool,
) -> Result<Value, String> {
    let command = bridge_command_with_mode(
        "launch",
        codex_home,
        mode,
        provider_json,
        hide_official_quota_notice,
        restore_history,
    )?;
    run_bridge_command(command)
}

fn run_bridge_enhanced_launch(codex_home: &str) -> Result<Value, String> {
    run_bridge_command(bridge_command("enhanced-launch", codex_home)?)
}

fn run_bridge_command(command: Vec<String>) -> Result<Value, String> {
    append_prelaunch_log(&format!("bridge_command_start command={}", redact_command(&command)));
    let mut process = Command::new(&command[0]);
    process.args(&command[1..]);
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        process.creation_flags(0x08000000);
    }
    for (key, value) in bridge_runtime_environment() {
        process.env(key, value);
    }

    let output = process.output().map_err(|error| {
        append_prelaunch_log(&format!("bridge_command_spawn_failed error={error}"));
        error.to_string()
    })?;
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    append_prelaunch_log(&format!(
        "bridge_command_exit status={} stdout={} stderr={}",
        output.status,
        truncate_for_log(&stdout, 4000),
        truncate_for_log(&stderr, 4000)
    ));

    if !output.status.success() {
        return Err(if !stderr.is_empty() { stderr } else { stdout });
    }

    let payload: Value = serde_json::from_slice(&output.stdout).map_err(|error| {
        append_prelaunch_log(&format!("bridge_command_parse_failed error={error}"));
        error.to_string()
    })?;
    append_prelaunch_log(&format!(
        "bridge_command_payload {}",
        truncate_for_log(&payload.to_string(), 4000)
    ));
    Ok(payload)
}

fn append_prelaunch_log(message: &str) {
    let Some(local_app_data) = std::env::var_os("LOCALAPPDATA") else {
        return;
    };
    let log_dir = PathBuf::from(local_app_data)
        .join("AI-Strategist")
        .join("logs");
    if std::fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    let log_path = log_dir.join("prelaunch-command.log");
    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = writeln!(file, "[{timestamp}] {message}");
    }
}

fn truncate_for_log(value: &str, max_chars: usize) -> String {
    let mut truncated: String = value.chars().take(max_chars).collect();
    if value.chars().count() > max_chars {
        truncated.push_str("...<truncated>");
    }
    truncated
}

fn redact_command(command: &[String]) -> String {
    command
        .iter()
        .map(|part| {
            if part.contains("api_key") || part.contains("OPENAI_API_KEY") || part.contains("experimental_bearer_token") {
                "<redacted>".to_string()
            } else {
                part.clone()
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn run_bridge_repair(
    codex_home: &str,
    include_archived: bool,
    allow_missing_cwd: bool,
    allow_empty_cwd: bool,
    allow_missing_session: bool,
    projectless_mode: Option<&str>,
    unarchive_selected: bool,
) -> Result<Value, String> {
    let command = bridge_command_with_recovery_options(
        "repair",
        codex_home,
        RecoveryOptions {
            include_archived,
            allow_missing_cwd,
            allow_empty_cwd,
            allow_missing_session,
            projectless_mode,
            unarchive_selected,
        },
    )?;
    run_bridge_command(command)
}

fn resolved_threadripper_env_value() -> Option<String> {
    resolved_threadripper_runtime().map(|runtime| runtime.path.display().to_string())
}

fn resolved_threadripper_runtime() -> Option<crate::platform::runtime_resolver::ResolvedRuntime> {
    crate::platform::runtime_resolver::resolve_helper_binary("codex-threadripper.exe")
        .or_else(|| crate::platform::runtime_resolver::resolve_helper_binary("codex-threadripper"))
}

fn hidden_command(name: &str) -> Command {
    let mut command = Command::new(name);
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command
}

fn normalize_codex_home(codex_home: &str) -> PathBuf {
    let mut expanded = codex_home.to_string();
    for (key, value) in std::env::vars() {
        expanded = expanded.replace(&format!("%{key}%"), &value);
    }
    if let Some(rest) = expanded.strip_prefix("~/") {
        if let Some(home) = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")) {
            return PathBuf::from(home).join(rest);
        }
    }
    PathBuf::from(expanded)
}

fn read_auth_mode_from_codex_home(codex_home: &Path) -> Option<String> {
    let auth_path = codex_home.join("auth.json");
    let contents = std::fs::read_to_string(auth_path).ok()?;
    let payload: Value = serde_json::from_str(&contents).ok()?;
    payload
        .get("auth_mode")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToString::to_string)
}

fn parse_threadripper_status_output(text: &str) -> (Option<String>, Option<i64>) {
    let mut target_provider = None;
    let mut rows_needing_reconcile = None;
    for line in text.lines().map(str::trim) {
        if let Some(value) = line.strip_prefix("Target provider:") {
            target_provider = Some(value.trim().to_string());
        } else if let Some(value) = line.strip_prefix("Rows needing reconcile:") {
            rows_needing_reconcile = value.trim().parse::<i64>().ok();
        }
    }
    (target_provider, rows_needing_reconcile)
}

fn run_threadripper_status_from_rust(codex_home: &Path) -> (Option<String>, Option<i64>) {
    let Some(runtime) = resolved_threadripper_runtime() else {
        return (None, None);
    };

    let mut command = Command::new(runtime.path);
    command
        .arg("--codex-home")
        .arg(codex_home)
        .arg("status");
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }

    let Ok(output) = command.output() else {
        return (None, None);
    };
    if !output.status.success() {
        return (None, None);
    }
    parse_threadripper_status_output(&String::from_utf8_lossy(&output.stdout))
}

fn parse_tasklist_processes(image_name: &str, text: &str) -> Vec<Value> {
    let mut processes = Vec::new();
    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.contains("INFO:") {
            continue;
        }
        let columns = line
            .split("\",\"")
            .map(|part| part.trim().trim_matches('"').to_string())
            .collect::<Vec<_>>();
        if columns.first().map(|value| value.to_lowercase())
            != Some(image_name.to_lowercase())
        {
            continue;
        }
        let pid = columns
            .get(1)
            .and_then(|value| value.parse::<i64>().ok())
            .map(Value::from)
            .unwrap_or(Value::Null);
        processes.push(serde_json::json!({
            "image": columns.first().cloned().unwrap_or_else(|| image_name.to_string()),
            "pid": pid,
        }));
    }
    processes
}

fn parse_cim_processes(text: &str) -> Vec<Value> {
    let mut processes = Vec::new();
    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.trim_matches('"').starts_with("Name\",\"") || line.starts_with("Name,") {
            continue;
        }
        let columns = line
            .split(',')
            .map(|part| part.trim().trim_matches('"').to_string())
            .collect::<Vec<_>>();
        let Some(image) = columns.first().filter(|value| !value.is_empty()) else {
            continue;
        };
        let pid = columns
            .get(1)
            .and_then(|value| value.parse::<i64>().ok())
            .map(Value::from)
            .unwrap_or(Value::Null);
        let exe = columns.get(2).cloned().unwrap_or_default();
        processes.push(serde_json::json!({
            "image": image,
            "pid": pid,
            "exe": exe,
        }));
    }
    processes
}

fn is_runtime_helper_process(process: &Value) -> bool {
    let image = process
        .get("image")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let exe = process
        .get("exe")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .replace("/", "\\")
        .to_lowercase();

    image.eq_ignore_ascii_case("codex.exe")
        && (exe.contains("\\app\\resources\\codex.exe")
            || exe.ends_with("\\resources\\codex.exe")
            || exe.ends_with("\\codex\\codex.exe"))
}

fn is_codex_desktop_process(process: &Value) -> bool {
    let image = process
        .get("image")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let exe = process
        .get("exe")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .replace("/", "\\")
        .to_lowercase();

    image.eq_ignore_ascii_case("Codex.exe")
        && exe.contains("\\windowsapps\\openai.codex_")
        && exe.ends_with("\\app\\codex.exe")
}

fn is_managed_codex_process(process: &Value) -> bool {
    is_runtime_helper_process(process) || is_codex_desktop_process(process)
}

fn codex_running_processes_from_rust() -> Vec<Value> {
    let mut processes = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let output = hidden_command("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" | Select-Object Name,ProcessId,ExecutablePath | ConvertTo-Csv -NoTypeInformation",
        ])
        .output();
    if let Ok(output) = output {
        if output.status.success() {
            for process in parse_cim_processes(&String::from_utf8_lossy(&output.stdout)) {
                let image = process
                    .get("image")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_lowercase();
                let pid = process.get("pid").and_then(Value::as_i64);
                if seen.insert((image, pid)) {
                    processes.push(process);
                }
            }
            return processes;
        }
    }

    for image_name in ["Codex.exe", "codex.exe"] {
        let output = hidden_command("tasklist")
            .args(["/FI", &format!("IMAGENAME eq {image_name}"), "/FO", "CSV", "/NH"])
            .output();
        let Ok(output) = output else {
            continue;
        };
        if !output.status.success() {
            continue;
        }
        for process in parse_tasklist_processes(image_name, &String::from_utf8_lossy(&output.stdout)) {
            let image = process
                .get("image")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_lowercase();
            let pid = process.get("pid").and_then(Value::as_i64);
            if seen.insert((image, pid)) {
                processes.push(process);
            }
        }
    }
    processes
}

fn prelaunch_runtime_status_payload() -> Value {
    let processes = codex_running_processes_from_rust();
    serde_json::json!({
        "ok": true,
        "codex_running": !processes.is_empty(),
        "processes": processes,
    })
}

fn taskkill_args(pid: i64) -> Vec<String> {
    vec![
        "/PID".to_string(),
        pid.to_string(),
        "/F".to_string(),
    ]
}

fn terminate_codex_processes_from_rust(timeout_seconds: f64) -> Value {
    let processes = codex_running_processes_from_rust()
        .into_iter()
        .filter(is_managed_codex_process)
        .filter(|process| process.get("pid").and_then(Value::as_i64).is_some())
        .collect::<Vec<_>>();
    let mut killed = Vec::new();
    let mut errors = Vec::new();

    for process in processes {
        let Some(pid) = process.get("pid").and_then(Value::as_i64) else {
            continue;
        };
        let output = hidden_command("taskkill").args(taskkill_args(pid)).output();
        match output {
            Ok(output) if output.status.success() => killed.push(process),
            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
                let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
                let message = if !stderr.is_empty() {
                    stderr
                } else if !stdout.is_empty() {
                    stdout
                } else {
                    format!("exit code {}", output.status)
                };
                let image = process
                    .get("image")
                    .and_then(Value::as_str)
                    .unwrap_or("Codex");
                errors.push(format!("{image} PID {pid}: {message}"));
            }
            Err(error) => {
                let image = process
                    .get("image")
                    .and_then(Value::as_str)
                    .unwrap_or("Codex");
                errors.push(format!("{image} PID {pid}: {error}"));
            }
        }
    }

    let deadline =
        std::time::Instant::now() + std::time::Duration::from_secs_f64(timeout_seconds.max(0.0));
    let mut remaining = codex_running_processes_from_rust()
        .into_iter()
        .filter(is_managed_codex_process)
        .collect::<Vec<_>>();
    while !remaining.is_empty() && std::time::Instant::now() < deadline {
        std::thread::sleep(std::time::Duration::from_millis(200));
        remaining = codex_running_processes_from_rust()
            .into_iter()
            .filter(is_managed_codex_process)
            .collect::<Vec<_>>();
    }

    serde_json::json!({
        "ok": remaining.is_empty(),
        "killed": killed,
        "remaining": remaining,
        "errors": errors,
    })
}

fn provider_distribution_from_sqlite(codex_home: &Path) -> serde_json::Map<String, Value> {
    let mut distribution = serde_json::Map::new();
    let db_path = codex_home.join("state_5.sqlite");
    if !db_path.exists() {
        return distribution;
    }
    let Ok(connection) = rusqlite::Connection::open(db_path) else {
        return distribution;
    };
    let Ok(mut statement) = connection.prepare(
        "select coalesce(model_provider, '<null>') as provider, count(*) as total \
         from threads \
         group by coalesce(model_provider, '<null>') \
         order by total desc, provider asc",
    ) else {
        return distribution;
    };
    let Ok(rows) = statement.query_map([], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
    }) else {
        return distribution;
    };
    for row in rows.flatten() {
        distribution.insert(row.0, Value::from(row.1));
    }
    distribution
}

fn prelaunch_status_payload(codex_home: &str) -> Value {
    let codex_home = normalize_codex_home(codex_home);
    let config_path = codex_home.join("config.toml");
    let config_model_provider = read_model_provider_from_codex_config(&codex_home);
    let hybrid_provider_key = reusable_hybrid_provider_key(&codex_home);
    let threadripper_available = resolved_threadripper_runtime().is_some();
    let (threadripper_target_provider, rows_needing_reconcile) =
        run_threadripper_status_from_rust(&codex_home);

    serde_json::json!({
        "ok": true,
        "evidence": {
            "config_path": config_path.display().to_string(),
            "config_model_provider": config_model_provider,
            "hybrid_provider_configured": hybrid_provider_key.is_some(),
            "hybrid_provider_key": hybrid_provider_key,
            "auth_mode": read_auth_mode_from_codex_home(&codex_home),
            "threadripper_available": threadripper_available,
            "threadripper_target_provider": threadripper_target_provider,
            "rows_needing_reconcile": rows_needing_reconcile,
            "provider_distribution": provider_distribution_from_sqlite(&codex_home),
        },
        "codexPlus": codex_plus_read_only_status(&codex_home),
    })
}

fn prelaunch_environment_payload(codex_home: &str) -> Value {
    let codex_home = normalize_codex_home(codex_home);
    let config_path = codex_home.join("config.toml");
    let auth_path = codex_home.join("auth.json");
    let state_path = codex_home.join("state_5.sqlite");
    let bridge_program = bridge_program_path();
    let bridge_script = bridge_script_path();
    let bridge_exe = bridge_exe_path();
    let runtime = prelaunch_runtime_status_payload();
    let python = crate::platform::runtime_resolver::resolve_python_runtime();
    let threadripper = resolved_threadripper_runtime();
    let codex_desktop = crate::platform::runtime_resolver::resolve_codex_desktop_exe();
    let codex_desktop_path = codex_desktop
        .as_ref()
        .map(|runtime| runtime.path.display().to_string());
    let codex_desktop_source = codex_desktop.as_ref().map(|runtime| runtime.source.as_str());
    let codex_running = runtime
        .get("codex_running")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let codex_launch_available = bridge_program.is_some() && codex_desktop.is_some();
    let config_model_provider = read_model_provider_from_codex_config(&codex_home);
    let hybrid_provider_key = reusable_hybrid_provider_key(&codex_home);
    let auth_mode = read_auth_mode_from_codex_home(&codex_home);

    let mut blockers = Vec::new();
    let mut warnings = Vec::new();

    if !codex_home_exists(&codex_home) {
        blockers.push("codex_home_missing");
    }
    if bridge_program.is_none() {
        blockers.push("prelaunch_bridge_missing");
    }
    if !codex_launch_available {
        blockers.push("codex_desktop_not_found");
    }
    if !config_path.exists() {
        warnings.push("config_missing");
    }
    if auth_mode.is_none() {
        warnings.push("auth_missing");
    }
    if threadripper.is_none() {
        warnings.push("threadripper_unavailable");
    }
    if hybrid_provider_key.is_none() {
        warnings.push("hybrid_provider_missing");
    }

    json!({
        "ok": blockers.is_empty(),
        "codexHome": path_status(&codex_home),
        "config": {
            "path": config_path.display().to_string(),
            "exists": config_path.exists(),
            "modelProvider": config_model_provider,
            "hybridProviderConfigured": hybrid_provider_key.is_some(),
            "hybridProviderKey": hybrid_provider_key,
            "authMode": auth_mode,
            "authPath": path_status(&auth_path),
            "statePath": path_status(&state_path),
        },
        "bridge": {
            "programPath": bridge_program.as_ref().map(|path| path.display().to_string()),
            "scriptPath": bridge_script.as_ref().map(|path| path.display().to_string()),
            "exePath": bridge_exe.as_ref().map(|path| path.display().to_string()),
            "usesExe": bridge_exe.is_some(),
            "available": bridge_program.is_some(),
        },
        "runtimes": {
            "python": {
                "path": python.path.display().to_string(),
                "source": python.source.as_str(),
            },
            "threadripper": threadripper.as_ref().map(|runtime| runtime.path.display().to_string()),
            "threadripperAvailable": threadripper.is_some(),
        },
        "codexDesktop": {
            "productResolvedExe": codex_desktop_path,
            "productResolvedSource": codex_desktop_source,
            "appid": null,
            "lastResortExe": null,
            "launchAvailable": codex_launch_available,
            "running": codex_running,
        },
        "runtime": runtime,
        "blockers": blockers,
        "warnings": warnings,
    })
}

fn bridge_runtime_environment() -> Vec<(&'static str, String)> {
    let mut values = Vec::new();
    let python = crate::platform::runtime_resolver::resolve_python_runtime();
    values.push((
        "AI_STRATEGIST_PYTHON_RUNTIME",
        python.path.display().to_string(),
    ));
    values.push((
        "AI_STRATEGIST_PYTHON_RUNTIME_SOURCE",
        python.source.as_str().to_string(),
    ));

    if let Some(runtime) = crate::platform::runtime_resolver::resolve_codex_cli() {
        values.push((
            "AI_STRATEGIST_CODEX_CLI",
            runtime.path.display().to_string(),
        ));
        values.push((
            "AI_STRATEGIST_CODEX_CLI_SOURCE",
            runtime.source.as_str().to_string(),
        ));
    }

    #[cfg(target_os = "windows")]
    if let Some(runtime) = crate::platform::runtime_resolver::resolve_codex_desktop_exe() {
        values.push((
            "AI_STRATEGIST_CODEX_DESKTOP",
            runtime.path.display().to_string(),
        ));
        values.push((
            "AI_STRATEGIST_CODEX_DESKTOP_SOURCE",
            runtime.source.as_str().to_string(),
        ));
    }

    if let Some(threadripper_path) = resolved_threadripper_env_value() {
        values.push(("AI_STRATEGIST_THREADRIPPER", threadripper_path));
    }

    values.push((
        "AI_STRATEGIST_REPORTS_DIR",
        crate::platform::paths::CodexPaths::new()
            .codexmate_dir
            .join("reports")
            .display()
            .to_string(),
    ));

    values
}

fn codex_plus_read_only_status(codex_home: &Path) -> Value {
    let relay = codex_plus_core::relay_config::relay_status_from_home(codex_home);
    serde_json::json!({
        "relay": relay,
        "providerSync": {
            "status": "readOnly",
            "targetProvider": read_model_provider_from_codex_config(codex_home),
        },
    })
}

#[tauri::command]
pub fn prelaunch_status(codex_home: String) -> Result<Value, String> {
    Ok(prelaunch_status_payload(&codex_home))
}

#[tauri::command]
pub fn prelaunch_environment(codex_home: String) -> Result<Value, String> {
    Ok(prelaunch_environment_payload(&codex_home))
}

#[tauri::command]
pub fn prelaunch_runtime_status() -> Result<Value, String> {
    Ok(prelaunch_runtime_status_payload())
}

#[tauri::command]
pub fn prelaunch_stop_runtime() -> Result<Value, String> {
    Ok(terminate_codex_processes_from_rust(5.0))
}

#[tauri::command]
pub fn prelaunch_launch(
    codex_home: String,
    mode: Option<String>,
    provider_json: Option<String>,
    hide_official_quota_notice: Option<bool>,
    restore_history: Option<bool>,
) -> Result<Value, String> {
    let provider_json = provider_json_for_launch(&codex_home, mode.as_deref(), provider_json.as_deref())?;
    if matches!(mode.as_deref(), Some("api" | "hybrid")) && provider_json.as_deref().is_some_and(|payload| payload.contains("ai_strategist_model_bucket")) {
        start_model_relay()?;
    }
    run_bridge_launch(
        &codex_home,
        mode.as_deref(),
        provider_json.as_deref(),
        hide_official_quota_notice.unwrap_or(false),
        restore_history.unwrap_or(false),
    )
}

#[tauri::command]
pub fn prelaunch_enhanced_launch(codex_home: String) -> Result<Value, String> {
    run_bridge_enhanced_launch(&codex_home)
}

#[tauri::command]
pub fn prelaunch_repair(
    codex_home: String,
    include_archived: Option<bool>,
    allow_missing_cwd: Option<bool>,
    allow_empty_cwd: Option<bool>,
    allow_missing_session: Option<bool>,
    projectless_mode: Option<String>,
    unarchive_selected: Option<bool>,
) -> Result<Value, String> {
    run_bridge_repair(
        &codex_home,
        include_archived.unwrap_or(false),
        allow_missing_cwd.unwrap_or(false),
        allow_empty_cwd.unwrap_or(false),
        allow_missing_session.unwrap_or(false),
        projectless_mode.as_deref(),
        unarchive_selected.unwrap_or(false),
    )
}

#[cfg(test)]
mod tests {
    use super::super::prelaunch_bridge::{
        bridge_command, bridge_command_with_mode, bridge_command_with_recovery_options,
        bridge_script_path, bundled_bridge_candidates, python_command, repo_root_from_manifest,
        RecoveryOptions,
    };
    use super::super::prelaunch_provider::{
        configure_provider_for_launch, load_provider_profile_from_config, provider_json_for_launch,
        ProviderProfile,
    };
    use super::{
        bridge_runtime_environment, resolved_threadripper_env_value,
    };
    use std::fs;
    use std::path::PathBuf;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn bridge_command_fails_clearly_when_bridge_is_missing() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        std::env::remove_var("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        let error = bridge_command("repair", r"C:\Users\test\.codex")
            .expect_err("missing bridge should fail before spawning");
        assert!(error.contains("prelaunch_bridge_missing"));
        if let Some(previous) = previous {
            std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", previous);
        }
    }

    #[test]
    fn bridge_script_path_prefers_existing_explicit_environment_override() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        let bridge = std::env::temp_dir().join(format!(
            "ai-strategist-custom-bridge-{}.py",
            std::process::id()
        ));
        fs::write(&bridge, "# test bridge").expect("write bridge");
        std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", &bridge);

        assert_eq!(bridge_script_path().as_deref(), Some(bridge.as_path()));
        fs::remove_file(&bridge).ok();

        if let Some(previous) = previous {
            std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", previous);
        } else {
            std::env::remove_var("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        }
    }

    #[test]
    fn bridge_command_runs_explicit_bridge_exe_directly() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        let bridge = std::env::temp_dir().join(format!(
            "ai-strategist-custom-bridge-{}.exe",
            std::process::id()
        ));
        fs::write(&bridge, b"test bridge").expect("write bridge");
        std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", &bridge);

        let command =
            bridge_command("repair", r"C:\Users\test\.codex").expect("bridge command");
        assert_eq!(command[0], bridge.display().to_string());
        assert_eq!(command[1], "repair");
        assert!(!command.contains(&python_command()));
        fs::remove_file(&bridge).ok();

        if let Some(previous) = previous {
            std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", previous);
        } else {
            std::env::remove_var("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        }
    }

    #[test]
    fn bridge_script_path_does_not_fall_back_to_development_repo_bridge() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        std::env::set_var(
            "AI_STRATEGIST_PRELAUNCH_BRIDGE",
            repo_root_from_manifest().join("missing_bridge.py"),
        );

        assert!(bridge_script_path().is_none());
        let error = bridge_command("repair", r"C:\Users\test\.codex")
            .expect_err("missing explicit bridge should not fall back to repo script");
        assert!(error.contains("prelaunch_bridge_missing"));

        if let Some(previous) = previous {
            std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", previous);
        } else {
            std::env::remove_var("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        }
    }

    #[test]
    fn bundled_bridge_candidates_cover_tauri_resource_layouts() {
        let candidates = bundled_bridge_candidates();
        let rendered = candidates
            .iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>()
            .join("\n");

        assert!(rendered.contains("prelaunch_bridge.py"));
        assert!(rendered.contains("resources"));
        assert!(rendered.contains("_up_"));
        assert!(rendered.contains("Resources"));
    }

    #[test]
    fn launch_command_can_forward_hide_official_quota_notice_flag() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        let bridge = std::env::temp_dir().join(format!(
            "ai-strategist-custom-bridge-{}.py",
            std::process::id()
        ));
        fs::write(&bridge, "# test bridge").expect("write bridge");
        std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", &bridge);

        let command = bridge_command_with_mode(
            "launch",
            r"C:\Users\test\.codex",
            Some("api"),
            Some(r#"{"key":"lac"}"#),
            true,
            true,
        )
        .expect("bridge command");

        assert!(command.contains(&"--hide-official-quota-notice".to_string()));
        assert!(command.contains(&"--restore-history".to_string()));
        assert!(command.contains(&"--provider-json".to_string()));
        assert!(command.contains(&r#"{"key":"lac"}"#.to_string()));
        fs::remove_file(&bridge).ok();
        if let Some(previous) = previous {
            std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", previous);
        } else {
            std::env::remove_var("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        }
    }

    #[test]
    fn repair_command_can_forward_advanced_recovery_options() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        let bridge = std::env::temp_dir().join(format!(
            "ai-strategist-custom-bridge-{}.py",
            std::process::id()
        ));
        fs::write(&bridge, "# test bridge").expect("write bridge");
        std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", &bridge);

        let command = bridge_command_with_recovery_options(
            "repair",
            r"C:\Users\test\.codex",
            RecoveryOptions {
                include_archived: true,
                allow_missing_cwd: true,
                allow_empty_cwd: true,
                allow_missing_session: true,
                projectless_mode: Some("all"),
                unarchive_selected: true,
            },
        )
        .expect("bridge command");

        assert!(command.contains(&"--include-archived".to_string()));
        assert!(command.contains(&"--allow-missing-cwd".to_string()));
        assert!(command.contains(&"--allow-empty-cwd".to_string()));
        assert!(command.contains(&"--allow-missing-session".to_string()));
        assert!(command.contains(&"--projectless-mode".to_string()));
        assert!(command.contains(&"all".to_string()));
        assert!(command.contains(&"--unarchive-selected".to_string()));
        fs::remove_file(&bridge).ok();
        if let Some(previous) = previous {
            std::env::set_var("AI_STRATEGIST_PRELAUNCH_BRIDGE", previous);
        } else {
            std::env::remove_var("AI_STRATEGIST_PRELAUNCH_BRIDGE");
        }
    }

    #[test]
    fn resolved_threadripper_env_value_uses_path_helper_when_available() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-threadripper-test-{}",
            std::process::id()
        ));
        fs::create_dir_all(&temp_root).expect("temp root");
        let helper = temp_root.join("codex-threadripper.exe");
        fs::write(&helper, b"").expect("helper file");

        let original_path = std::env::var_os("PATH");
        std::env::set_var("PATH", temp_root.as_os_str());
        let resolved = resolved_threadripper_env_value();
        match original_path {
            Some(value) => std::env::set_var("PATH", value),
            None => std::env::remove_var("PATH"),
        }
        let _ = fs::remove_file(&helper);
        let _ = fs::remove_dir_all(&temp_root);

        assert_eq!(resolved, Some(PathBuf::from(helper).display().to_string()));
    }

    #[test]
    fn bridge_environment_includes_product_reports_dir() {
        let env = bridge_runtime_environment();
        assert!(env.iter().any(|(key, value)| {
            *key == "AI_STRATEGIST_REPORTS_DIR" && value.contains("reports")
        }));
        assert!(env
            .iter()
            .any(|(key, _)| *key == "AI_STRATEGIST_PYTHON_RUNTIME"));
    }

    #[test]
    fn codex_plus_read_only_status_detects_relay_config_from_codex_home() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-codex-plus-status-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(
            temp_root.join("auth.json"),
            r#"{"auth_mode":"chatgpt","tokens":{"access_token":"token"}}"#,
        )
        .expect("auth");
        fs::write(
            temp_root.join("config.toml"),
            r#"model_provider = "CodexPlusPlus"
[model_providers.CodexPlusPlus]
name = "CodexPlusPlus"
wire_api = "responses"
requires_openai_auth = true
base_url = "https://relay.example.test/v1"
experimental_bearer_token = "sk-test"
"#,
        )
        .expect("config");

        let status = super::codex_plus_read_only_status(&temp_root);

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(status["relay"]["configured"], true);
        assert_eq!(status["relay"]["authenticated"], true);
        assert_eq!(status["providerSync"]["targetProvider"], "CodexPlusPlus");
    }

    #[test]
    fn api_launch_provider_prefers_current_non_openai_config_profile() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-provider-current-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(
            temp_root.join("config.toml"),
            r#"model_provider = "custom"

[model_providers.lac]
name = "LAC"
base_url = "https://lac.example.test/v1"
wire_api = "responses"
env_key = "LAC_KEY"

[model_providers.custom]
name = "Custom"
base_url = "https://custom.example.test/v1"
wire_api = "chat"
env_key = "CUSTOM_KEY"
"#,
        )
        .expect("config");

        let profile = load_provider_profile_from_config(&temp_root, "api")
            .expect("provider profile");

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(profile.key, "custom");
        assert_eq!(profile.name, "Custom");
        assert_eq!(profile.base_url, "https://custom.example.test/v1");
        assert_eq!(profile.wire_api, "chat");
        assert_eq!(profile.env_key, "CUSTOM_KEY");
    }

    #[test]
    fn api_launch_provider_falls_back_to_lac_when_current_is_openai() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-provider-lac-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(
            temp_root.join("config.toml"),
            r#"model_provider = "openai"

[model_providers.cliproxy]
name = "CliProxy"
base_url = "https://cliproxy.example.test/v1"
wire_api = "responses"
env_key = "CLIPROXY_KEY"

[model_providers.lac]
name = "LAC"
base_url = "https://lac.example.test/v1"
wire_api = "responses"
env_key = "LAC_KEY"
"#,
        )
        .expect("config");

        let profile = load_provider_profile_from_config(&temp_root, "api")
            .expect("provider profile");

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(profile.key, "lac");
    }

    #[test]
    fn hybrid_launch_provider_requires_openai_auth_and_bearer_token() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-provider-hybrid-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(
            temp_root.join("config.toml"),
            r#"model_provider = "lac"

[model_providers.lac]
name = "LAC"
base_url = "https://lac.example.test/v1"
wire_api = "responses"
env_key = "LAC_KEY"

[model_providers.CodexPlusPlus]
name = "CodexPlusPlus"
base_url = "https://relay.example.test/v1"
wire_api = "responses"
requires_openai_auth = true
experimental_bearer_token = "sk-test"
"#,
        )
        .expect("config");

        let profile = load_provider_profile_from_config(&temp_root, "hybrid")
            .expect("provider profile");

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(profile.key, "CodexPlusPlus");
        assert!(profile.requires_openai_auth);
        assert_eq!(profile.experimental_bearer_token, "sk-test");
    }

    #[test]
    fn configure_provider_for_api_launch_writes_backup_and_provider_block() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-provider-config-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(
            temp_root.join("config.toml"),
            r#"model_reasoning_effort = "medium"
model_provider = "openai"
"#,
        )
        .expect("config");
        let profile = ProviderProfile {
            key: "lac".to_string(),
            name: "LAC".to_string(),
            base_url: "https://lac.example.test/v1".to_string(),
            wire_api: "responses".to_string(),
            env_key: "LAC_KEY".to_string(),
            requires_openai_auth: false,
            experimental_bearer_token: "".to_string(),
        };

        let result = configure_provider_for_launch(&temp_root, "api", Some(&profile))
            .expect("configured provider");
        let updated = fs::read_to_string(temp_root.join("config.toml")).expect("updated config");

        let backup_path = result.backup_path.clone().expect("backup path");
        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(result.target_model_provider, "lac");
        assert_eq!(result.verified_model_provider, "lac");
        assert!(backup_path.contains("config.toml.backup_ai_manager_"));
        assert!(updated.contains("model_provider = \"lac\""));
        assert!(updated.contains("[model_providers.lac]"));
        assert!(updated.contains("env_key = \"LAC_KEY\""));
        assert!(updated.contains("supports_websockets = false"));
    }

    #[test]
    fn configure_provider_for_hybrid_launch_rejects_missing_bearer_token() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-provider-hybrid-reject-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(temp_root.join("config.toml"), r#"model_provider = "openai""#)
            .expect("config");
        let profile = ProviderProfile {
            key: "CodexPlusPlus".to_string(),
            name: "CodexPlusPlus".to_string(),
            base_url: "https://relay.example.test/v1".to_string(),
            wire_api: "responses".to_string(),
            env_key: "".to_string(),
            requires_openai_auth: true,
            experimental_bearer_token: "".to_string(),
        };

        let result = configure_provider_for_launch(&temp_root, "hybrid", Some(&profile));

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(
            result.expect_err("hybrid should reject missing token"),
            "Hybrid mode requires experimental_bearer_token."
        );
    }


    #[test]
    fn hybrid_launch_requires_model_bucket_instead_of_reusing_config_provider() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_MODEL_GATEWAY_CONFIG");
        std::env::set_var("AI_STRATEGIST_MODEL_GATEWAY_CONFIG", r"C:\missing\model-gateway.json");
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-enhanced-reuse-provider-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(
            temp_root.join("config.toml"),
            r#"model_provider = "codexzh"

[model_providers.codexzh]
name = "codexzh"
base_url = "https://api.codexzh.com/v1"
wire_api = "responses"
requires_openai_auth = true
experimental_bearer_token = "sk-test"
"#,
        )
        .expect("config");

        let provider_json = provider_json_for_launch(
            &temp_root.display().to_string(),
            Some("hybrid"),
            None,
        );

        let _ = fs::remove_dir_all(&temp_root);
        match previous {
            Some(value) => std::env::set_var("AI_STRATEGIST_MODEL_GATEWAY_CONFIG", value),
            None => std::env::remove_var("AI_STRATEGIST_MODEL_GATEWAY_CONFIG"),
        }
        assert_eq!(
            provider_json.expect_err("hybrid launch should not reuse old config providers"),
            "No enabled model bucket relay is configured for this launch mode."
        );
    }

    #[test]
    fn prelaunch_status_reports_reusable_manual_hybrid_provider() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-hybrid-status-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(temp_root.join("auth.json"), r#"{"auth_mode":"chatgpt"}"#)
            .expect("auth");
        fs::write(
            temp_root.join("config.toml"),
            r#"model_provider = "codexzh"

[model_providers.codexzh]
name = "codexzh"
base_url = "https://api.codexzh.com/v1"
wire_api = "responses"
requires_openai_auth = true
experimental_bearer_token = "sk-test"
"#,
        )
        .expect("config");

        let payload = super::prelaunch_status_payload(&temp_root.display().to_string());

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(payload["evidence"]["auth_mode"], "chatgpt");
        assert_eq!(payload["evidence"]["hybrid_provider_configured"], true);
        assert_eq!(payload["evidence"]["hybrid_provider_key"], "codexzh");
    }

    #[test]
    fn prelaunch_status_payload_matches_legacy_evidence_shape_without_python_bridge() {
        let temp_root = std::env::temp_dir().join(format!(
            "ai-strategist-prelaunch-status-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&temp_root);
        fs::create_dir_all(&temp_root).expect("temp root");
        fs::write(
            temp_root.join("auth.json"),
            r#"{"auth_mode":"apikey","OPENAI_API_KEY":"sk-test"}"#,
        )
        .expect("auth");
        fs::write(temp_root.join("config.toml"), r#"model_provider = "lac""#)
            .expect("config");

        let payload = super::prelaunch_status_payload(&temp_root.display().to_string());

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(payload["ok"], true);
        assert_eq!(payload["evidence"]["config_model_provider"], "lac");
        assert_eq!(payload["evidence"]["auth_mode"], "apikey");
        assert!(payload["evidence"]["config_path"]
            .as_str()
            .unwrap()
            .ends_with("config.toml"));
        assert!(payload.get("codexPlus").is_some());
        assert!(!temp_root.join("state_5.sqlite").exists());
    }

    #[test]
    fn parses_tasklist_csv_rows_for_codex_processes() {
        let processes = super::parse_tasklist_processes(
            "Codex.exe",
            "\"Codex.exe\",\"1234\",\"Console\",\"1\",\"100 K\"\r\n\
             \"Other.exe\",\"9999\",\"Console\",\"1\",\"100 K\"\r\n",
        );

        assert_eq!(processes.len(), 1);
        assert_eq!(processes[0]["image"], "Codex.exe");
        assert_eq!(processes[0]["pid"], 1234);
    }

    #[test]
    fn parses_cim_process_csv_rows_with_executable_paths() {
        let processes = super::parse_cim_processes(
            "\"Name\",\"ProcessId\",\"ExecutablePath\"\r\n\
             \"Codex.exe\",\"1234\",\"C:\\Program Files\\WindowsApps\\OpenAI.Codex\\app\\Codex.exe\"\r\n\
             \"codex.exe\",\"2345\",\"C:\\Program Files\\WindowsApps\\OpenAI.Codex\\app\\resources\\codex.exe\"\r\n",
        );

        assert_eq!(processes.len(), 2);
        assert_eq!(processes[0]["image"], "Codex.exe");
        assert_eq!(processes[0]["pid"], 1234);
        assert_eq!(processes[1]["image"], "codex.exe");
        assert_eq!(processes[1]["pid"], 2345);
        assert!(processes[1]["exe"].as_str().unwrap().ends_with("resources\\codex.exe"));
    }

    #[test]
    fn runtime_helper_filter_skips_desktop_gui_processes() {
        let gui = serde_json::json!({
            "image": "Codex.exe",
            "pid": 1234,
            "exe": "C:\\Program Files\\WindowsApps\\OpenAI.Codex\\app\\Codex.exe",
        });
        let helper = serde_json::json!({
            "image": "codex.exe",
            "pid": 2345,
            "exe": "C:\\Program Files\\WindowsApps\\OpenAI.Codex\\app\\resources\\codex.exe",
        });

        assert!(!super::is_runtime_helper_process(&gui));
        assert!(super::is_runtime_helper_process(&helper));
    }

    #[test]
    fn stop_runtime_taskkill_args_do_not_kill_process_trees() {
        assert_eq!(super::taskkill_args(1234), vec!["/PID", "1234", "/F"]);
    }
}

use serde_json::Value;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Clone, Debug, PartialEq, Eq, Deserialize, Serialize)]
struct ProviderProfile {
    key: String,
    name: String,
    base_url: String,
    wire_api: String,
    env_key: String,
    requires_openai_auth: bool,
    experimental_bearer_token: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
struct ProviderConfigResult {
    config_path: String,
    backup_path: Option<String>,
    mode: String,
    target_model_provider: String,
    verified_model_provider: String,
}

fn repo_root_from_manifest() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("repo root")
        .to_path_buf()
}

fn python_command() -> String {
    crate::platform::runtime_resolver::resolve_python_runtime()
        .path
        .display()
        .to_string()
}

fn bridge_command(subcommand: &str, codex_home: &str) -> Vec<String> {
    bridge_command_with_mode(subcommand, codex_home, None, None, false, false)
}

#[derive(Default)]
struct RecoveryOptions<'a> {
    include_archived: bool,
    allow_missing_cwd: bool,
    allow_empty_cwd: bool,
    allow_missing_session: bool,
    projectless_mode: Option<&'a str>,
    unarchive_selected: bool,
}

fn append_recovery_options(command: &mut Vec<String>, options: RecoveryOptions<'_>) {
    if options.include_archived {
        command.push("--include-archived".to_string());
    }
    if options.allow_missing_cwd {
        command.push("--allow-missing-cwd".to_string());
    }
    if options.allow_empty_cwd {
        command.push("--allow-empty-cwd".to_string());
    }
    if options.allow_missing_session {
        command.push("--allow-missing-session".to_string());
    }
    if let Some(projectless_mode) = options.projectless_mode {
        command.push("--projectless-mode".to_string());
        command.push(projectless_mode.to_string());
    }
    if options.unarchive_selected {
        command.push("--unarchive-selected".to_string());
    }
}

fn bridge_command_with_mode(
    subcommand: &str,
    codex_home: &str,
    mode: Option<&str>,
    provider_json: Option<&str>,
    hide_official_quota_notice: bool,
    restore_history: bool,
) -> Vec<String> {
    let mut command = vec![
        python_command(),
        repo_root_from_manifest()
            .join("prelaunch_bridge.py")
            .display()
            .to_string(),
        subcommand.to_string(),
        "--codex-home".to_string(),
        codex_home.to_string(),
    ];
    if let Some(mode) = mode {
        command.push("--mode".to_string());
        command.push(mode.to_string());
    }
    if let Some(provider_json) = provider_json {
        command.push("--provider-json".to_string());
        command.push(provider_json.to_string());
    }
    if hide_official_quota_notice {
        command.push("--hide-official-quota-notice".to_string());
    }
    if restore_history {
        command.push("--restore-history".to_string());
    }
    command
}

fn bridge_command_with_recovery_options(
    subcommand: &str,
    codex_home: &str,
    options: RecoveryOptions<'_>,
) -> Vec<String> {
    let mut command = bridge_command(subcommand, codex_home);
    append_recovery_options(&mut command, options);
    command
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
    );
    run_bridge_command(command)
}

fn toml_string(table: &toml::Table, key: &str) -> String {
    table
        .get(key)
        .and_then(toml::Value::as_str)
        .map(str::trim)
        .unwrap_or_default()
        .to_string()
}

fn toml_bool(table: &toml::Table, key: &str) -> bool {
    table
        .get(key)
        .and_then(toml::Value::as_bool)
        .unwrap_or(false)
}

fn read_model_provider_from_config_contents(contents: &str) -> Option<String> {
    for line in contents.lines() {
        let stripped = line.trim();
        if stripped.starts_with('#') || stripped.starts_with('[') {
            continue;
        }
        let Some((key, value)) = stripped.split_once('=') else {
            continue;
        };
        if key.trim() != "model_provider" {
            continue;
        }
        let value = value.trim().trim_matches('"').trim();
        if !value.is_empty() {
            return Some(value.to_string());
        }
    }
    None
}

fn parse_provider_profiles(raw: &str) -> Result<BTreeMap<String, ProviderProfile>, String> {
    let payload = raw
        .parse::<toml::Value>()
        .map_err(|error| format!("Failed to parse config.toml: {error}"))?;
    let mut profiles = BTreeMap::new();
    let Some(provider_tables) = payload
        .get("model_providers")
        .and_then(toml::Value::as_table)
    else {
        return Ok(profiles);
    };

    for (key, value) in provider_tables {
        let Some(table) = value.as_table() else {
            continue;
        };
        let name = toml_string(table, "name");
        let wire_api = toml_string(table, "wire_api");
        profiles.insert(
            key.to_string(),
            ProviderProfile {
                key: key.to_string(),
                name: if name.is_empty() {
                    key.to_string()
                } else {
                    name
                },
                base_url: toml_string(table, "base_url"),
                wire_api: if wire_api.is_empty() {
                    "responses".to_string()
                } else {
                    wire_api
                },
                env_key: toml_string(table, "env_key"),
                requires_openai_auth: toml_bool(table, "requires_openai_auth"),
                experimental_bearer_token: toml_string(table, "experimental_bearer_token"),
            },
        );
    }
    Ok(profiles)
}

fn push_candidate(candidates: &mut Vec<String>, key: Option<&str>) {
    let Some(key) = key.map(str::trim).filter(|key| !key.is_empty()) else {
        return;
    };
    if !candidates.iter().any(|candidate| candidate == key) {
        candidates.push(key.to_string());
    }
}

fn load_provider_profile_from_config(
    codex_home: &Path,
    mode: &str,
) -> Result<ProviderProfile, String> {
    let config_path = codex_home.join("config.toml");
    let raw = std::fs::read_to_string(&config_path)
        .map_err(|_| format!("Config file not found: {}", config_path.display()))?;
    let current_provider = read_model_provider_from_config_contents(&raw);
    let profiles = parse_provider_profiles(&raw)?;
    if profiles.is_empty() {
        return Err("No model provider profiles found in config.toml.".to_string());
    }

    let mut candidates = Vec::new();
    if current_provider
        .as_deref()
        .map(|provider| !provider.eq_ignore_ascii_case("openai"))
        .unwrap_or(false)
    {
        push_candidate(&mut candidates, current_provider.as_deref());
    }
    push_candidate(&mut candidates, Some("lac"));
    push_candidate(&mut candidates, Some("cliproxy"));
    for key in profiles.keys() {
        if !key.eq_ignore_ascii_case("openai") {
            push_candidate(&mut candidates, Some(key));
        }
    }

    if mode == "hybrid" {
        for key in &candidates {
            let Some(profile) = profiles.get(key) else {
                continue;
            };
            if profile.requires_openai_auth && !profile.experimental_bearer_token.trim().is_empty() {
                return Ok(profile.clone());
            }
        }
        return Err(
            "No hybrid-capable provider found in config.toml. Expected requires_openai_auth=true and experimental_bearer_token."
                .to_string(),
        );
    }

    for key in &candidates {
        if let Some(profile) = profiles.get(key) {
            return Ok(profile.clone());
        }
    }

    Err("No non-official provider found in config.toml for API launch mode.".to_string())
}

fn provider_json_for_launch(
    codex_home: &str,
    mode: Option<&str>,
    provider_json: Option<&str>,
) -> Result<Option<String>, String> {
    if let Some(provider_json) = provider_json.map(str::trim).filter(|value| !value.is_empty()) {
        return Ok(Some(provider_json.to_string()));
    }
    let Some(mode @ ("api" | "hybrid")) = mode else {
        return Ok(None);
    };
    let profile = load_provider_profile_from_config(&normalize_codex_home(codex_home), mode)?;
    serde_json::to_string(&profile)
        .map(Some)
        .map_err(|error| error.to_string())
}

fn reusable_hybrid_provider_key(codex_home: &Path) -> Option<String> {
    load_provider_profile_from_config(codex_home, "hybrid")
        .ok()
        .map(|profile| profile.key)
}

fn toml_quoted(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

fn upsert_model_provider(raw: &str, provider: &str) -> String {
    let provider_line = format!("model_provider = \"{}\"", toml_quoted(provider));
    let mut output = Vec::new();
    let mut replaced = false;
    let mut inserted_after_reasoning = false;
    let mut in_root = true;

    for line in raw.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') {
            in_root = false;
        }
        if in_root && trimmed.starts_with("model_provider") && trimmed.contains('=') {
            output.push(provider_line.clone());
            replaced = true;
            continue;
        }
        output.push(line.to_string());
        if !replaced
            && in_root
            && trimmed.starts_with("model_reasoning_effort")
            && trimmed.contains('=')
        {
            output.push(provider_line.clone());
            inserted_after_reasoning = true;
        }
    }

    if !replaced && !inserted_after_reasoning {
        output.insert(0, provider_line);
    }
    let mut updated = output.join("\n");
    if raw.ends_with('\n') || !updated.ends_with('\n') {
        updated.push('\n');
    }
    updated
}

fn provider_block(profile: &ProviderProfile) -> String {
    let mut lines = vec![
        format!("[model_providers.{}]", profile.key),
        format!("name = \"{}\"", toml_quoted(&profile.name)),
        format!("base_url = \"{}\"", toml_quoted(&profile.base_url)),
        format!("wire_api = \"{}\"", toml_quoted(&profile.wire_api)),
    ];
    if profile.requires_openai_auth {
        lines.push("requires_openai_auth = true".to_string());
        let token = profile.experimental_bearer_token.trim();
        if !token.is_empty() {
            lines.push(format!(
                "experimental_bearer_token = \"{}\"",
                toml_quoted(token)
            ));
        }
    } else {
        let env_key = profile.env_key.trim();
        if !env_key.is_empty() {
            lines.push(format!("env_key = \"{}\"", toml_quoted(env_key)));
        }
        lines.push("supports_websockets = false".to_string());
    }
    lines.join("\n") + "\n"
}

fn table_range(raw: &str, header: &str) -> Option<(usize, usize)> {
    let mut start = None;
    let mut offset = 0;
    for segment in raw.split_inclusive('\n') {
        let trimmed = segment.trim();
        if start.is_some() && trimmed.starts_with('[') {
            return Some((start.unwrap(), offset));
        }
        if trimmed == header {
            start = Some(offset);
        }
        offset += segment.len();
    }
    if start.is_some() {
        return Some((start.unwrap(), raw.len()));
    }
    None
}

fn upsert_provider_block(raw: &str, profile: &ProviderProfile) -> String {
    let block = provider_block(profile);
    let header = format!("[model_providers.{}]", profile.key);
    if let Some((start, end)) = table_range(raw, &header) {
        return format!("{}{}{}", &raw[..start], block, &raw[end..]);
    }

    let mut updated = raw.to_string();
    if !updated.ends_with('\n') {
        updated.push('\n');
    }
    updated.push('\n');
    updated.push_str(&block);
    updated
}

fn configure_provider_for_launch(
    codex_home: &Path,
    mode: &str,
    profile: Option<&ProviderProfile>,
) -> Result<ProviderConfigResult, String> {
    let config_path = codex_home.join("config.toml");
    let raw = std::fs::read_to_string(&config_path)
        .map_err(|_| format!("Config file not found: {}", config_path.display()))?;
    let backup_path = config_path.with_file_name(format!(
        "config.toml.backup_ai_manager_{}",
        chrono::Local::now().format("%Y%m%d-%H%M%S")
    ));
    std::fs::write(&backup_path, &raw).map_err(|error| error.to_string())?;

    let (target, updated) = match mode {
        "official" => ("openai".to_string(), upsert_model_provider(&raw, "openai")),
        "api" | "hybrid" => {
            let Some(profile) = profile else {
                return Err("Provider profile is required for API launch mode.".to_string());
            };
            if mode == "hybrid" {
                if !profile.requires_openai_auth {
                    return Err("Hybrid mode requires requires_openai_auth=true.".to_string());
                }
                if profile.experimental_bearer_token.trim().is_empty() {
                    return Err("Hybrid mode requires experimental_bearer_token.".to_string());
                }
            }
            let updated = upsert_provider_block(&upsert_model_provider(&raw, &profile.key), profile);
            (profile.key.clone(), updated)
        }
        other => return Err(format!("Unsupported launch mode: {other}")),
    };

    std::fs::write(&config_path, updated).map_err(|error| error.to_string())?;
    let verified_raw = std::fs::read_to_string(&config_path).map_err(|error| error.to_string())?;
    let verified_provider = read_model_provider_from_config_contents(&verified_raw);
    if verified_provider.as_deref() != Some(target.as_str()) {
        return Err(format!(
            "Config verification failed: expected model_provider={target}, got {verified_provider:?}"
        ));
    }

    Ok(ProviderConfigResult {
        config_path: config_path.display().to_string(),
        backup_path: Some(backup_path.display().to_string()),
        mode: mode.to_string(),
        target_model_provider: target.clone(),
        verified_model_provider: target,
    })
}

fn run_bridge_command(command: Vec<String>) -> Result<Value, String> {
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

    let output = process.output().map_err(|error| error.to_string())?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        return Err(if !stderr.is_empty() { stderr } else { stdout });
    }

    serde_json::from_slice(&output.stdout).map_err(|error| error.to_string())
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
    );
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

fn codex_running_processes_from_rust() -> Vec<Value> {
    let mut processes = Vec::new();
    let mut seen = std::collections::HashSet::new();
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
        "/T".to_string(),
        "/F".to_string(),
    ]
}

fn terminate_codex_processes_from_rust(timeout_seconds: f64) -> Value {
    let processes = codex_running_processes_from_rust()
        .into_iter()
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
    let mut remaining = codex_running_processes_from_rust();
    while !remaining.is_empty() && std::time::Instant::now() < deadline {
        std::thread::sleep(std::time::Duration::from_millis(200));
        remaining = codex_running_processes_from_rust();
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

fn read_model_provider_from_codex_config(codex_home: &Path) -> String {
    let config_path = codex_home.join("config.toml");
    let Ok(contents) = std::fs::read_to_string(config_path) else {
        return "openai".to_string();
    };

    for line in contents.lines() {
        let stripped = line.trim();
        if !stripped.starts_with("model_provider") || !stripped.contains('=') {
            continue;
        }
        let Some((_, value)) = stripped.split_once('=') else {
            continue;
        };
        let value = value.trim().trim_matches('"').trim();
        if !value.is_empty() {
            return value.to_string();
        }
    }

    "openai".to_string()
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
    run_bridge_launch(
        &codex_home,
        mode.as_deref(),
        provider_json.as_deref(),
        hide_official_quota_notice.unwrap_or(false),
        restore_history.unwrap_or(false),
    )
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
    use super::{
        bridge_command, bridge_command_with_mode, bridge_command_with_recovery_options,
        bridge_runtime_environment, python_command, resolved_threadripper_env_value, RecoveryOptions,
    };
    use std::fs;
    use std::path::PathBuf;

    #[test]
    fn legacy_bridge_command_uses_repo_root_bridge_for_mutating_subcommands() {
        let command = bridge_command("repair", r"C:\Users\test\.codex");
        assert!(!command[0].is_empty());
        assert_eq!(command[0], python_command());
        assert!(command[1].ends_with("prelaunch_bridge.py"));
        assert_eq!(command[2], "repair");
    }

    #[test]
    fn launch_command_can_forward_hide_official_quota_notice_flag() {
        let command = bridge_command_with_mode(
            "launch",
            r"C:\Users\test\.codex",
            Some("api"),
            Some(r#"{"key":"lac"}"#),
            true,
            true,
        );

        assert!(command.contains(&"--hide-official-quota-notice".to_string()));
        assert!(command.contains(&"--restore-history".to_string()));
        assert!(command.contains(&"--provider-json".to_string()));
        assert!(command.contains(&r#"{"key":"lac"}"#.to_string()));
    }

    #[test]
    fn repair_command_can_forward_advanced_recovery_options() {
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
        );

        assert!(command.contains(&"--include-archived".to_string()));
        assert!(command.contains(&"--allow-missing-cwd".to_string()));
        assert!(command.contains(&"--allow-empty-cwd".to_string()));
        assert!(command.contains(&"--allow-missing-session".to_string()));
        assert!(command.contains(&"--projectless-mode".to_string()));
        assert!(command.contains(&"all".to_string()));
        assert!(command.contains(&"--unarchive-selected".to_string()));
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

        let profile = super::load_provider_profile_from_config(&temp_root, "api")
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

        let profile = super::load_provider_profile_from_config(&temp_root, "api")
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

        let profile = super::load_provider_profile_from_config(&temp_root, "hybrid")
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
        let profile = super::ProviderProfile {
            key: "lac".to_string(),
            name: "LAC".to_string(),
            base_url: "https://lac.example.test/v1".to_string(),
            wire_api: "responses".to_string(),
            env_key: "LAC_KEY".to_string(),
            requires_openai_auth: false,
            experimental_bearer_token: "".to_string(),
        };

        let result = super::configure_provider_for_launch(&temp_root, "api", Some(&profile))
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
        let profile = super::ProviderProfile {
            key: "CodexPlusPlus".to_string(),
            name: "CodexPlusPlus".to_string(),
            base_url: "https://relay.example.test/v1".to_string(),
            wire_api: "responses".to_string(),
            env_key: "".to_string(),
            requires_openai_auth: true,
            experimental_bearer_token: "".to_string(),
        };

        let result = super::configure_provider_for_launch(&temp_root, "hybrid", Some(&profile));

        let _ = fs::remove_dir_all(&temp_root);
        assert_eq!(
            result.expect_err("hybrid should reject missing token"),
            "Hybrid mode requires experimental_bearer_token."
        );
    }


    #[test]
    fn enhanced_relay_launch_can_reuse_saved_hybrid_provider_json() {
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

        let provider_json = super::provider_json_for_launch(
            &temp_root.display().to_string(),
            Some("hybrid"),
            None,
        )
        .expect("provider json")
        .expect("provider json present");

        let _ = fs::remove_dir_all(&temp_root);
        let payload: serde_json::Value = serde_json::from_str(&provider_json).expect("json");
        assert_eq!(payload["key"], "codexzh");
        assert_eq!(payload["base_url"], "https://api.codexzh.com/v1");
        assert_eq!(payload["requires_openai_auth"], true);
        assert_eq!(payload["experimental_bearer_token"], "sk-test");
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
    fn stop_runtime_taskkill_args_match_legacy_bridge() {
        assert_eq!(
            super::taskkill_args(1234),
            vec!["/PID", "1234", "/T", "/F"]
        );
    }
}

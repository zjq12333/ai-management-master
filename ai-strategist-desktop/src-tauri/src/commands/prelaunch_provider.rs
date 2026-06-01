use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Clone, Debug, PartialEq, Eq, Deserialize, Serialize)]
pub struct ProviderProfile {
    pub key: String,
    pub name: String,
    pub base_url: String,
    pub wire_api: String,
    pub env_key: String,
    pub requires_openai_auth: bool,
    pub experimental_bearer_token: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ProviderConfigResult {
    pub config_path: String,
    pub backup_path: Option<String>,
    pub mode: String,
    pub target_model_provider: String,
    pub verified_model_provider: String,
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

pub fn read_model_provider_from_config_contents(contents: &str) -> Option<String> {
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
                name: if name.is_empty() { key.to_string() } else { name },
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
    let Some(key) = key.map(str::trim).filter(|value| !value.is_empty()) else {
        return;
    };
    if !candidates.iter().any(|candidate| candidate == key) {
        candidates.push(key.to_string());
    }
}

pub fn load_provider_profile_from_config(
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

    Err("No API provider profile found in config.toml.".to_string())
}

pub fn provider_json_for_launch(
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
    if mode == "hybrid" {
        return Ok(None);
    }
    let profile = load_provider_profile_from_config(&normalize_codex_home(codex_home), mode)?;
    serde_json::to_string(&profile)
        .map(Some)
        .map_err(|error| error.to_string())
}

pub fn reusable_hybrid_provider_key(codex_home: &Path) -> Option<String> {
    let config_path = codex_home.join("config.toml");
    let raw = std::fs::read_to_string(config_path).ok()?;
    let profiles = parse_provider_profiles(&raw).ok()?;
    profiles
        .values()
        .find(|profile| {
            profile.requires_openai_auth && !profile.experimental_bearer_token.trim().is_empty()
        })
        .map(|profile| profile.key.clone())
}

fn provider_block(profile: &ProviderProfile) -> String {
    let mut lines = vec![
        format!("[model_providers.{}]", profile.key),
        format!("name = \"{}\"", toml_quoted(&profile.name)),
        format!("base_url = \"{}\"", toml_quoted(&profile.base_url)),
        format!("wire_api = \"{}\"", toml_quoted(&profile.wire_api)),
    ];
    if !profile.env_key.trim().is_empty() {
        lines.push(format!("env_key = \"{}\"", toml_quoted(&profile.env_key)));
    }
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

fn toml_quoted(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

fn upsert_model_provider(raw: &str, target: &str) -> String {
    let provider_line = format!("model_provider = \"{}\"", toml_quoted(target));
    let mut output = Vec::new();
    let mut replaced = false;
    let mut inserted_after_reasoning = false;
    let mut in_root = true;

    for line in raw.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') {
            if !replaced && in_root && !inserted_after_reasoning {
                output.push(provider_line.clone());
                inserted_after_reasoning = true;
            }
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
    if raw.ends_with('\n') {
        updated.push('\n');
    }
    updated
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
    let header = format!("[model_providers.{}]", profile.key);
    let block = provider_block(profile);
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

pub fn configure_provider_for_launch(
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
            let profile = match profile {
                Some(profile) => profile.clone(),
                None => load_provider_profile_from_config(codex_home, mode)?,
            };
            if mode == "hybrid" {
                if !profile.requires_openai_auth {
                    return Err("Hybrid mode requires requires_openai_auth=true.".to_string());
                }
                if profile.experimental_bearer_token.trim().is_empty() {
                    return Err("Hybrid mode requires experimental_bearer_token.".to_string());
                }
            }
            let updated = upsert_provider_block(&upsert_model_provider(&raw, &profile.key), &profile);
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

pub fn read_model_provider_from_codex_config(codex_home: &Path) -> String {
    let config_path = codex_home.join("config.toml");
    let Ok(contents) = std::fs::read_to_string(config_path) else {
        return "openai".to_string();
    };

    read_model_provider_from_config_contents(&contents).unwrap_or_else(|| "openai".to_string())
}

fn normalize_codex_home(codex_home: &str) -> std::path::PathBuf {
    let mut expanded = codex_home.trim().to_string();
    if expanded.is_empty() {
        return crate::platform::paths::CodexPaths::new().codex_home;
    }
    for (key, value) in std::env::vars() {
        expanded = expanded.replace(&format!("%{key}%"), &value);
    }
    if let Some(rest) = expanded.strip_prefix("~/") {
        if let Some(home) = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")) {
            return std::path::PathBuf::from(home).join(rest);
        }
    }
    std::path::PathBuf::from(expanded)
}

#[cfg(test)]
mod tests {
    use super::*;

    static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    #[test]
    fn provider_json_for_hybrid_reuse_does_not_require_existing_token() {
        let payload = provider_json_for_launch(r"%USERPROFILE%\.codex", Some("hybrid"), None)
            .expect("hybrid reuse should not validate provider before bridge launch");

        assert_eq!(payload, None);
    }

    #[test]
    fn normalize_codex_home_expands_windows_percent_environment() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let previous = std::env::var_os("AI_STRATEGIST_TEST_HOME");
        std::env::set_var("AI_STRATEGIST_TEST_HOME", r"C:\Users\test");

        let normalized = normalize_codex_home(r"%AI_STRATEGIST_TEST_HOME%\.codex");

        if let Some(previous) = previous {
            std::env::set_var("AI_STRATEGIST_TEST_HOME", previous);
        } else {
            std::env::remove_var("AI_STRATEGIST_TEST_HOME");
        }
        assert_eq!(normalized, std::path::PathBuf::from(r"C:\Users\test\.codex"));
    }
}

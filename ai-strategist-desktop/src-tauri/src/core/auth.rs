use crate::core::models::{AuthMode, CoreError, PlanType};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "camelCase")]
pub struct AuthTokens {
    pub id_token: Option<String>,
    pub access_token: Option<String>,
    pub refresh_token: Option<String>,
    pub account_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "camelCase")]
pub struct AuthFile {
    pub auth_mode: Option<String>,
    pub openai_api_key: Option<String>,
    #[serde(default)]
    pub tokens: AuthTokens,
    pub last_refresh: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct AuthSnapshot {
    pub account_key: String,
    pub email: String,
    pub account_name: Option<String>,
    pub workspace_name: Option<String>,
    pub profile_name: Option<String>,
    pub plan: PlanType,
    pub auth_mode: AuthMode,
    pub created_at: i64,
}

#[derive(Debug, Clone)]
pub struct ApiRequestContext {
    pub api_key: String,
}

pub fn current_timestamp() -> i64 {
    chrono::Utc::now().timestamp()
}

pub fn load_auth_file(path: &Path) -> Result<AuthFile, CoreError> {
    let raw = std::fs::read_to_string(path)?;
    // Codex Desktop writes various auth.json shapes. Be tolerant.
    let v: serde_json::Value = serde_json::from_str(&raw)?;

    let auth_mode = v
        .get("auth_mode")
        .and_then(|m| m.as_str())
        .map(|s| s.to_string());

    // Some environments store API key under OPENAI_API_KEY (apikey mode).
    let openai_api_key = v
        .get("openai_api_key")
        .and_then(|k| k.as_str())
        .map(|s| s.to_string())
        .or_else(|| {
            v.get("OPENAI_API_KEY")
                .and_then(|k| k.as_str())
                .map(|s| s.to_string())
        });

    let tokens = v
        .get("tokens")
        .cloned()
        .and_then(|t| serde_json::from_value::<AuthTokens>(t).ok())
        .unwrap_or_default();

    let last_refresh = v
        .get("last_refresh")
        .and_then(|m| m.as_str())
        .map(|s| s.to_string());

    Ok(AuthFile {
        auth_mode,
        openai_api_key,
        tokens,
        last_refresh,
    })
}

fn normalize_auth_mode(value: Option<&str>) -> AuthMode {
    match value.unwrap_or("").to_ascii_lowercase().as_str() {
        "chatgpt" => AuthMode::Chatgpt,
        _ => AuthMode::Apikey,
    }
}

pub fn make_auth_snapshot(auth: &AuthFile, path: &Path) -> Result<AuthSnapshot, CoreError> {
    let auth_mode = normalize_auth_mode(auth.auth_mode.as_deref());

    // Best effort key derivation:
    // - snapshots under ~/.codex/codexmate/auth-snapshots/<key>.json
    // - otherwise derive from filename
    let stem = path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("unknown");
    let account_key = auth
        .tokens
        .account_id
        .clone()
        .unwrap_or_else(|| stem.to_string());

    // Open-source: we don't have access to proprietary account enrichment.
    // Keep values stable and non-empty.
    let email = match auth_mode {
        AuthMode::Chatgpt => "unknown@chatgpt".to_string(),
        AuthMode::Apikey => "apikey".to_string(),
    };

    Ok(AuthSnapshot {
        account_key,
        email,
        account_name: None,
        workspace_name: None,
        profile_name: None,
        plan: PlanType::Unknown,
        auth_mode,
        created_at: current_timestamp(),
    })
}

pub fn make_api_request_context(auth: &AuthFile) -> Option<ApiRequestContext> {
    auth.openai_api_key
        .as_ref()
        .map(|k| ApiRequestContext { api_key: k.clone() })
}

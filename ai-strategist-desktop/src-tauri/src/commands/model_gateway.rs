use reqwest::blocking::Client;
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ModelProviderKind {
    OpenaiCompatible,
    Responses,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelProviderConfig {
    pub id: String,
    pub name: String,
    pub kind: ModelProviderKind,
    pub base_url: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_model: Option<String>,
    #[serde(default = "default_enabled")]
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelGatewayConfig {
    #[serde(default = "default_schema_version")]
    pub schema_version: u16,
    #[serde(default)]
    pub providers: Vec<ModelProviderConfig>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_provider_id: Option<String>,
    #[serde(default)]
    pub relay: ModelRelayConfig,
    #[serde(default)]
    pub model_routes: Vec<ModelRouteConfig>,
    #[serde(default)]
    pub fallback_order: Vec<String>,
    #[serde(default)]
    pub routing_policy: ModelRoutingPolicy,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelGatewaySnapshot {
    pub schema_version: u16,
    pub providers: Vec<ModelProviderConfig>,
    pub default_provider_id: Option<String>,
    pub config_path: String,
    pub relay: ModelRelayConfig,
    pub model_routes: Vec<ModelRouteConfig>,
    pub fallback_order: Vec<String>,
    pub routing_policy: ModelRoutingPolicy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelRelayConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_relay_port")]
    pub port: u16,
    #[serde(default)]
    pub auto_start: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub management_token: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ModelRoutingPolicy {
    FirstMatchThenDefault,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelRouteConfig {
    pub id: String,
    pub model_pattern: String,
    pub provider_id: String,
    #[serde(default = "default_enabled")]
    pub enabled: bool,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelRouteSavePayload {
    pub route: ModelRouteConfig,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelProviderSavePayload {
    pub provider: ModelProviderConfig,
    #[serde(default)]
    pub make_default: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpstreamModel {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub owned_by: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpstreamModelsPayload {
    pub ok: bool,
    pub provider_id: String,
    pub endpoint: String,
    pub models: Vec<UpstreamModel>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelProviderHealthPayload {
    pub ok: bool,
    pub provider_id: String,
    pub endpoint: String,
    pub status: String,
    pub latency_ms: u128,
    pub model_count: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

fn default_enabled() -> bool {
    true
}

fn default_relay_port() -> u16 {
    17431
}

fn default_schema_version() -> u16 {
    1
}

impl Default for ModelRoutingPolicy {
    fn default() -> Self {
        Self::FirstMatchThenDefault
    }
}

impl Default for ModelRelayConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            port: default_relay_port(),
            auto_start: false,
            management_token: None,
        }
    }
}

impl Default for ModelGatewayConfig {
    fn default() -> Self {
        Self {
            schema_version: default_schema_version(),
            providers: Vec::new(),
            default_provider_id: None,
            relay: ModelRelayConfig::default(),
            model_routes: Vec::new(),
            fallback_order: Vec::new(),
            routing_policy: ModelRoutingPolicy::default(),
        }
    }
}

fn normalize_base_url(base_url: &str) -> String {
    base_url.trim().trim_end_matches('/').to_string()
}

fn upstream_models_endpoint(provider: &ModelProviderConfig) -> String {
    let base = normalize_base_url(&provider.base_url);
    if base.ends_with("/models") {
        return base;
    }
    if base.ends_with("/v1") {
        return format!("{}/models", base);
    }
    format!("{}/v1/models", base)
}

fn provider_auth_headers(provider: &ModelProviderConfig) -> Result<HeaderMap, String> {
    let mut headers = HeaderMap::new();
    if let Some(api_key) = provider
        .api_key
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
    {
        let bearer = format!("Bearer {}", api_key);
        let auth = HeaderValue::from_str(&bearer)
            .map_err(|error| format!("Invalid API key header: {}", error))?;
        headers.insert(AUTHORIZATION, auth);
    }
    Ok(headers)
}

fn upstream_error(prefix: &str, status: reqwest::StatusCode, body: &str) -> String {
    let trimmed = body.trim();
    if trimmed.is_empty() {
        return format!("{} failed with HTTP {}", prefix, status.as_u16());
    }
    let preview = trimmed.chars().take(500).collect::<String>();
    format!("{} failed with HTTP {}: {}", prefix, status.as_u16(), preview)
}

pub fn config_path() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("AI_STRATEGIST_MODEL_GATEWAY_CONFIG") {
        return Ok(PathBuf::from(path));
    }
    let base = dirs::data_dir().ok_or_else(|| "Cannot resolve system data directory".to_string())?;
    Ok(base.join("AI Strategist").join("model-gateway.json"))
}

pub fn read_config(path: &PathBuf) -> Result<ModelGatewayConfig, String> {
    if !path.exists() {
        return Ok(ModelGatewayConfig::default());
    }

    let raw = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&raw).map_err(|error| error.to_string())
}

pub fn write_config(path: &PathBuf, config: &ModelGatewayConfig) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let raw = serde_json::to_string_pretty(config).map_err(|error| error.to_string())?;
    fs::write(path, raw).map_err(|error| error.to_string())
}

fn snapshot_from(config: ModelGatewayConfig, path: &PathBuf) -> ModelGatewaySnapshot {
    ModelGatewaySnapshot {
        schema_version: config.schema_version,
        providers: config.providers,
        default_provider_id: config.default_provider_id,
        config_path: path.display().to_string(),
        relay: config.relay,
        model_routes: config.model_routes,
        fallback_order: config.fallback_order,
        routing_policy: config.routing_policy,
    }
}

fn normalize_route(mut route: ModelRouteConfig) -> Result<ModelRouteConfig, String> {
    route.id = route.id.trim().to_string();
    route.model_pattern = route.model_pattern.trim().to_string();
    route.provider_id = route.provider_id.trim().to_string();

    if route.id.is_empty() {
        route.id = format!("route-{}", route.model_pattern.replace('*', "star"));
    }
    if route.model_pattern.is_empty() {
        return Err("Model pattern is required".to_string());
    }
    if route.provider_id.is_empty() {
        return Err("Provider ID is required".to_string());
    }

    Ok(route)
}

fn normalize_provider(mut provider: ModelProviderConfig) -> Result<ModelProviderConfig, String> {
    provider.id = provider.id.trim().to_string();
    provider.name = provider.name.trim().to_string();
    provider.base_url = provider.base_url.trim().trim_end_matches('/').to_string();
    provider.api_key = provider
        .api_key
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    provider.default_model = provider
        .default_model
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());

    if provider.id.is_empty() {
        return Err("Provider ID is required".to_string());
    }
    if provider.name.is_empty() {
        provider.name = provider.id.clone();
    }
    if provider.base_url.is_empty() {
        return Err("Base URL is required".to_string());
    }
    if !(provider.base_url.starts_with("http://") || provider.base_url.starts_with("https://")) {
        return Err("Base URL must start with http:// or https://".to_string());
    }

    Ok(provider)
}

#[tauri::command]
pub fn model_gateway_snapshot() -> Result<ModelGatewaySnapshot, String> {
    let path = config_path()?;
    let config = read_config(&path)?;
    Ok(snapshot_from(config, &path))
}

#[tauri::command]
pub fn save_model_provider(payload: ModelProviderSavePayload) -> Result<ModelGatewaySnapshot, String> {
    let path = config_path()?;
    let mut config = read_config(&path)?;
    let provider = normalize_provider(payload.provider)?;

    if let Some(existing) = config.providers.iter_mut().find(|item| item.id == provider.id) {
        *existing = provider.clone();
    } else {
        config.providers.push(provider.clone());
    }

    if payload.make_default || config.default_provider_id.is_none() {
        config.default_provider_id = Some(provider.id);
    }

    write_config(&path, &config)?;
    Ok(snapshot_from(config, &path))
}

#[tauri::command]
pub fn delete_model_provider(provider_id: String) -> Result<ModelGatewaySnapshot, String> {
    let path = config_path()?;
    let mut config = read_config(&path)?;
    let provider_id = provider_id.trim().to_string();
    let before = config.providers.len();

    config.providers.retain(|provider| provider.id != provider_id);
    if config.providers.len() == before {
        return Err(format!("Provider {} was not found", provider_id));
    }

    if config.default_provider_id.as_deref() == Some(provider_id.as_str()) {
        config.default_provider_id = config.providers.first().map(|provider| provider.id.clone());
    }

    write_config(&path, &config)?;
    Ok(snapshot_from(config, &path))
}

#[tauri::command]
pub fn set_default_model_provider(provider_id: String) -> Result<ModelGatewaySnapshot, String> {
    let path = config_path()?;
    let mut config = read_config(&path)?;
    let provider_id = provider_id.trim().to_string();

    if !config.providers.iter().any(|provider| provider.id == provider_id) {
        return Err(format!("Provider {} was not found", provider_id));
    }

    config.default_provider_id = Some(provider_id);
    write_config(&path, &config)?;
    Ok(snapshot_from(config, &path))
}

#[tauri::command]
pub fn save_model_route(payload: ModelRouteSavePayload) -> Result<ModelGatewaySnapshot, String> {
    let path = config_path()?;
    let mut config = read_config(&path)?;
    let route = normalize_route(payload.route)?;

    if !config.providers.iter().any(|provider| provider.id == route.provider_id) {
        return Err(format!("Provider {} was not found", route.provider_id));
    }

    if let Some(existing) = config
        .model_routes
        .iter_mut()
        .find(|existing| existing.id == route.id)
    {
        *existing = route;
    } else {
        config.model_routes.push(route);
    }

    write_config(&path, &config)?;
    Ok(snapshot_from(config, &path))
}

#[tauri::command]
pub fn delete_model_route(route_id: String) -> Result<ModelGatewaySnapshot, String> {
    let path = config_path()?;
    let mut config = read_config(&path)?;
    let route_id = route_id.trim().to_string();
    let before = config.model_routes.len();
    config.model_routes.retain(|route| route.id != route_id);

    if config.model_routes.len() == before {
        return Err(format!("Route {} was not found", route_id));
    }

    write_config(&path, &config)?;
    Ok(snapshot_from(config, &path))
}

#[tauri::command]
pub fn list_upstream_models(provider_id: String) -> Result<UpstreamModelsPayload, String> {
    let path = config_path()?;
    let config = read_config(&path)?;
    let provider = config
        .providers
        .into_iter()
        .find(|item| item.id == provider_id)
        .ok_or_else(|| format!("Unknown provider: {provider_id}"))?;
    let endpoint = upstream_models_endpoint(&provider);
    let request = Client::builder()
        .timeout(Duration::from_secs(12))
        .build()
        .map_err(|error| error.to_string())?
        .get(&endpoint)
        .headers(provider_auth_headers(&provider)?);

    match request.send() {
        Ok(response) => {
            let status = response.status();
            let text = response.text().unwrap_or_default();
            if !status.is_success() {
                return Ok(UpstreamModelsPayload {
                    ok: false,
                    provider_id,
                    endpoint,
                    models: Vec::new(),
                    error: Some(upstream_error("List upstream models", status, &text)),
                });
            }
            let parsed: Value = serde_json::from_str(&text)
                .map_err(|error| format!("Invalid models response JSON: {}", error))?;
            let mut models = parsed
                .get("data")
                .and_then(Value::as_array)
                .or_else(|| parsed.get("models").and_then(Value::as_array))
                .or_else(|| parsed.as_array())
                .map(|items| {
                    items
                        .iter()
                        .filter_map(|item| {
                            let id = item
                                .as_str()
                                .or_else(|| item.get("id").and_then(Value::as_str))
                                .or_else(|| item.get("name").and_then(Value::as_str))?
                                .to_string();
                            let owned_by = item
                                .get("owned_by")
                                .or_else(|| item.get("ownedBy"))
                                .and_then(Value::as_str)
                                .map(ToString::to_string);
                            Some(UpstreamModel { id, owned_by })
                        })
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default();
            models.sort_by(|left, right| left.id.cmp(&right.id));
            models.dedup_by(|left, right| left.id == right.id);
            if models.is_empty() {
                return Ok(UpstreamModelsPayload {
                    ok: false,
                    provider_id,
                    endpoint,
                    models,
                    error: Some("No model ids were found in the upstream models response".to_string()),
                });
            }

            Ok(UpstreamModelsPayload {
                ok: true,
                provider_id,
                endpoint,
                models,
                error: None,
            })
        }
        Err(error) => Ok(UpstreamModelsPayload {
            ok: false,
            provider_id,
            endpoint,
            models: Vec::new(),
            error: Some(error.to_string()),
        }),
    }
}

#[tauri::command]
pub fn check_model_provider_health(provider_id: String) -> Result<ModelProviderHealthPayload, String> {
    let started = std::time::Instant::now();
    let models = list_upstream_models(provider_id)?;
    let latency_ms = started.elapsed().as_millis();

    Ok(ModelProviderHealthPayload {
        ok: models.ok,
        provider_id: models.provider_id,
        endpoint: models.endpoint,
        status: if models.ok {
            "healthy".to_string()
        } else {
            "unhealthy".to_string()
        },
        latency_ms,
        model_count: models.models.len(),
        error: models.error,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_provider_trims_and_requires_base_url() {
        let provider = normalize_provider(ModelProviderConfig {
            id: " deepseek ".to_string(),
            name: "".to_string(),
            kind: ModelProviderKind::OpenaiCompatible,
            base_url: " https://api.deepseek.com/v1/ ".to_string(),
            api_key: Some(" ".to_string()),
            default_model: Some(" deepseek-chat ".to_string()),
            enabled: true,
        })
        .unwrap();

        assert_eq!(provider.id, "deepseek");
        assert_eq!(provider.name, "deepseek");
        assert_eq!(provider.base_url, "https://api.deepseek.com/v1");
        assert_eq!(provider.api_key, None);
        assert_eq!(provider.default_model, Some("deepseek-chat".to_string()));
    }
}

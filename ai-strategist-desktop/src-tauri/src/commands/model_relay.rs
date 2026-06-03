use crate::commands::model_gateway::{
    config_path, read_config, write_config, ModelGatewayConfig, ModelProviderConfig, ModelProviderKind,
};
use reqwest::blocking::Client;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Mutex, OnceLock};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

static RELAY_STATE: OnceLock<Mutex<ModelRelayRuntimeState>> = OnceLock::new();

#[derive(Debug, Default)]
struct ModelRelayRuntimeState {
    port: Option<u16>,
    stop_requested: bool,
    logs: Vec<ModelRelayLogEntry>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelRelayStatusPayload {
    pub enabled: bool,
    pub running: bool,
    pub port: u16,
    pub base_url: String,
    pub config_path: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelRelayLogEntry {
    pub timestamp_ms: u128,
    pub method: String,
    pub path: String,
    pub provider_id: Option<String>,
    pub status: u16,
    pub latency_ms: u128,
    pub error: Option<String>,
}

#[derive(Debug, Clone, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelRelayConfigPayload {
    pub port: u16,
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub auto_start: bool,
    #[serde(default)]
    pub management_token: Option<String>,
}

#[tauri::command]
pub fn model_relay_status() -> Result<ModelRelayStatusPayload, String> {
    let path = config_path()?;
    let config = read_config(&path)?;
    Ok(status_from(&config, &path.display().to_string()))
}

#[tauri::command]
pub fn save_model_relay_config(payload: ModelRelayConfigPayload) -> Result<ModelRelayStatusPayload, String> {
    if payload.port == 0 {
        return Err("Relay port must be greater than 0".to_string());
    }

    let path = config_path()?;
    let mut config = read_config(&path)?;
    config.relay.enabled = payload.enabled;
    config.relay.port = payload.port;
    config.relay.auto_start = payload.auto_start;
    config.relay.management_token = payload
        .management_token
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    write_config(&path, &config)?;

    Ok(status_from(&config, &path.display().to_string()))
}

#[tauri::command]
pub fn start_model_relay() -> Result<ModelRelayStatusPayload, String> {
    let path = config_path()?;
    let mut config = read_config(&path)?;
    config.relay.enabled = true;
    let port = config.relay.port;

    {
        let mut state = relay_state().lock().map_err(|error| error.to_string())?;
        if state.port == Some(port) {
            write_config(&path, &config)?;
            return Ok(status_from(&config, &path.display().to_string()));
        }
        if state.port.is_some() {
            return Err("Model relay is already running on another port; restart the app to change ports".to_string());
        }
        state.port = Some(port);
        state.stop_requested = false;
    }

    let listener = TcpListener::bind(("127.0.0.1", port)).map_err(|error| {
        let mut state = relay_state().lock().ok();
        if let Some(state) = state.as_mut() {
            state.port = None;
        }
        error.to_string()
    })?;
    listener
        .set_nonblocking(true)
        .map_err(|error| error.to_string())?;

    thread::spawn(move || {
        loop {
            let should_stop = relay_state()
                .lock()
                .map(|state| state.stop_requested && state.port == Some(port))
                .unwrap_or(true);
            if should_stop {
                if let Ok(mut state) = relay_state().lock() {
                    if state.port == Some(port) {
                        state.port = None;
                        state.stop_requested = false;
                    }
                }
                break;
            }

            match listener.accept() {
                Ok((stream, _)) => {
                    thread::spawn(move || {
                        let _ = handle_stream(stream);
                    });
                }
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    thread::sleep(Duration::from_millis(50));
                }
                Err(_) => break,
            }
        }
    });

    write_config(&path, &config)?;
    Ok(status_from(&config, &path.display().to_string()))
}

#[tauri::command]
pub fn stop_model_relay() -> Result<ModelRelayStatusPayload, String> {
    let path = config_path()?;
    let mut config = read_config(&path)?;
    config.relay.enabled = false;

    let running_port = {
        let mut state = relay_state().lock().map_err(|error| error.to_string())?;
        state.stop_requested = true;
        state.port
    };
    if let Some(port) = running_port {
        let _ = TcpStream::connect(("127.0.0.1", port));
        thread::sleep(Duration::from_millis(120));
    }

    write_config(&path, &config)?;
    Ok(status_from(&config, &path.display().to_string()))
}

#[tauri::command]
pub fn restart_model_relay() -> Result<ModelRelayStatusPayload, String> {
    let _ = stop_model_relay()?;
    thread::sleep(Duration::from_millis(120));
    start_model_relay()
}

#[tauri::command]
pub fn model_relay_logs() -> Result<Vec<ModelRelayLogEntry>, String> {
    let state = relay_state().lock().map_err(|error| error.to_string())?;
    Ok(state.logs.clone())
}

fn relay_state() -> &'static Mutex<ModelRelayRuntimeState> {
    RELAY_STATE.get_or_init(|| Mutex::new(ModelRelayRuntimeState::default()))
}

fn status_from(config: &ModelGatewayConfig, config_path: &str) -> ModelRelayStatusPayload {
    let running = relay_state()
        .lock()
        .map(|state| state.port == Some(config.relay.port))
        .unwrap_or(false);

    ModelRelayStatusPayload {
        enabled: config.relay.enabled,
        running,
        port: config.relay.port,
        base_url: format!("http://127.0.0.1:{}", config.relay.port),
        config_path: config_path.to_string(),
    }
}

fn handle_stream(mut stream: TcpStream) -> Result<(), String> {
    let request = parse_request(&mut stream)?;
    let response = route_request(request);
    write_response(&mut stream, response)
}

#[derive(Debug)]
struct RelayRequest {
    method: String,
    path: String,
    headers: HashMap<String, String>,
    body: Vec<u8>,
}

#[derive(Debug)]
struct RelayResponse {
    status: u16,
    content_type: String,
    body: Vec<u8>,
}

fn parse_request(stream: &mut TcpStream) -> Result<RelayRequest, String> {
    let mut reader = BufReader::new(stream.try_clone().map_err(|error| error.to_string())?);
    let mut first_line = String::new();
    reader.read_line(&mut first_line).map_err(|error| error.to_string())?;
    let mut parts = first_line.split_whitespace();
    let method = parts.next().unwrap_or_default().to_string();
    let path = parts.next().unwrap_or_default().to_string();

    let mut headers = HashMap::new();
    loop {
        let mut line = String::new();
        reader.read_line(&mut line).map_err(|error| error.to_string())?;
        let trimmed = line.trim_end();
        if trimmed.is_empty() {
            break;
        }
        if let Some((key, value)) = trimmed.split_once(':') {
            headers.insert(key.trim().to_ascii_lowercase(), value.trim().to_string());
        }
    }

    let content_length = headers
        .get("content-length")
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(0);
    let mut body = vec![0; content_length];
    if content_length > 0 {
        reader.read_exact(&mut body).map_err(|error| error.to_string())?;
    }

    Ok(RelayRequest {
        method,
        path,
        headers,
        body,
    })
}

fn route_request(request: RelayRequest) -> RelayResponse {
    let started = Instant::now();
    let method = request.method.clone();
    let path = request.path.clone();
    let routed = route_request_inner(request);
    let (response, provider_id, error) = match routed {
        Ok((response, provider_id)) => (response, provider_id, None),
        Err(error) => (
            json_response(500, json!({ "error": { "message": error.clone() } })),
            None,
            Some(error),
        ),
    };
    push_log(ModelRelayLogEntry {
        timestamp_ms: SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or(0),
        method,
        path,
        provider_id,
        status: response.status,
        latency_ms: started.elapsed().as_millis(),
        error,
    });
    response
}

fn route_request_inner(request: RelayRequest) -> Result<(RelayResponse, Option<String>), String> {
    let path = config_path()?;
    let config = read_config(&path)?;
    if request.method == "GET" && request.path == "/health" {
        return Ok((json_response(200, json!({ "ok": true })), None));
    }

    authorize_request(&config, &request)?;
    let requested_model = extract_model(&request.body);
    let provider = provider_for_request(&config, requested_model.as_deref())?;
    let provider_id = Some(provider.id.clone());
    let client = Client::builder()
        .timeout(Duration::from_secs(90))
        .build()
        .map_err(|error| error.to_string())?;

    match (request.method.as_str(), request.path.as_str()) {
        ("GET", "/v1/models") => proxy_get_models(&client, &provider).map(|response| (response, provider_id)),
        ("POST", "/v1/chat/completions") => proxy_chat_completions(&client, &provider, &request)
            .map(|response| (response, provider_id)),
        ("POST", "/v1/responses") => proxy_responses(&client, &provider, &request).map(|response| (response, provider_id)),
        _ => Ok((
            json_response(
                404,
                json!({ "error": { "message": "Unsupported model relay route" } }),
            ),
            provider_id,
        )),
    }
}

fn push_log(entry: ModelRelayLogEntry) {
    if let Ok(mut state) = relay_state().lock() {
        state.logs.push(entry);
        if state.logs.len() > 50 {
            let overflow = state.logs.len() - 50;
            state.logs.drain(0..overflow);
        }
    }
}

fn authorize_request(config: &ModelGatewayConfig, request: &RelayRequest) -> Result<(), String> {
    let expected = match config.relay.management_token.as_deref() {
        Some(token) if !token.is_empty() => token,
        _ => return Ok(()),
    };
    let actual = request
        .headers
        .get("authorization")
        .and_then(|value| value.strip_prefix("Bearer "))
        .or_else(|| request.headers.get("x-ai-strategist-token").map(String::as_str));

    if actual == Some(expected) {
        Ok(())
    } else {
        Err("Relay access token is required".to_string())
    }
}

fn extract_model(body: &[u8]) -> Option<String> {
    serde_json::from_slice::<Value>(body)
        .ok()
        .and_then(|value| value.get("model").and_then(Value::as_str).map(str::to_string))
}

fn provider_for_request(config: &ModelGatewayConfig, model: Option<&str>) -> Result<ModelProviderConfig, String> {
    if let Some(model) = model {
        for route in config.model_routes.iter().filter(|route| route.enabled) {
            if model_matches(&route.model_pattern, model) {
                if let Some(provider) = config
                    .providers
                    .iter()
                    .find(|provider| provider.enabled && provider.id == route.provider_id)
                {
                    return Ok(provider.clone());
                }
            }
        }
    }

    default_provider(config)
}

fn model_matches(pattern: &str, model: &str) -> bool {
    let pattern = pattern.trim();
    if pattern == "*" {
        return true;
    }
    if let Some(prefix) = pattern.strip_suffix('*') {
        return model.starts_with(prefix);
    }
    pattern == model
}

fn default_provider(config: &ModelGatewayConfig) -> Result<ModelProviderConfig, String> {
    let provider = config
        .fallback_order
        .iter()
        .filter_map(|id| config.providers.iter().find(|provider| provider.id == *id))
        .find(|provider| provider.enabled)
        .or_else(|| {
            config
                .default_provider_id
                .as_deref()
                .and_then(|id| config.providers.iter().find(|provider| provider.id == id))
        })
        .or_else(|| config.providers.iter().find(|provider| provider.enabled))
        .ok_or_else(|| "No enabled model provider is configured".to_string())?;

    if !provider.enabled {
        return Err(format!("Default provider {} is disabled", provider.id));
    }
    Ok(provider.clone())
}

fn proxy_chat_completions(
    client: &Client,
    provider: &ModelProviderConfig,
    request: &RelayRequest,
) -> Result<RelayResponse, String> {
    match provider.kind {
        ModelProviderKind::OpenaiCompatible => proxy_json(client, provider, "/chat/completions", request),
        ModelProviderKind::Responses => {
            let body = convert_chat_to_responses(&request.body)?;
            let response = proxy_json_body(client, provider, "/responses", body, request)?;
            Ok(convert_responses_response_to_chat(response))
        }
    }
}

fn proxy_responses(
    client: &Client,
    provider: &ModelProviderConfig,
    request: &RelayRequest,
) -> Result<RelayResponse, String> {
    match provider.kind {
        ModelProviderKind::Responses => proxy_json(client, provider, "/responses", request),
        ModelProviderKind::OpenaiCompatible => {
            let body = convert_responses_to_chat(&request.body)?;
            let response = proxy_json_body(client, provider, "/chat/completions", body, request)?;
            Ok(convert_chat_response_to_responses(response))
        }
    }
}

fn proxy_get_models(client: &Client, provider: &ModelProviderConfig) -> Result<RelayResponse, String> {
    let endpoint = format!("{}/models", provider.base_url.trim_end_matches('/'));
    let mut request = client.get(&endpoint);
    if let Some(api_key) = provider.api_key.as_deref() {
        request = request.bearer_auth(api_key);
    }
    upstream_response(request.send().map_err(|error| error.to_string())?)
}

fn proxy_json(
    client: &Client,
    provider: &ModelProviderConfig,
    upstream_path: &str,
    request: &RelayRequest,
) -> Result<RelayResponse, String> {
    proxy_json_body(client, provider, upstream_path, request.body.clone(), request)
}

fn proxy_json_body(
    client: &Client,
    provider: &ModelProviderConfig,
    upstream_path: &str,
    body: Vec<u8>,
    request: &RelayRequest,
) -> Result<RelayResponse, String> {
    let endpoint = format!("{}{}", provider.base_url.trim_end_matches('/'), upstream_path);
    let mut upstream = client
        .post(endpoint)
        .header("Content-Type", "application/json")
        .body(body);

    if let Some(api_key) = provider.api_key.as_deref() {
        upstream = upstream.bearer_auth(api_key);
    }

    if let Some(accept) = request.headers.get("accept") {
        upstream = upstream.header("Accept", accept);
    }

    upstream_response(upstream.send().map_err(|error| error.to_string())?)
}

fn convert_chat_to_responses(body: &[u8]) -> Result<Vec<u8>, String> {
    let value: Value = serde_json::from_slice(body).map_err(|error| error.to_string())?;
    let model = value
        .get("model")
        .cloned()
        .ok_or_else(|| "model is required".to_string())?;
    let input = value
        .get("messages")
        .cloned()
        .ok_or_else(|| "messages is required".to_string())?;
    let mut converted = json!({
        "model": model,
        "input": input,
    });
    if let Some(stream) = value.get("stream") {
        converted["stream"] = stream.clone();
    }
    serde_json::to_vec(&converted).map_err(|error| error.to_string())
}

fn convert_responses_to_chat(body: &[u8]) -> Result<Vec<u8>, String> {
    let value: Value = serde_json::from_slice(body).map_err(|error| error.to_string())?;
    let model = value
        .get("model")
        .cloned()
        .ok_or_else(|| "model is required".to_string())?;
    let messages = match value.get("input") {
        Some(Value::String(input)) => json!([{ "role": "user", "content": input }]),
        Some(Value::Array(items)) => Value::Array(items.clone()),
        Some(input) => json!([{ "role": "user", "content": input.to_string() }]),
        None => return Err("input is required".to_string()),
    };
    let mut converted = json!({
        "model": model,
        "messages": messages,
    });
    if let Some(stream) = value.get("stream") {
        converted["stream"] = stream.clone();
    }
    serde_json::to_vec(&converted).map_err(|error| error.to_string())
}

fn convert_responses_response_to_chat(response: RelayResponse) -> RelayResponse {
    if response.status < 200 || response.status >= 300 || !response.content_type.contains("json") {
        return response;
    }
    let Ok(value) = serde_json::from_slice::<Value>(&response.body) else {
        return response;
    };
    let content = response_text_from_responses(&value).unwrap_or_default();
    let model = value.get("model").cloned().unwrap_or_else(|| json!(""));
    json_response(
        response.status,
        json!({
            "id": value.get("id").cloned().unwrap_or_else(|| json!("relay-response")),
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }]
        }),
    )
}

fn convert_chat_response_to_responses(response: RelayResponse) -> RelayResponse {
    if response.status < 200 || response.status >= 300 || !response.content_type.contains("json") {
        return response;
    }
    let Ok(value) = serde_json::from_slice::<Value>(&response.body) else {
        return response;
    };
    let content = value
        .get("choices")
        .and_then(Value::as_array)
        .and_then(|choices| choices.first())
        .and_then(|choice| choice.get("message"))
        .and_then(|message| message.get("content"))
        .and_then(Value::as_str)
        .unwrap_or_default();
    json_response(
        response.status,
        json!({
            "id": value.get("id").cloned().unwrap_or_else(|| json!("relay-response")),
            "object": "response",
            "model": value.get("model").cloned().unwrap_or_else(|| json!("")),
            "output_text": content,
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": content
                }]
            }]
        }),
    )
}

fn response_text_from_responses(value: &Value) -> Option<String> {
    if let Some(text) = value.get("output_text").and_then(Value::as_str) {
        return Some(text.to_string());
    }
    value
        .get("output")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .and_then(|item| item.get("content"))
        .and_then(Value::as_array)
        .and_then(|content| content.first())
        .and_then(|part| part.get("text"))
        .and_then(Value::as_str)
        .map(str::to_string)
}

fn upstream_response(response: reqwest::blocking::Response) -> Result<RelayResponse, String> {
    let status = response.status().as_u16();
    let content_type = response
        .headers()
        .get("content-type")
        .and_then(|value| value.to_str().ok())
        .unwrap_or("application/json")
        .to_string();
    let body = response.bytes().map_err(|error| error.to_string())?.to_vec();

    Ok(RelayResponse {
        status,
        content_type,
        body,
    })
}

fn json_response(status: u16, body: Value) -> RelayResponse {
    RelayResponse {
        status,
        content_type: "application/json".to_string(),
        body: serde_json::to_vec(&body).unwrap_or_else(|_| b"{}".to_vec()),
    }
}

fn write_response(stream: &mut TcpStream, response: RelayResponse) -> Result<(), String> {
    let status_text = match response.status {
        200 => "OK",
        404 => "Not Found",
        500 => "Internal Server Error",
        _ => "OK",
    };
    let headers = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n",
        response.status,
        status_text,
        response.content_type,
        response.body.len()
    );
    stream
        .write_all(headers.as_bytes())
        .and_then(|_| stream.write_all(&response.body))
        .map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_response_serializes_body() {
        let response = json_response(200, json!({ "ok": true }));
        assert_eq!(response.status, 200);
        assert_eq!(response.content_type, "application/json");
        assert!(String::from_utf8(response.body).unwrap().contains("\"ok\":true"));
    }

    #[test]
    fn model_pattern_supports_prefix_and_wildcard() {
        assert!(model_matches("qwen-*", "qwen-plus"));
        assert!(model_matches("*", "anything"));
        assert!(model_matches("deepseek-chat", "deepseek-chat"));
        assert!(!model_matches("deepseek-chat", "deepseek-reasoner"));
    }

    #[test]
    fn converts_between_chat_and_responses_shapes() {
        let responses = convert_chat_to_responses(
            br#"{"model":"x","messages":[{"role":"user","content":"hi"}],"stream":true}"#,
        )
        .unwrap();
        let responses_value: Value = serde_json::from_slice(&responses).unwrap();
        assert_eq!(responses_value["model"], "x");
        assert_eq!(responses_value["input"][0]["content"], "hi");
        assert_eq!(responses_value["stream"], true);

        let chat = convert_responses_to_chat(br#"{"model":"x","input":"hello"}"#).unwrap();
        let chat_value: Value = serde_json::from_slice(&chat).unwrap();
        assert_eq!(chat_value["messages"][0]["role"], "user");
        assert_eq!(chat_value["messages"][0]["content"], "hello");
    }

    #[test]
    fn converts_response_payloads_between_protocol_shapes() {
        let chat = convert_responses_response_to_chat(RelayResponse {
            status: 200,
            content_type: "application/json".to_string(),
            body: br#"{"id":"r1","model":"x","output_text":"hello"}"#.to_vec(),
        });
        let chat_value: Value = serde_json::from_slice(&chat.body).unwrap();
        assert_eq!(chat_value["object"], "chat.completion");
        assert_eq!(chat_value["choices"][0]["message"]["content"], "hello");

        let responses = convert_chat_response_to_responses(RelayResponse {
            status: 200,
            content_type: "application/json".to_string(),
            body: br#"{"id":"c1","model":"x","choices":[{"message":{"content":"hi"}}]}"#.to_vec(),
        });
        let responses_value: Value = serde_json::from_slice(&responses.body).unwrap();
        assert_eq!(responses_value["object"], "response");
        assert_eq!(responses_value["output_text"], "hi");
    }
}

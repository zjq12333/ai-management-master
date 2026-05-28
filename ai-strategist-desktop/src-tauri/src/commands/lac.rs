use reqwest::blocking::Client;
use serde_json::{json, Value};
use std::time::Duration;

const DEFAULT_LAC_CONTROL_SPACE_URL: &str = "http://127.0.0.1:20128/control/lac-control-space";

fn lac_control_space_url() -> String {
    std::env::var("AI_STRATEGIST_LAC_CONTROL_SPACE_URL")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| DEFAULT_LAC_CONTROL_SPACE_URL.to_string())
}

#[tauri::command]
pub fn lac_control_space_status() -> Result<Value, String> {
    let endpoint = lac_control_space_url();
    let client = Client::builder()
        .timeout(Duration::from_millis(1800))
        .build()
        .map_err(|error| error.to_string())?;

    match client.get(&endpoint).send() {
        Ok(response) => {
            let status = response.status().as_u16();
            if !response.status().is_success() {
                return Ok(json!({
                    "ok": false,
                    "reachable": false,
                    "endpoint": endpoint,
                    "status_code": status,
                    "error": format!("LAC returned HTTP {}", status),
                    "snapshot": null,
                }));
            }

            let snapshot = response.json::<Value>().map_err(|error| error.to_string())?;
            Ok(json!({
                "ok": true,
                "reachable": true,
                "endpoint": endpoint,
                "status_code": status,
                "error": null,
                "snapshot": snapshot,
            }))
        }
        Err(error) => Ok(json!({
            "ok": false,
            "reachable": false,
            "endpoint": endpoint,
            "status_code": null,
            "error": error.to_string(),
            "snapshot": null,
        })),
    }
}

use crate::core::auth::ApiRequestContext;
use crate::core::models::{
    ApiProxyConfigPayload, ApiProxyDetectPayload, ApiProxyMode, ApiProxyTestPayload, CoreError,
};

// Open-source build: keep API proxy probing minimal.
// We return structured payloads so the UI can show status, but we avoid heavy networking logic.

pub fn sanitize_proxy_config(
    input: &ApiProxyConfigPayload,
) -> Result<ApiProxyConfigPayload, CoreError> {
    let mut cfg = input.clone();
    match cfg.mode {
        ApiProxyMode::Direct => {
            cfg.url = None;
        }
        ApiProxyMode::Manual => {
            if let Some(ref url) = cfg.url {
                if url.trim().is_empty() {
                    cfg.url = None;
                }
            }
        }
    }
    Ok(cfg)
}

pub fn test_api_connectivity(
    cfg: &ApiProxyConfigPayload,
    _context: Option<&ApiRequestContext>,
) -> ApiProxyTestPayload {
    match cfg.mode {
        ApiProxyMode::Direct => ApiProxyTestPayload {
            code: "direct".into(),
            reachable: true,
            status_code: None,
            message: "Direct mode (not probed)".into(),
        },
        ApiProxyMode::Manual => {
            if let Some(ref url) = cfg.url {
                ApiProxyTestPayload {
                    code: "manual".into(),
                    reachable: true,
                    status_code: None,
                    message: format!("Manual proxy set: {url}"),
                }
            } else {
                ApiProxyTestPayload {
                    code: "manual_missing_url".into(),
                    reachable: false,
                    status_code: None,
                    message: "Manual proxy mode requires a URL".into(),
                }
            }
        }
    }
}

pub fn detect_api_proxy_config(_context: Option<&ApiRequestContext>) -> ApiProxyDetectPayload {
    // Open-source build: do not attempt system proxy inspection by default.
    ApiProxyDetectPayload {
        found: false,
        mode: None,
        url: None,
        probe: ApiProxyTestPayload {
            code: "detect_skipped".into(),
            reachable: false,
            status_code: None,
            message: "Detection not implemented in open-source build".into(),
        },
    }
}

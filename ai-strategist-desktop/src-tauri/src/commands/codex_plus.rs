use codex_plus_core::status::StatusStore;
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CodexPlusUpstreamSnapshot {
    pub version: &'static str,
    pub repository: &'static str,
    pub license: &'static str,
    pub latest_status_present: bool,
}

#[tauri::command]
pub fn codex_plus_upstream_snapshot() -> CodexPlusUpstreamSnapshot {
    upstream_snapshot_payload()
}

fn upstream_snapshot_payload() -> CodexPlusUpstreamSnapshot {
    CodexPlusUpstreamSnapshot {
        version: codex_plus_core::version::VERSION,
        repository: "https://github.com/BigPizzaV3/CodexPlusPlus",
        license: "MIT",
        latest_status_present: StatusStore::default()
            .load_latest()
            .ok()
            .flatten()
            .is_some(),
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn upstream_snapshot_uses_codex_plus_metadata() {
        let payload = super::upstream_snapshot_payload();

        assert_eq!(payload.version, "1.1.7");
        assert_eq!(payload.repository, "https://github.com/BigPizzaV3/CodexPlusPlus");
        assert_eq!(payload.license, "MIT");
    }
}

use crate::core::analytics::UsageAnalyticsPayload;
use crate::core::models::{CoreSnapshotPayload, McpServerListPayload, SkillListPayload};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct BootstrapStatePayload {
    pub written_at: Option<i64>,
    pub snapshot_progressive: Option<CoreSnapshotPayload>,
    pub usage_analytics: Option<UsageAnalyticsPayload>,
    pub mcp_servers: Option<McpServerListPayload>,
    pub installed_skills: Option<SkillListPayload>,
}

pub fn load(path: &Path) -> BootstrapStatePayload {
    let raw = std::fs::read_to_string(path).ok();
    raw.and_then(|s| serde_json::from_str::<BootstrapStatePayload>(&s).ok())
        .unwrap_or_default()
}

pub fn update<F>(path: &Path, mut apply: F) -> Result<(), crate::core::models::CoreError>
where
    F: FnMut(&mut BootstrapStatePayload),
{
    let mut payload = load(path);
    apply(&mut payload);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let data = serde_json::to_string_pretty(&payload)?;
    std::fs::write(path, data)?;
    Ok(())
}

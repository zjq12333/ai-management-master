use crate::core::models::{CoreError, RateLimitWindow, UsageSource};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "camelCase")]
pub struct QuotaStoreFile {
    pub updated_at: i64,
    #[serde(default)]
    pub items: Vec<QuotaStoreItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct QuotaStoreItem {
    pub account_key: String,
    pub captured_at: i64,
    pub usage_source: UsageSource,
    pub primary_window: Option<RateLimitWindow>,
    pub secondary_window: Option<RateLimitWindow>,
    pub token_status: Option<String>,
}

pub fn load_or_default(path: &Path) -> QuotaStoreFile {
    let raw = std::fs::read_to_string(path).ok();
    raw.and_then(|s| serde_json::from_str::<QuotaStoreFile>(&s).ok())
        .unwrap_or_default()
}

pub fn save(path: &Path, payload: &QuotaStoreFile) -> Result<(), CoreError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let data = serde_json::to_string_pretty(payload)?;
    std::fs::write(path, data)?;
    Ok(())
}

pub fn find_item<'a>(store: &'a QuotaStoreFile, account_key: &str) -> Option<&'a QuotaStoreItem> {
    store.items.iter().find(|i| i.account_key == account_key)
}

pub fn upsert_item(store: &mut QuotaStoreFile, item: QuotaStoreItem, updated_at: i64) -> bool {
    if let Some(existing) = store
        .items
        .iter_mut()
        .find(|i| i.account_key == item.account_key)
    {
        if *existing == item {
            return false;
        }
        *existing = item;
        store.updated_at = updated_at;
        return true;
    }
    store.items.push(item);
    store.updated_at = updated_at;
    true
}

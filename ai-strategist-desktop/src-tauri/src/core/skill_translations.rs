use crate::core::auth::current_timestamp;
use crate::core::models::{
    CoreError, SkillTranslationCachePayload, SkillTranslationEntry, SkillTranslationPayload,
    SkillTranslationRequestItem,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::path::Path;

#[derive(Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SkillTranslationCacheFile {
    // Kept only so old local cache files with a saved DeepL key still parse.
    #[serde(default)]
    #[serde(rename = "deeplApiKey")]
    _legacy_deepl_api_key: Option<String>,
    #[serde(default)]
    translations: HashMap<String, SkillTranslationEntry>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct MyMemoryResponse {
    response_data: MyMemoryResponseData,
    #[serde(default)]
    response_status: i32,
    #[serde(default)]
    response_details: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct MyMemoryResponseData {
    translated_text: String,
}

pub fn load_cache(cache_path: &Path) -> Result<SkillTranslationCachePayload, CoreError> {
    let cache = read_cache_file(cache_path)?;
    Ok(SkillTranslationCachePayload {
        configured: true,
        translations: cache.translations,
        source_path: cache_path.display().to_string(),
    })
}

pub fn translate_summaries(
    cache_path: &Path,
    _api_key: Option<String>,
    items: Vec<SkillTranslationRequestItem>,
) -> Result<SkillTranslationPayload, CoreError> {
    let mut cache = read_cache_file(cache_path)?;

    let mut pending = Vec::new();
    let mut skipped = 0i32;
    for item in items {
        let text = item.text.trim();
        if text.is_empty() || !needs_zh_translation(text) {
            skipped += 1;
            continue;
        }

        let source_hash = hash_text(text);
        if cache
            .translations
            .get(&item.id)
            .map(|entry| entry.source_hash == source_hash)
            .unwrap_or(false)
        {
            skipped += 1;
            continue;
        }

        pending.push((item.id, text.to_string(), source_hash));
    }

    let mut translated_count = 0i32;
    let mut failed_count = 0i32;
    for (skill_id, source, source_hash) in pending {
        match mymemory_translate(&source) {
            Ok(zh) => {
                cache.translations.insert(
                    skill_id.clone(),
                    SkillTranslationEntry {
                        skill_id,
                        source_hash,
                        source,
                        zh,
                        updated_at: current_timestamp(),
                    },
                );
                translated_count += 1;
            }
            Err(_) => {
                failed_count += 1;
            }
        }
    }

    write_cache_file(cache_path, &cache)?;

    Ok(SkillTranslationPayload {
        configured: true,
        translated_count,
        skipped_count: skipped,
        failed_count,
        translations: cache.translations,
        source_path: cache_path.display().to_string(),
    })
}

fn read_cache_file(cache_path: &Path) -> Result<SkillTranslationCacheFile, CoreError> {
    if !cache_path.exists() {
        return Ok(SkillTranslationCacheFile::default());
    }
    let raw = std::fs::read_to_string(cache_path)?;
    Ok(serde_json::from_str(&raw).unwrap_or_default())
}

fn write_cache_file(cache_path: &Path, cache: &SkillTranslationCacheFile) -> Result<(), CoreError> {
    if let Some(parent) = cache_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let data = serde_json::to_string_pretty(cache)?;
    std::fs::write(cache_path, data)?;
    Ok(())
}

fn mymemory_translate(text: &str) -> Result<String, CoreError> {
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(20))
        .build()?;
    let response = client
        .get("https://api.mymemory.translated.net/get")
        .query(&[
            ("q", clamp_mymemory_text(text)),
            ("langpair", "en|zh-CN".to_string()),
            ("mt", "1".to_string()),
        ])
        .send()?;
    if !response.status().is_success() {
        return Err(CoreError::OperationFailed(format!(
            "MyMemory translation failed: HTTP {}",
            response.status()
        )));
    }

    let payload: MyMemoryResponse = response.json()?;
    if payload.response_status >= 400 {
        return Err(CoreError::OperationFailed(format!(
            "MyMemory translation failed: {}",
            payload
                .response_details
                .unwrap_or_else(|| payload.response_status.to_string())
        )));
    }

    let translated = payload.response_data.translated_text.trim().to_string();
    if translated.is_empty() {
        return Err(CoreError::OperationFailed(
            "MyMemory translation returned empty text".to_string(),
        ));
    }
    Ok(translated)
}

fn clamp_mymemory_text(text: &str) -> String {
    const MAX_BYTES: usize = 500;
    let trimmed = text.trim();
    if trimmed.len() <= MAX_BYTES {
        return trimmed.to_string();
    }

    let mut end = 0usize;
    for (idx, ch) in trimmed.char_indices() {
        let next = idx + ch.len_utf8();
        if next > MAX_BYTES {
            break;
        }
        end = next;
    }
    trimmed[..end].trim_end().to_string()
}

fn hash_text(text: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    format!("{:x}", hasher.finalize())
}

fn needs_zh_translation(text: &str) -> bool {
    let mut ascii_letters = 0usize;
    let mut cjk = 0usize;
    for ch in text.chars() {
        if ch.is_ascii_alphabetic() {
            ascii_letters += 1;
        } else if ('\u{4e00}'..='\u{9fff}').contains(&ch) {
            cjk += 1;
        }
    }
    ascii_letters >= 12 && ascii_letters > cjk.saturating_mul(2)
}

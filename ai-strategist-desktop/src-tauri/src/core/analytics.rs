use serde::{Deserialize, Serialize};

// Open-source build: keep analytics minimal so the app can compile and run.
// Proprietary analytics logic is not included in this repo.

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "camelCase")]
pub struct UsageAnalyticsPayload {}

use std::path::{Path, PathBuf};

#[cfg(test)]
pub fn repo_root_from_manifest() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("repo root")
        .to_path_buf()
}

fn explicit_bridge_path_from_env() -> Option<PathBuf> {
    if let Some(path) = std::env::var_os("AI_STRATEGIST_PRELAUNCH_BRIDGE") {
        let path = PathBuf::from(path);
        if path.exists() {
            return Some(path);
        }
    }
    None
}

pub fn bridge_program_path() -> Option<PathBuf> {
    explicit_bridge_path_from_env().or_else(|| {
        bundled_bridge_candidates()
            .into_iter()
            .find(|candidate| candidate.exists())
    })
}

pub fn bridge_script_path() -> Option<PathBuf> {
    bridge_program_path()
        .filter(|path| !is_windows_executable(path))
}

pub fn bridge_exe_path() -> Option<PathBuf> {
    bridge_program_path().filter(|path| is_windows_executable(path))
}

fn is_windows_executable(path: &Path) -> bool {
    path.extension()
        .and_then(|extension| extension.to_str())
        .is_some_and(|extension| extension.eq_ignore_ascii_case("exe"))
}

pub fn bundled_bridge_candidates() -> Vec<PathBuf> {
    let Some(exe_dir) = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
    else {
        return Vec::new();
    };

    let mut candidates = Vec::new();
    for file_name in ["prelaunch_bridge.exe", "prelaunch_bridge.py"] {
        candidates.extend([
            exe_dir.join(file_name),
            exe_dir.join("prelaunch").join(file_name),
            exe_dir.join("resources").join(file_name),
            exe_dir.join("resources").join("prelaunch").join(file_name),
            exe_dir.join("_up_").join(file_name),
            exe_dir.join("_up_").join("prelaunch").join(file_name),
            exe_dir.join("..").join("Resources").join(file_name),
            exe_dir
                .join("..")
                .join("Resources")
                .join("prelaunch")
                .join(file_name),
        ]);
    }
    candidates
}

fn bridge_command_prefix() -> Result<Vec<String>, String> {
    if let Some(path) = bridge_exe_path() {
        return Ok(vec![path.display().to_string()]);
    }
    let Some(script_path) = bridge_script_path() else {
        return Err(
            "prelaunch_bridge_missing: could not find bundled prelaunch_bridge.exe or prelaunch_bridge.py"
                .to_string(),
        );
    };
    Ok(vec![
        python_command(),
        script_path.display().to_string(),
    ])
}

pub fn python_command() -> String {
    crate::platform::runtime_resolver::resolve_python_runtime()
        .path
        .display()
        .to_string()
}

pub fn bridge_command(subcommand: &str, codex_home: &str) -> Result<Vec<String>, String> {
    bridge_command_with_mode(subcommand, codex_home, None, None, false, false)
}

#[derive(Default)]
pub struct RecoveryOptions<'a> {
    pub include_archived: bool,
    pub allow_missing_cwd: bool,
    pub allow_empty_cwd: bool,
    pub allow_missing_session: bool,
    pub projectless_mode: Option<&'a str>,
    pub unarchive_selected: bool,
}

fn append_recovery_options(command: &mut Vec<String>, options: RecoveryOptions<'_>) {
    if options.include_archived {
        command.push("--include-archived".to_string());
    }
    if options.allow_missing_cwd {
        command.push("--allow-missing-cwd".to_string());
    }
    if options.allow_empty_cwd {
        command.push("--allow-empty-cwd".to_string());
    }
    if options.allow_missing_session {
        command.push("--allow-missing-session".to_string());
    }
    if let Some(projectless_mode) = options.projectless_mode {
        command.push("--projectless-mode".to_string());
        command.push(projectless_mode.to_string());
    }
    if options.unarchive_selected {
        command.push("--unarchive-selected".to_string());
    }
}

pub fn bridge_command_with_mode(
    subcommand: &str,
    codex_home: &str,
    mode: Option<&str>,
    provider_json: Option<&str>,
    hide_official_quota_notice: bool,
    restore_history: bool,
) -> Result<Vec<String>, String> {
    let mut command = bridge_command_prefix()?;
    command.extend([
        subcommand.to_string(),
        "--codex-home".to_string(),
        codex_home.to_string(),
    ]);
    if let Some(mode) = mode {
        command.push("--mode".to_string());
        command.push(mode.to_string());
    }
    if let Some(provider_json) = provider_json {
        command.push("--provider-json".to_string());
        command.push(provider_json.to_string());
    }
    if hide_official_quota_notice {
        command.push("--hide-official-quota-notice".to_string());
    }
    if restore_history {
        command.push("--restore-history".to_string());
    }
    Ok(command)
}

pub fn bridge_command_with_recovery_options(
    subcommand: &str,
    codex_home: &str,
    options: RecoveryOptions<'_>,
) -> Result<Vec<String>, String> {
    let mut command = bridge_command(subcommand, codex_home)?;
    append_recovery_options(&mut command, options);
    Ok(command)
}

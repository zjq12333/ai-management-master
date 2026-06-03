use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ResolvedRuntimeSource {
    ManagedLocal,
    BundledCache,
    PathFallback,
}

impl ResolvedRuntimeSource {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::ManagedLocal => "managedLocal",
            Self::BundledCache => "bundledCache",
            Self::PathFallback => "pathFallback",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedRuntime {
    pub path: PathBuf,
    pub source: ResolvedRuntimeSource,
}

const REQUIRED_BRIDGE_PYTHON_MODULES: &[&str] = &["requests", "websocket"];

fn local_openai_codex_bin_root() -> Option<PathBuf> {
    std::env::var("LOCALAPPDATA")
        .ok()
        .map(PathBuf::from)
        .map(|root| root.join("OpenAI").join("Codex").join("bin"))
}

fn env_runtime_path(key: &str, source: ResolvedRuntimeSource) -> Option<ResolvedRuntime> {
    std::env::var_os(key)
        .map(PathBuf::from)
        .filter(|path| path.exists())
        .map(|path| ResolvedRuntime { path, source })
}

fn is_windowsapps_codex_desktop_shim(path: &PathBuf) -> bool {
    let normalized = path.to_string_lossy().replace('/', "\\").to_lowercase();
    normalized.contains("\\windowsapps\\openai.codex_") && normalized.ends_with("\\app\\codex.exe")
}

#[cfg(target_os = "windows")]
fn find_windowsapps_codex_desktop_exe() -> Option<PathBuf> {
    let root = std::env::var_os("PROGRAMFILES")
        .map(PathBuf::from)
        .map(|path| path.join("WindowsApps"))?;
    let mut candidates: Vec<PathBuf> = std::fs::read_dir(root)
        .ok()?
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let file_name = entry.file_name().to_string_lossy().to_lowercase();
            if file_name.starts_with("openai.codex_") {
                let candidate = entry.path().join("app").join("Codex.exe");
                if candidate.exists() {
                    return Some(candidate);
                }
            }
            None
        })
        .collect();
    candidates.sort_by(|a, b| b.cmp(a));
    candidates.into_iter().next()
}

#[cfg(not(target_os = "windows"))]
fn find_windowsapps_codex_desktop_exe() -> Option<PathBuf> {
    None
}

fn python_runtime_supports_modules(path: &PathBuf, modules: &[&str]) -> bool {
    let import_list = modules.join(", ");
    #[cfg(target_os = "windows")]
    let output = crate::platform::windows::background_command_path(path)
        .args(["-c", &format!("import {}", import_list)])
        .output();
    #[cfg(not(target_os = "windows"))]
    let output = std::process::Command::new(path)
        .args(["-c", &format!("import {}", import_list)])
        .output();

    matches!(output, Ok(result) if result.status.success())
}

fn validated_python_runtime(runtime: ResolvedRuntime) -> Option<ResolvedRuntime> {
    if python_runtime_supports_modules(&runtime.path, REQUIRED_BRIDGE_PYTHON_MODULES) {
        Some(runtime)
    } else {
        None
    }
}

fn userprofile_dir() -> Option<PathBuf> {
    std::env::var("USERPROFILE").ok().map(PathBuf::from)
}

fn latest_runtime_dir(root: &PathBuf) -> Option<PathBuf> {
    let mut dirs: Vec<PathBuf> = std::fs::read_dir(root)
        .ok()
        .into_iter()
        .flat_map(|entries| entries.filter_map(Result::ok))
        .filter_map(|entry| {
            let path = entry.path();
            if path.is_dir() {
                Some(path)
            } else {
                None
            }
        })
        .collect();
    dirs.sort_by(|a, b| b.file_name().cmp(&a.file_name()));
    dirs.into_iter().next()
}

fn find_in_runtime_dirs<F>(mut resolve: F) -> Option<ResolvedRuntime>
where
    F: FnMut(&PathBuf) -> Option<ResolvedRuntime>,
{
    if let Some(userprofile) = userprofile_dir() {
        let bundled_root = userprofile
            .join(".cache")
            .join("codex-runtimes")
            .join("codex-primary-runtime")
            .join("dependencies");
        if let Some(runtime) = resolve(&bundled_root) {
            return Some(runtime);
        }
    }

    if let Some(bin_root) = local_openai_codex_bin_root() {
        if let Some(latest) = latest_runtime_dir(&bin_root) {
            if let Some(runtime) = resolve(&latest) {
                return Some(runtime);
            }
        }
    }

    None
}

fn bundled_python_candidates() -> Vec<PathBuf> {
    let Some(exe_dir) = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(PathBuf::from))
    else {
        return Vec::new();
    };

    vec![
        exe_dir.join("python").join("python.exe"),
        exe_dir.join("resources").join("python").join("python.exe"),
        exe_dir.join("_up_").join("python").join("python.exe"),
        exe_dir
            .join("..")
            .join("Resources")
            .join("python")
            .join("python.exe"),
    ]
}

pub fn resolve_python_runtime() -> ResolvedRuntime {
    env_runtime_path("AI_STRATEGIST_PYTHON", ResolvedRuntimeSource::ManagedLocal)
        .and_then(validated_python_runtime)
        .or_else(|| {
            bundled_python_candidates().into_iter().find_map(|path| {
                if path.exists() {
                    validated_python_runtime(ResolvedRuntime {
                        path,
                        source: ResolvedRuntimeSource::ManagedLocal,
                    })
                } else {
                    None
                }
            })
        })
        .or_else(|| find_in_runtime_dirs(|root| {
        let bundled_candidate = root.join("python").join("python.exe");
        if bundled_candidate.exists() {
            return validated_python_runtime(ResolvedRuntime {
                path: bundled_candidate,
                source: ResolvedRuntimeSource::BundledCache,
            });
        }

        let direct_candidate = root.join("python.exe");
        if direct_candidate.exists() {
            return validated_python_runtime(ResolvedRuntime {
                path: direct_candidate,
                source: ResolvedRuntimeSource::ManagedLocal,
            });
        }

        None
    }))
    .or_else(|| {
        find_on_path("python.exe", true)
            .map(|path| ResolvedRuntime {
                path,
                source: ResolvedRuntimeSource::PathFallback,
            })
            .and_then(validated_python_runtime)
    })
    .unwrap_or(ResolvedRuntime {
        path: PathBuf::from("python"),
        source: ResolvedRuntimeSource::PathFallback,
    })
}

pub fn resolve_helper_binary(name: &str) -> Option<ResolvedRuntime> {
    find_in_runtime_dirs(|root| {
        let candidate = root.join(name);
        if candidate.exists() {
            return Some(ResolvedRuntime {
                path: candidate,
                source: if root.ends_with("dependencies") {
                    ResolvedRuntimeSource::BundledCache
                } else {
                    ResolvedRuntimeSource::ManagedLocal
                },
            });
        }
        None
    })
    .or_else(|| {
        find_on_path(name, true).map(|path| ResolvedRuntime {
            path,
            source: ResolvedRuntimeSource::PathFallback,
        })
    })
}

pub fn resolve_codex_cli() -> Option<ResolvedRuntime> {
    if let Some(runtime) = env_runtime_path("AI_STRATEGIST_CODEX_CLI", ResolvedRuntimeSource::ManagedLocal) {
        return Some(runtime);
    }

    if let Some(local_appdata) = std::env::var("LOCALAPPDATA").ok().map(PathBuf::from) {
        let shim = local_appdata
            .join("OpenAI")
            .join("Codex")
            .join("shim")
            .join("codex.cmd");
        if shim.exists() {
            return Some(ResolvedRuntime {
                path: shim,
                source: ResolvedRuntimeSource::ManagedLocal,
            });
        }
    }

    find_in_runtime_dirs(|root| {
        let candidate = root.join("codex.exe");
        if candidate.exists() {
            return Some(ResolvedRuntime {
                path: candidate,
                source: if root.ends_with("dependencies") {
                    ResolvedRuntimeSource::BundledCache
                } else {
                    ResolvedRuntimeSource::ManagedLocal
                },
            });
        }
        None
    })
    .or_else(|| {
        find_on_path("codex.exe", false).map(|path| ResolvedRuntime {
            path,
            source: ResolvedRuntimeSource::PathFallback,
        })
    })
    .or_else(|| {
        find_on_path("codex.cmd", false).map(|path| ResolvedRuntime {
            path,
            source: ResolvedRuntimeSource::PathFallback,
        })
    })
}

#[cfg(target_os = "windows")]
pub fn resolve_codex_desktop_exe() -> Option<ResolvedRuntime> {
    if let Some(runtime) =
        env_runtime_path("AI_STRATEGIST_CODEX_DESKTOP", ResolvedRuntimeSource::ManagedLocal)
    {
        return Some(runtime);
    }

    let env_candidates = [
        ("LOCALAPPDATA", "Programs\\Codex\\Codex.exe"),
        ("LOCALAPPDATA", "Codex\\Codex.exe"),
        ("LOCALAPPDATA", "Programs\\OpenAI Codex\\Codex.exe"),
        ("LOCALAPPDATA", "Programs\\OpenAI\\Codex\\Codex.exe"),
        ("PROGRAMFILES", "Codex\\Codex.exe"),
        ("PROGRAMFILES", "OpenAI Codex\\Codex.exe"),
        ("PROGRAMFILES", "OpenAI\\Codex\\Codex.exe"),
        ("PROGRAMFILES(X86)", "Codex\\Codex.exe"),
        ("PROGRAMFILES(X86)", "OpenAI Codex\\Codex.exe"),
        ("PROGRAMFILES(X86)", "OpenAI\\Codex\\Codex.exe"),
    ];

    for (env_key, suffix) in env_candidates {
        if let Ok(prefix) = std::env::var(env_key) {
            let candidate = PathBuf::from(prefix).join(suffix);
            if candidate.exists() {
                return Some(ResolvedRuntime {
                    path: candidate,
                    source: ResolvedRuntimeSource::ManagedLocal,
                });
            }
        }
    }

    query_codex_desktop_from_registry()
        .map(|path| ResolvedRuntime {
            path,
            source: ResolvedRuntimeSource::ManagedLocal,
        })
        .or_else(|| {
            find_windowsapps_codex_desktop_exe().map(|path| ResolvedRuntime {
                path,
                source: ResolvedRuntimeSource::ManagedLocal,
            })
        })
        .or_else(|| {
            find_on_path("Codex.exe", false).map(|path| ResolvedRuntime {
                path,
                source: ResolvedRuntimeSource::PathFallback,
            })
        })
}

fn find_on_path(name: &str, allow_windowsapps: bool) -> Option<PathBuf> {
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths)
            .map(|dir| dir.join(name))
            .find(|candidate| {
                candidate.exists() && (allow_windowsapps || !path_contains_windowsapps(candidate))
            })
    })
}

fn path_contains_windowsapps(path: &std::path::Path) -> bool {
    path.components().any(|component| {
        component
            .as_os_str()
            .to_string_lossy()
            .eq_ignore_ascii_case("WindowsApps")
    })
}

#[cfg(target_os = "windows")]
fn query_codex_desktop_from_registry() -> Option<PathBuf> {
    let reg_paths = [
        r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Codex.exe",
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Codex.exe",
    ];
    for reg_path in reg_paths {
        if let Some(p) = query_reg_default_value(reg_path) {
            let pb = PathBuf::from(&p);
            if pb.exists() {
                return Some(pb);
            }
        }
    }

    let uninstall_roots = [
        r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    ];
    for root in uninstall_roots {
        if let Some(p) = find_codex_in_uninstall_entries(root) {
            return Some(p);
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn query_reg_default_value(key_path: &str) -> Option<String> {
    let output = crate::platform::windows::background_command("reg")
        .args(["query", key_path, "/ve"])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    for line in stdout.lines() {
        let trimmed = line.trim();
        if trimmed.contains("REG_SZ") || trimmed.contains("REG_EXPAND_SZ") {
            let parts: Vec<&str> = trimmed.splitn(3, "    ").collect();
            if parts.len() == 3 {
                let value = parts[2].trim();
                if !value.is_empty() {
                    return Some(value.to_string());
                }
            }
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn find_codex_in_uninstall_entries(root: &str) -> Option<PathBuf> {
    let output = crate::platform::windows::background_command("powershell")
        .args([
            "-NoProfile",
            "-Command",
            &format!(
                "Get-ChildItem 'Registry::{}' -ErrorAction SilentlyContinue | ForEach-Object {{ \
                    $dn = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DisplayName; \
                    $il = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).InstallLocation; \
                    if ($dn -like '*Codex*' -and $il) {{ Write-Output $il }} \
                }}",
                root
            ),
        ])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    for line in stdout.lines() {
        let dir = line.trim();
        if dir.is_empty() {
            continue;
        }
        let exe = PathBuf::from(dir).join("Codex.exe");
        if exe.exists() {
            return Some(exe);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::{
        bundled_python_candidates, find_on_path, python_runtime_supports_modules,
        resolve_codex_desktop_exe, resolve_python_runtime, ResolvedRuntimeSource,
    };
    use std::fs;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn python_runtime_resolution_returns_some_path() {
        let resolved = resolve_python_runtime();
        assert!(!resolved.path.as_os_str().is_empty());
        assert!(matches!(
            resolved.source,
            ResolvedRuntimeSource::ManagedLocal
                | ResolvedRuntimeSource::BundledCache
                | ResolvedRuntimeSource::PathFallback
        ));
    }

    #[test]
    fn resolved_python_runtime_supports_bridge_modules_when_discovered() {
        let resolved = resolve_python_runtime();
        if resolved.path != std::path::PathBuf::from("python") {
            assert!(python_runtime_supports_modules(&resolved.path, super::REQUIRED_BRIDGE_PYTHON_MODULES));
        }
    }

    #[test]
    fn invalid_explicit_python_runtime_does_not_win_resolution() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let original = std::env::var_os("AI_STRATEGIST_PYTHON");
        std::env::set_var("AI_STRATEGIST_PYTHON", "C:\\invalid\\missing-python.exe");
        let resolved = resolve_python_runtime();
        match original {
            Some(value) => std::env::set_var("AI_STRATEGIST_PYTHON", value),
            None => std::env::remove_var("AI_STRATEGIST_PYTHON"),
        }

        assert_ne!(resolved.path, std::path::PathBuf::from("C:\\invalid\\missing-python.exe"));
    }

    #[test]
    fn bundled_python_candidates_cover_tauri_resource_layouts() {
        let rendered = bundled_python_candidates()
            .iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>()
            .join("\n");

        assert!(rendered.contains("python"));
        assert!(rendered.contains("python.exe"));
        assert!(rendered.contains("resources"));
        assert!(rendered.contains("_up_"));
        assert!(rendered.contains("Resources"));
    }

    #[test]
    fn path_lookup_can_exclude_windowsapps_entries() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let root = std::env::temp_dir().join(format!(
            "ai-strategist-windowsapps-path-test-{}",
            std::process::id()
        ));
        let windowsapps = root.join("WindowsApps");
        fs::create_dir_all(&windowsapps).expect("windowsapps dir");
        let candidate = windowsapps.join("codex.exe");
        fs::write(&candidate, b"").expect("candidate");

        let original_path = std::env::var_os("PATH");
        std::env::set_var("PATH", windowsapps.as_os_str());
        let excluded = find_on_path("codex.exe", false);
        let allowed = find_on_path("codex.exe", true);
        match original_path {
            Some(value) => std::env::set_var("PATH", value),
            None => std::env::remove_var("PATH"),
        }
        let _ = fs::remove_dir_all(&root);

        assert_eq!(excluded, None);
        assert_eq!(allowed, Some(candidate));
    }

    #[test]
    fn explicit_codex_desktop_runtime_rejects_windowsapps_shim() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let root = std::env::temp_dir().join(format!(
            "ai-strategist-codex-desktop-env-test-{}",
            std::process::id()
        ));
        let windowsapps_shim = root
            .join("Microsoft")
            .join("WindowsApps")
            .join("OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0")
            .join("app")
            .join("Codex.exe");
        fs::create_dir_all(windowsapps_shim.parent().expect("shim parent")).expect("shim dir");
        fs::write(&windowsapps_shim, b"").expect("shim");

        let original_runtime = std::env::var_os("AI_STRATEGIST_CODEX_DESKTOP");
        let original_path = std::env::var_os("PATH");
        std::env::set_var("AI_STRATEGIST_CODEX_DESKTOP", windowsapps_shim.as_os_str());
        std::env::set_var("PATH", "");
        let resolved = resolve_codex_desktop_exe();
        match original_runtime {
            Some(value) => std::env::set_var("AI_STRATEGIST_CODEX_DESKTOP", value),
            None => std::env::remove_var("AI_STRATEGIST_CODEX_DESKTOP"),
        }
        match original_path {
            Some(value) => std::env::set_var("PATH", value),
            None => std::env::remove_var("PATH"),
        }
        let _ = fs::remove_dir_all(&root);

        assert_eq!(resolved, None);
    }
}

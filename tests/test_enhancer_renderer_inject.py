import subprocess
from pathlib import Path


def test_enhancer_renderer_script_parses_with_node():
    script = Path("enhancer_renderer_inject.js")
    assert script.exists()
    result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_enhancer_renderer_script_contains_project_move_contract():
    text = Path("enhancer_renderer_inject.js").read_text(encoding="utf-8")
    assert "聊天信息搬家" in text
    assert "普通对话" in text
    assert "/move-thread-workspace" in text
    assert "/thread-projectless" in text
    assert "/thread-sort-keys" in text
    assert "applyProjectMoveProjection" in text
    assert "moveRowToChats" in text
    assert "moveRowToProjectList" in text


def test_enhancer_renderer_script_copies_handoff_prompt_when_takeover_fails():
    text = Path("enhancer_renderer_inject.js").read_text(encoding="utf-8")
    assert "function copyTextToClipboard" in text
    assert "自动打开新对话失败" in text
    assert "已复制接管提示" in text
    assert "await copyTextToClipboard(prompt)" in text


def test_enhancer_renderer_script_contains_must_install_plugin_unlock():
    text = Path("enhancer_renderer_inject.js").read_text(encoding="utf-8")
    start = text.index("function pluginInstallCandidates")
    end = text.index("function normalizeWorkspacePath", start)
    plugin_unlock_code = text[start:end]
    assert "mustInstallPluginsEnabled" in text
    assert "function pluginEntryButton" in plugin_unlock_code
    assert "function enablePluginEntry" in plugin_unlock_code
    assert "spoofChatGPTAuthMethod(pluginButton)" in plugin_unlock_code
    assert "data-ai-strategist-plugin-enabled" not in plugin_unlock_code
    assert "aiStrategistPluginEnabled" in plugin_unlock_code
    assert "unlockMustInstallPluginButtons" in plugin_unlock_code
    assert "button:disabled.w-full.justify-center" in plugin_unlock_code
    assert "[role='button'][aria-disabled='true'].cursor-not-allowed" in plugin_unlock_code
    assert "button:disabled\"," not in plugin_unlock_code
    assert "button[aria-disabled='true']\"," not in plugin_unlock_code
    assert "document.body.textContent" not in plugin_unlock_code
    assert "button.disabled = false" in plugin_unlock_code
    assert "removeAttribute(\"aria-disabled\")" in plugin_unlock_code
    assert "spoofChatGPTAuthMethod(document.body)" in plugin_unlock_code
    assert "必须装" in plugin_unlock_code
    assert "unlockMustInstallPluginButtons();" in text[text.index("function scan") :]

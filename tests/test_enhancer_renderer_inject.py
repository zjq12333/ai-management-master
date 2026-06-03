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
    assert "function submitComposerPrompt" in text
    assert "function composerContainsPrompt" in text
    assert "接管提示仍停留在输入框，未成功发送" in text
    assert "自动打开新对话失败" in text
    assert "已复制接管提示" in text
    assert "await copyTextToClipboard(prompt)" in text

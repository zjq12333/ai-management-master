import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";

type EnhancerInternals = {
  findReadySendButton: (composer?: HTMLElement | null) => HTMLButtonElement | null;
  setComposerValue: (composer: HTMLElement, value: string) => void;
  submitComposerPrompt: (composer: HTMLElement, prompt: string) => Promise<void>;
};

declare global {
  interface Window {
    __aiStrategistEnhancerInternals?: EnhancerInternals;
    __aiStrategistEnhancerObserver?: MutationObserver;
  }
}

const loadRendererInject = async () => {
  document.body.innerHTML = "<main></main>";
  vi.resetModules();
  await import("../../../../enhancer_renderer_inject.js?raw").then(({ default: script }) => {
    window.eval(script);
  });
  return window.__aiStrategistEnhancerInternals as EnhancerInternals;
};

const visibleRect = (node: Element) => {
  Object.defineProperty(node, "getBoundingClientRect", {
    configurable: true,
    value: () => ({
      width: 32,
      height: 32,
      top: 0,
      left: 0,
      right: 32,
      bottom: 32,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }),
  });
};

afterEach(() => {
  window.__aiStrategistEnhancerObserver?.disconnect?.();
  window.__aiStrategistEnhancerInternals = undefined;
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("renderer one-click handoff submit helpers", () => {
  it("writes contenteditable composers with beforeinput and input events", async () => {
    const internals = await loadRendererInject();
    const composer = document.createElement("div");
    composer.setAttribute("contenteditable", "true");
    visibleRect(composer);
    document.body.appendChild(composer);
    const events: string[] = [];
    composer.addEventListener("beforeinput", () => events.push("beforeinput"));
    composer.addEventListener("input", () => events.push("input"));

    internals.setComposerValue(composer, "take over the next phase");

    expect(composer).toHaveTextContent("take over the next phase");
    expect(events).toEqual(["beforeinput", "input"]);
  });

  it("waits for an enabled send button near the composer before clicking", async () => {
    vi.useFakeTimers();
    const internals = await loadRendererInject();
    const form = document.createElement("form");
    const composer = document.createElement("textarea");
    const send = document.createElement("button");
    send.type = "submit";
    send.disabled = true;
    visibleRect(composer);
    visibleRect(send);
    form.append(composer, send);
    document.body.appendChild(form);
    internals.setComposerValue(composer, "handoff prompt");
    const clicked = vi.fn();
    send.addEventListener("click", () => {
      clicked();
      composer.value = "";
    });

    const promise = internals.submitComposerPrompt(composer, "handoff prompt");
    await vi.advanceTimersByTimeAsync(300);
    expect(clicked).not.toHaveBeenCalled();
    send.disabled = false;
    await vi.advanceTimersByTimeAsync(1_000);
    await promise;

    expect(clicked).toHaveBeenCalled();
    vi.useRealTimers();
  });
});

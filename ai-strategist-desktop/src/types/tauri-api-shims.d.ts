declare module "@tauri-apps/api/core" {
  export function invoke<T = unknown>(cmd: string, args?: Record<string, unknown>): Promise<T>;
}

declare module "@tauri-apps/api/app" {
  export function getVersion(): Promise<string>;
}

declare module "@tauri-apps/api/window" {
  export interface TauriWindow {
    label: string;
    minimize?: () => Promise<void>;
    toggleMaximize?: () => Promise<void>;
    close?: () => Promise<void>;
  }

  export function getCurrentWindow(): TauriWindow;
}

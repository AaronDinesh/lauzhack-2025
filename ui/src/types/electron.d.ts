export {};

declare global {
  interface Window {
    electronAPI?: {
      togglePanel: (url?: string) => Promise<boolean>;
      loadPanel: (url?: string) => Promise<boolean>;
      resizePanel: (fraction: number, topOffset?: number) => Promise<{ panelSplit: number; controlBarOffset: number }>;
      detachPanel: () => Promise<{ panelVisible: boolean; panelAttached: boolean }>;
      attachPanel: () => Promise<{ panelVisible: boolean; panelAttached: boolean }>;
      capturePanel: () => Promise<string | null>;
      sendFrame: (bytes: Uint8Array | ArrayBuffer) => Promise<boolean>;
      setFrameEndpoint: (endpoint: string) => Promise<string>;
    };
  }
}

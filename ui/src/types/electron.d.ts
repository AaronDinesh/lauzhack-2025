export {};

declare global {
  interface Window {
    electronAPI?: {
      togglePanel: (url?: string) => Promise<boolean>;
      loadPanel: (url?: string) => Promise<boolean>;
    };
  }
}

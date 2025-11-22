'use client';

import { useCallback, useEffect, useState } from 'react';
import CameraView from '@/components/CameraView';
import WebPanel from '@/components/WebPanel';
import ControlBar from '@/components/ControlBar';
import { useMXBridge } from '@/hooks/useMXBridge';

export default function Home() {
  const sanitizeUrl = (value?: string) => {
    const trimmed = value?.trim();
    return trimmed && trimmed.length > 0 ? trimmed : undefined;
  };

  const initialPanelUrl =
    sanitizeUrl(process.env.NEXT_PUBLIC_PANEL_URL) || 'https://example.com';
  const [panelVisible, setPanelVisible] = useState(false);
  const [panelUrl, setPanelUrl] = useState<string>(initialPanelUrl);
  const [isElectron, setIsElectron] = useState(false);
  const [bridgeEndpoint, setBridgeEndpoint] = useState(
    process.env.NEXT_PUBLIC_MX_BRIDGE_URL || 'http://127.0.0.1:8000/stream'
  );
  const [mockMode, setMockMode] = useState(false);
  const [dockSide, setDockSide] = useState<'left' | 'right'>('right');
  const [workspaceSplit, setWorkspaceSplit] = useState(70); // percentage for camera

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsElectron(Boolean(window.electronAPI));
    }
  }, []);

  const resolveUrl = useCallback(
    (urlCandidate?: string) => {
      return sanitizeUrl(urlCandidate) || sanitizeUrl(panelUrl) || initialPanelUrl;
    },
    [panelUrl, initialPanelUrl]
  );

  const showPanelWithUrl = useCallback(
    async (url: string) => {
      const resolved = resolveUrl(url);
      setPanelUrl(resolved);
      if (isElectron && window.electronAPI?.loadPanel) {
        await window.electronAPI.loadPanel(resolved);
        setPanelVisible(true);
        return;
      }
      setPanelVisible(true);
    },
    [isElectron, resolveUrl]
  );

  const togglePanelVisibility = useCallback(
    async (urlOverride?: string) => {
      const urlToUse = resolveUrl(urlOverride);
      if (isElectron && window.electronAPI?.togglePanel) {
        const visible = await window.electronAPI.togglePanel(urlToUse);
        setPanelVisible(visible);
        return;
      }
      setPanelVisible((prev) => !prev);
    },
    [isElectron, resolveUrl]
  );

  // Connect to MX Bridge via SSE
  const { connected, error: bridgeError } = useMXBridge(bridgeEndpoint, {
    onSetUrl: (url: string) => {
      showPanelWithUrl(url);
    },
    onTogglePanel: () => {
      togglePanelVisibility();
    },
    onTriggerStep: (step: string) => {
      console.log('[MX Action] Trigger step:', step);
    },
    onSetLayout: (layout: { dockSide?: 'left' | 'right'; workspaceSplit?: number }) => {
      if (layout.dockSide) setDockSide(layout.dockSide);
      if (layout.workspaceSplit) setWorkspaceSplit(layout.workspaceSplit);
    },
    onSetMockMode: (enabled: boolean) => {
      setMockMode(enabled);
    },
    onSetBridgeEndpoint: (endpoint: string) => {
      setBridgeEndpoint(endpoint);
    },
  });

  const handleMockSetUrl = useCallback(() => {
    if (!mockMode) return;
    showPanelWithUrl('https://www.example.com');
  }, [mockMode, showPanelWithUrl]);

  return (
    <div className="flex flex-col h-screen w-screen bg-darker text-white overflow-hidden">
      {/* Top Control Bar */}
      <ControlBar
        connected={connected}
        bridgeError={bridgeError}
        bridgeEndpoint={bridgeEndpoint}
        mockMode={mockMode}
        panelUrl={panelUrl}
        panelVisible={panelVisible}
        onSetBridgeEndpoint={setBridgeEndpoint}
        onToggleMockMode={() => setMockMode(!mockMode)}
        onMockSetUrl={handleMockSetUrl}
        onPanelUrlChange={setPanelUrl}
        onTogglePanel={togglePanelVisibility}
        onSearchPanel={showPanelWithUrl}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {dockSide === 'left' && panelVisible && !isElectron && (
          <WebPanel
            url={panelUrl}
            onClose={() => setPanelVisible(false)}
            width={100 - workspaceSplit}
          />
        )}

        <CameraView
          width={panelVisible && !isElectron ? workspaceSplit : 100}
        />

        {dockSide === 'right' && panelVisible && !isElectron && (
          <WebPanel
            url={panelUrl}
            onClose={() => setPanelVisible(false)}
            width={100 - workspaceSplit}
          />
        )}
      </div>
    </div>
  );
}

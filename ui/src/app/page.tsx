'use client';

import { useState } from 'react';
import CameraView from '@/components/CameraView';
import WebPanel from '@/components/WebPanel';
import ControlBar from '@/components/ControlBar';
import { useMXBridge } from '@/hooks/useMXBridge';

export default function Home() {
  const [panelVisible, setPanelVisible] = useState(false);
  const [panelUrl, setPanelUrl] = useState<string>('');
  const [bridgeEndpoint, setBridgeEndpoint] = useState(
    process.env.NEXT_PUBLIC_MX_BRIDGE_URL || 'http://127.0.0.1:8000/stream'
  );
  const [mockMode, setMockMode] = useState(false);
  const [dockSide, setDockSide] = useState<'left' | 'right'>('right');
  const [workspaceSplit, setWorkspaceSplit] = useState(70); // percentage for camera

  // Connect to MX Bridge via SSE
  const { connected, error: bridgeError } = useMXBridge(bridgeEndpoint, {
    onSetUrl: (url: string) => {
      setPanelUrl(url);
      setPanelVisible(true);
    },
    onTogglePanel: () => {
      setPanelVisible((prev) => !prev);
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

  const handleMockSetUrl = () => {
    if (mockMode) {
      setPanelUrl('https://www.example.com');
      setPanelVisible(true);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-darker text-white overflow-hidden">
      {/* Top Control Bar */}
      <ControlBar
        connected={connected}
        bridgeError={bridgeError}
        bridgeEndpoint={bridgeEndpoint}
        mockMode={mockMode}
        onSetBridgeEndpoint={setBridgeEndpoint}
        onToggleMockMode={() => setMockMode(!mockMode)}
        onMockSetUrl={handleMockSetUrl}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {dockSide === 'left' && panelVisible && (
          <WebPanel
            url={panelUrl}
            onClose={() => setPanelVisible(false)}
            width={100 - workspaceSplit}
          />
        )}

        <CameraView
          width={panelVisible ? workspaceSplit : 100}
        />

        {dockSide === 'right' && panelVisible && (
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


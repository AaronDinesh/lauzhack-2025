'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import CameraView from '@/components/CameraView';
import WebPanel from '@/components/WebPanel';
import ControlBar from '@/components/ControlBar';
import StatusDock, { StatusItem } from '@/components/StatusDock';
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
  const [isResizing, setIsResizing] = useState(false);
  const [controlBarHeight, setControlBarHeight] = useState(0);
  const [isElectron, setIsElectron] = useState(false);
  const [bridgeEndpoint, setBridgeEndpoint] = useState(
    process.env.NEXT_PUBLIC_MX_BRIDGE_URL || 'http://127.0.0.1:8000/stream'
  );
  const [mockMode, setMockMode] = useState(false);
  const [dockSide, setDockSide] = useState<'left' | 'right'>('right');
  const [workspaceSplit, setWorkspaceSplit] = useState(70); // percentage for camera
  const workspaceRef = useRef<HTMLDivElement>(null);
  const controlBarRef = useRef<HTMLDivElement>(null);
  const HANDLE_WIDTH = 8; // px
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsElectron(Boolean(window.electronAPI));
    }
  }, []);

  useLayoutEffect(() => {
    if (!controlBarRef.current) return;
    const updateHeight = () => {
      setControlBarHeight(controlBarRef.current?.getBoundingClientRect().height || 0);
    };
    updateHeight();

    const observer = new ResizeObserver(updateHeight);
    observer.observe(controlBarRef.current);

    return () => observer.disconnect();
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
        if (visible && window.electronAPI?.resizePanel) {
          // Keep Electron panel width in sync with workspace split
          await window.electronAPI.resizePanel(
            (100 - workspaceSplit) / 100,
            controlBarHeight
          );
        }
        return;
      }
      setPanelVisible((prev) => !prev);
    },
    [controlBarHeight, isElectron, resolveUrl, workspaceSplit]
  );

  // Connect to MX Bridge via SSE
  const { connected, error: bridgeError } = useMXBridge(bridgeEndpoint, {
    onSetUrl: (url: string) => {
      showPanelWithUrl(url);
      pushStatus({ label: 'Opening resource', detail: url, tone: 'info' });
    },
    onTogglePanel: () => {
      togglePanelVisibility();
      pushStatus({ label: panelVisible ? 'Hiding panel' : 'Showing panel', tone: 'info' });
    },
    onTriggerStep: (step: string) => {
      console.log('[MX Action] Trigger step:', step);
      handleStepStatus(step);
    },
    onSetLayout: (layout: { dockSide?: 'left' | 'right'; workspaceSplit?: number }) => {
      if (layout.dockSide) setDockSide(layout.dockSide);
      if (layout.workspaceSplit) setWorkspaceSplit(layout.workspaceSplit);
      pushStatus({
        label: 'Layout updated',
        detail: `Dock: ${layout.dockSide || dockSide}, Camera: ${layout.workspaceSplit ?? workspaceSplit}%`,
        tone: 'info',
      });
    },
    onSetMockMode: (enabled: boolean) => {
      setMockMode(enabled);
      pushStatus({ label: 'Mock mode', detail: enabled ? 'Enabled' : 'Disabled', tone: enabled ? 'warning' : 'info' });
    },
    onSetBridgeEndpoint: (endpoint: string) => {
      setBridgeEndpoint(endpoint);
      pushStatus({ label: 'Bridge endpoint updated', detail: endpoint, tone: 'info' });
    },
  });

  const handleMockSetUrl = useCallback(() => {
    if (!mockMode) return;
    showPanelWithUrl('https://www.example.com');
  }, [mockMode, showPanelWithUrl]);

  const [panelWasVisibleBeforeSettings, setPanelWasVisibleBeforeSettings] = useState(false);
  const [panelSnapshot, setPanelSnapshot] = useState<string | null>(null);
  const [panelDetachedForSettings, setPanelDetachedForSettings] = useState(false);
  const [statusItems, setStatusItems] = useState<StatusItem[]>([]);
  const [isRecording, setIsRecording] = useState(false);

  const pushStatus = useCallback(
    (item: Omit<StatusItem, 'id' | 'ts'> & { id?: string; ts?: number }) => {
      setStatusItems((prev) => {
        const id = item.id || `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
        const ts = item.ts || Date.now();
        return [{ ...item, id, ts }, ...prev].slice(0, 15);
      });
    },
    []
  );

  const handleStepStatus = useCallback(
    (step: string) => {
      const normalized = step.toLowerCase();

      if (normalized.includes('talk_start') || normalized === 'talk_start') {
        setIsRecording(true);
        pushStatus({ label: 'Recording…', tone: 'warning' });
        return;
      }

      if (normalized.includes('talk_stop') || normalized === 'talk_stop') {
        setIsRecording(false);
        pushStatus({ label: 'Stopped recording', tone: 'info' });
        return;
      }

      if (normalized.startsWith('resource_')) {
        pushStatus({ label: 'Opening resource', detail: normalized, tone: 'success' });
        return;
      }

      pushStatus({ label: step, tone: 'info' });
    },
    [pushStatus]
  );

  const handleSettingsVisibilityChange = useCallback(
    (open: boolean) => {
      setSettingsOpen(open);
      if (open) {
        if (panelVisible && isElectron && window.electronAPI) {
          setPanelWasVisibleBeforeSettings(true);
          // Detach immediately so overlay covers both areas at once.
          window.electronAPI.detachPanel();
          setPanelDetachedForSettings(true);
          // Capture asynchronously without blocking the overlay.
          void window.electronAPI
            .capturePanel()
            .then((snapshot) => snapshot && setPanelSnapshot(snapshot))
            .catch(() => {});
        } else {
          setPanelWasVisibleBeforeSettings(false);
        }
      } else {
        if (panelDetachedForSettings && window.electronAPI) {
          void window.electronAPI.attachPanel();
        }
        setPanelSnapshot(null);
        setPanelDetachedForSettings(false);
        setPanelWasVisibleBeforeSettings(false);
      }
    },
    [isElectron, panelDetachedForSettings, panelVisible]
  );

  const startResize = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (event: MouseEvent) => {
      if (!workspaceRef.current) return;
      const rect = workspaceRef.current.getBoundingClientRect();
      const relativeX = event.clientX - rect.left;
      const ratio = relativeX / rect.width;
      const clamped = Math.min(Math.max(ratio, 0.2), 0.8);
      const cameraPercent = Math.round(clamped * 100);

      setWorkspaceSplit(cameraPercent);

      if (isElectron && panelVisible && window.electronAPI?.resizePanel) {
        window.electronAPI.resizePanel(1 - clamped, controlBarHeight);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isElectron, isResizing, panelVisible]);

  return (
    <div className="flex flex-col h-screen w-screen bg-darker text-white overflow-hidden">
      {/* Top Control Bar */}
      <ControlBar
        ref={controlBarRef}
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
        onSettingsVisibilityChange={handleSettingsVisibilityChange}
      />

      {/* Main Content Area */}
      <div
        className="grid flex-1 overflow-hidden"
        ref={workspaceRef}
        style={{
      gridTemplateColumns: panelVisible
            ? dockSide === 'left'
              ? `calc(${100 - workspaceSplit}% - ${HANDLE_WIDTH}px) ${HANDLE_WIDTH}px ${workspaceSplit}%`
              : `${workspaceSplit}% ${HANDLE_WIDTH}px calc(${100 - workspaceSplit}% - ${HANDLE_WIDTH}px)`
            : '100%',
    }}
  >
        {dockSide === 'left' && panelVisible && (
          <>
            {!isElectron ? (
              <WebPanel
                url={panelUrl}
                onClose={() => setPanelVisible(false)}
                width={100}
              />
            ) : panelSnapshot && settingsOpen ? (
              <img src={panelSnapshot} alt="Panel snapshot" className="w-full h-full object-cover" />
            ) : (
              <div
                className="bg-dark border-r border-gray-800"
                title="External panel (Electron)"
              />
            )}

            <div
              onMouseDown={startResize}
              className="cursor-col-resize bg-gray-800 hover:bg-gray-700 transition-colors"
              style={{ width: HANDLE_WIDTH }}
              title="Drag to resize panel"
            />
          </>
        )}

        <div className="min-w-0">
          <CameraView width={100} />
        </div>

        {dockSide === 'right' && panelVisible && (
          <>
            <div
              onMouseDown={startResize}
              className="cursor-col-resize bg-gray-800 hover:bg-gray-700 transition-colors"
              style={{ width: HANDLE_WIDTH }}
              title="Drag to resize panel"
            />

            {!isElectron ? (
              <WebPanel
                url={panelUrl}
                onClose={() => setPanelVisible(false)}
                width={100}
              />
            ) : panelSnapshot && settingsOpen ? (
              <img src={panelSnapshot} alt="Panel snapshot" className="w-full h-full object-cover" />
            ) : (
              <div
                className="bg-dark border-l border-gray-800"
                title="External panel (Electron)"
              />
            )}
          </>
        )}
      </div>

      {settingsOpen && (
        <div className="fixed inset-0 z-[9500] bg-black/60 pointer-events-auto" />
      )}

      <StatusDock
        items={statusItems}
        recording={isRecording}
        onClear={() => setStatusItems([])}
      />
    </div>
  );
}

'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useDebouncedCallback } from 'use-debounce';
import CameraView from '@/components/CameraView';
import WebPanel from '@/components/WebPanel';
import ControlBar from '@/components/ControlBar';
import StatusDock, { StatusItem } from '@/components/StatusDock';
import { useMXBridge, SegmentationEventPayload } from '@/hooks/useMXBridge';

export default function Home() {
  const sanitizeUrl = (value?: string) => {
    const trimmed = value?.trim();
    return trimmed && trimmed.length > 0 ? trimmed : undefined;
  };

  const initialPanelUrl =
    sanitizeUrl(process.env.NEXT_PUBLIC_PANEL_URL) || 'https://google.com';
  const [panelVisible, setPanelVisible] = useState(false);
  const [panelUrl, setPanelUrl] = useState<string>(initialPanelUrl);
  const [isResizing, setIsResizing] = useState(false);
  const [controlBarHeight, setControlBarHeight] = useState(0);
  const [isElectron, setIsElectron] = useState(false);
  const [bridgeEndpoint, setBridgeEndpoint] = useState(
    process.env.NEXT_PUBLIC_MX_BRIDGE_URL || ''
  );
  const DEFAULT_BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND_URL);
  const DEFAULT_FRAME_ENDPOINT = process.env.NEXT_PUBLIC_FRAME_ENDPOINT || 'tcp://127.0.0.1:5557';
  const [frameEndpoint, setFrameEndpoint] = useState(DEFAULT_FRAME_ENDPOINT);
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

  useEffect(() => {
    if (typeof window !== 'undefined' && window.electronAPI?.setFrameEndpoint) {
      window.electronAPI.setFrameEndpoint(frameEndpoint);
    }
  }, [frameEndpoint]);

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

  useEffect(() => {
    if (!isElectron || !panelVisible || !window.electronAPI?.resizePanel) {
      return;
    }
    const panelFraction = (100 - workspaceSplit) / 100;
    window.electronAPI.resizePanel(panelFraction, controlBarHeight);
  }, [workspaceSplit, controlBarHeight, isElectron, panelVisible]);

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

      // Handle workspace split with smooth resizing
      if (typeof layout.workspaceSplit === 'number') {
        // Calculate delta from current position
        const currentSplit = workspaceSplit;
        const rawDelta = layout.workspaceSplit - currentSplit;

        // Clamp each update to ±5% to avoid big jumps
        const clampedDelta = Math.max(-5, Math.min(5, rawDelta));
        pendingDelta.current += clampedDelta;

        // Update UI instantly for smooth feel
        setWorkspaceSplit(prev => {
          const newVal = Math.max(20, Math.min(80, prev + clampedDelta));

          // Also inform the Electron host (if present)
          if (isElectron && panelVisible && window.electronAPI?.resizePanel) {
            const clamped = Math.min(Math.max(newVal / 100, 0.2), 0.8);
            window.electronAPI.resizePanel(1 - clamped, controlBarHeight);
          }

          return newVal;
        });

        // Debounced request to backend
        debounceSend();
      }
    },
    onSetMockMode: (enabled: boolean) => {
      setMockMode(enabled);
      pushStatus({ label: 'Mock mode', detail: enabled ? 'Enabled' : 'Disabled', tone: enabled ? 'warning' : 'info' });
    },
    onSetBridgeEndpoint: (endpoint: string) => {
      setBridgeEndpoint(endpoint);
      pushStatus({ label: 'Bridge endpoint updated', detail: endpoint, tone: 'info' });
    },
<<<<<<< Updated upstream
    onSegmentationData: handleSegmentationData,
    onSegmentationVisible: handleSegmentationVisible,
=======
    onScrollVertical: (delta: number) => {
      // Dispatch a custom event that the WebPanel iframe can listen to
      window.dispatchEvent(new CustomEvent('scroll-panel', { detail: { delta } }));
    },
>>>>>>> Stashed changes
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
  const [segmentationData, setSegmentationData] = useState<SegmentationEventPayload | null>(null);
  const [segmentationVisible, setSegmentationVisible] = useState(false);
  const [segmentationLoading, setSegmentationLoading] = useState(false);
  const [segmentationError, setSegmentationError] = useState<string | null>(null);
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);
  const lastModeRef = useRef<string | null>(null);
  const lastTranscriptRef = useRef<string | null>(null);
  const lastResponseRef = useRef<string | null>(null);
  const pendingDelta = useRef(0); // accumulated dial delta for smooth resizing

  // Debounced callback to send accumulated resize delta to backend
  const debounceSend = useDebouncedCallback(() => {
    if (pendingDelta.current === 0) return;
    // Send a single resize_panel action with the accumulated delta
    fetch(`${backendUrl.replace(/\/$/, '')}/console/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'resize_panel', value: pendingDelta.current }),
    });
    pendingDelta.current = 0; // reset after sending
  }, 100); // 100 ms debounce

  const normalizeSegmentationPayload = useCallback((raw?: any): SegmentationEventPayload | null => {
    if (!raw || typeof raw !== 'object') {
      return null;
    }
    return {
      prompt: raw.prompt,
      imageData: raw.imageData || raw.image_data,
      numObjects: raw.numObjects ?? raw.num_objects,
      scores: raw.scores,
      timestamp: raw.timestamp,
    };
  }, []);

  const fetchLatestSegmentation = useCallback(async () => {
    if (!backendUrl || !backendUrl.trim()) {
      return null;
    }
    setSegmentationLoading(true);
    setSegmentationError(null);
    try {
      const res = await fetch(`${backendUrl.replace(/\/$/, '')}/segmentation/latest`);
      if (!res.ok) {
        if (res.status === 404) {
          setSegmentationData(null);
          return null;
        }
        throw new Error(`Failed to fetch segmentation (${res.status})`);
      }
      const json = await res.json();
      const normalized = normalizeSegmentationPayload(json);
      setSegmentationData(normalized);
      return normalized;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load segmentation overlay.';
      setSegmentationError(message);
      return null;
    } finally {
      setSegmentationLoading(false);
    }
  }, [backendUrl, normalizeSegmentationPayload]);

  const sendSegmentationToggle = useCallback(
    async (forceValue?: boolean) => {
      if (!backendUrl || !backendUrl.trim()) {
        return;
      }
      try {
        const payload: Record<string, any> = { action: 'toggle_segmentation_overlay' };
        if (typeof forceValue === 'boolean') {
          payload.value = forceValue ? 1 : 0;
        }
        await fetch(`${backendUrl.replace(/\/$/, '')}/console/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        console.error('Failed to toggle segmentation overlay:', err);
        setSegmentationError('Unable to toggle segmentation overlay.');
      }
    },
    [backendUrl]
  );

  const handleSegmentationData = useCallback(
    (payload: SegmentationEventPayload) => {
      const normalized = normalizeSegmentationPayload(payload);
      if (!normalized) return;
      setSegmentationData(normalized);
      setSegmentationError(null);
    },
    [normalizeSegmentationPayload]
  );

  const handleSegmentationVisible = useCallback(
    (visible: boolean) => {
      setSegmentationVisible(visible);
      if (visible && !segmentationData) {
        void fetchLatestSegmentation();
      }
    },
    [fetchLatestSegmentation, segmentationData]
  );

  const handleSegmentationButton = useCallback(() => {
    void sendSegmentationToggle(segmentationVisible ? false : true);
  }, [segmentationVisible, sendSegmentationToggle]);

  const handleSegmentationClose = useCallback(() => {
    void sendSegmentationToggle(false);
  }, [sendSegmentationToggle]);

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
        pushStatus({ label: 'Recording...', tone: 'warning' });
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

  useEffect(() => {
    const pollStatus = async () => {
      if (!backendUrl || !backendUrl.trim()) {
        return;
      }
      try {
        const res = await fetch(`${backendUrl.replace(/\/$/, '')}/status`);
        if (!res.ok) return;
        const data = await res.json();
        if (typeof data === 'object' && data) {
          if (typeof data.talking === 'boolean') {
            setIsRecording(Boolean(data.talking));
          }
          if (data.mode && data.mode !== lastModeRef.current) {
            lastModeRef.current = data.mode;
            pushStatus({
              label: `Mode: ${data.mode}`,
              tone: data.mode === 'talking' ? 'warning' : 'info',
            });
          }
          if (data.last_transcript && data.last_transcript !== lastTranscriptRef.current) {
            lastTranscriptRef.current = data.last_transcript;
            pushStatus({ label: 'You said', detail: data.last_transcript, tone: 'info' });
          }
          if (data.last_response && data.last_response !== lastResponseRef.current) {
            lastResponseRef.current = data.last_response;
            pushStatus({ label: 'Jarvis responded', detail: data.last_response, tone: 'success' });
          }
          if (typeof data.workspace_split === 'number' && Number.isFinite(data.workspace_split)) {
            setWorkspaceSplit((prev) =>
              Math.abs(prev - data.workspace_split) < 0.1 ? prev : data.workspace_split
            );
          }
          if (typeof data.segmentation_visible === 'boolean') {
            setSegmentationVisible((prev) =>
              data.segmentation_visible === prev ? prev : data.segmentation_visible
            );
          }
          if (data.segmentation_available) {
            if (!segmentationData && !segmentationLoading) {
              void fetchLatestSegmentation();
            }
          } else if (segmentationData) {
            setSegmentationData(null);
          }
        }
      } catch (err) {
        console.error('Failed to fetch status:', err);
      }
    };

    pollStatus();
    statusPollRef.current = setInterval(pollStatus, 500);
    return () => {
      if (statusPollRef.current) {
        clearInterval(statusPollRef.current);
      }
    };
  }, [backendUrl, fetchLatestSegmentation, pushStatus, segmentationData, segmentationLoading]);

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
            .catch(() => { });
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
        backendUrl={backendUrl}
        frameEndpoint={frameEndpoint}
        mockMode={mockMode}
        panelUrl={panelUrl}
        panelVisible={panelVisible}
        onSetBridgeEndpoint={setBridgeEndpoint}
        onSetBackendUrl={setBackendUrl}
        onSetFrameEndpoint={setFrameEndpoint}
        onToggleMockMode={() => setMockMode(!mockMode)}
        onMockSetUrl={handleMockSetUrl}
        onPanelUrlChange={setPanelUrl}
        onTogglePanel={togglePanelVisibility}
        onSearchPanel={showPanelWithUrl}
        onSettingsVisibilityChange={handleSettingsVisibilityChange}
      />

      {/* Main Content Area */}
      <div
        className="grid flex-1"
        ref={workspaceRef}
        style={{
          gridTemplateColumns: panelVisible
            ? dockSide === 'left'
              ? `calc(${100 - workspaceSplit}% - ${HANDLE_WIDTH}px) ${HANDLE_WIDTH}px ${workspaceSplit}%`
              : `${workspaceSplit}% ${HANDLE_WIDTH}px calc(${100 - workspaceSplit}% - ${HANDLE_WIDTH}px)`
            : '100%',
          overflow: 'hidden',
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
          <CameraView width={100} frameEndpoint={frameEndpoint} />
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

      {segmentationData && !segmentationVisible && (
        <button
          className="btn btn-primary fixed bottom-6 right-6 z-[9300] shadow-lg"
          onClick={handleSegmentationButton}
          disabled={segmentationLoading}
        >
          {segmentationLoading ? 'Preparing overlay...' : 'Show Segmentation'}
        </button>
      )}

      {segmentationVisible && (
        <div className="fixed inset-0 z-[9600] flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-black/70" onClick={handleSegmentationClose} />
          <div className="relative z-[9601] w-[min(900px,100%)] max-h-[90vh] bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden pointer-events-auto">
            <div className="flex items-start justify-between gap-4 px-6 py-4 border-b border-gray-800">
              <div>
                <div className="text-xs uppercase tracking-wide text-gray-400">Segmentation</div>
                <div className="text-lg font-semibold">{segmentationData?.prompt || 'Latest overlay'}</div>
                <div className="text-sm text-gray-400">
                  {segmentationData?.numObjects != null
                    ? `${segmentationData.numObjects} object${segmentationData.numObjects === 1 ? '' : 's'} detected`
                    : 'Awaiting detection results'}
                </div>
              </div>
              <button className="btn btn-secondary" onClick={handleSegmentationClose}>
                Close
              </button>
            </div>
            <div className="p-6 overflow-y-auto bg-black/20">
              {segmentationLoading ? (
                <div className="text-center text-gray-300 py-8">Loading segmentation overlay...</div>
              ) : segmentationData?.imageData ? (
                <img
                  src={segmentationData.imageData}
                  alt={segmentationData?.prompt || 'Segmentation overlay'}
                  className="w-full rounded-xl border border-gray-800 object-contain"
                />
              ) : (
                <div className="text-center text-gray-400 py-8">
                  No segmentation image available yet. Trigger the tool from Jarvis to generate one.
                </div>
              )}
              {segmentationError && (
                <div className="mt-4 text-sm text-red-400 text-center">{segmentationError}</div>
              )}
            </div>
          </div>
        </div>
      )}

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

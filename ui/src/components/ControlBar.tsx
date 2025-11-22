'use client';

import { forwardRef, useEffect, useState } from 'react';

interface ControlBarProps {
  connected: boolean;
  bridgeError: string | null;
  bridgeEndpoint: string;
  mockMode: boolean;
  panelUrl: string;
  panelVisible: boolean;
  onSetBridgeEndpoint: (endpoint: string) => void;
  onToggleMockMode: () => void;
  onMockSetUrl: () => void;
  onPanelUrlChange: (url: string) => void;
  onTogglePanel: (url?: string) => void;
  onSearchPanel: (url: string) => void;
}

const ControlBar = forwardRef<HTMLDivElement, ControlBarProps>(function ControlBar(
{
  connected,
  bridgeError,
  bridgeEndpoint,
  mockMode,
  panelUrl,
  panelVisible,
  onSetBridgeEndpoint,
  onToggleMockMode,
  onMockSetUrl,
  onPanelUrlChange,
  onTogglePanel,
  onSearchPanel,
},
ref) {
  const [showSettings, setShowSettings] = useState(false);
  const [endpointInput, setEndpointInput] = useState(bridgeEndpoint);
  const [panelUrlInput, setPanelUrlInput] = useState(panelUrl);

  useEffect(() => {
    setEndpointInput(bridgeEndpoint);
  }, [bridgeEndpoint]);

  useEffect(() => {
    setPanelUrlInput(panelUrl);
  }, [panelUrl]);

  const handleSaveEndpoint = () => {
    onSetBridgeEndpoint(endpointInput);
    setShowSettings(false);
  };

  return (
    <div
      ref={ref}
      className="flex flex-wrap items-center gap-4 px-6 py-3 bg-dark border-b border-gray-800"
    >
      {/* App Title */}
      <div className="flex items-center gap-2">
        <span className="text-xl">🔧</span>
        <h1 className="text-lg font-bold">MX Repair Desktop</h1>
      </div>

      {/* Bridge Status */}
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            connected ? 'bg-green-500' : 'bg-red-500'
          }`}
          title={connected ? 'Connected to MX Bridge' : 'Disconnected'}
        />
        <span className="text-sm text-gray-400">
          {connected ? 'Bridge Connected' : bridgeError || 'Disconnected'}
        </span>
      </div>

      {/* Mock Mode */}
      {mockMode && (
        <>
          <div className="px-3 py-1 bg-yellow-900/50 text-yellow-400 text-xs rounded-full border border-yellow-700">
            Mock Mode Active
          </div>
          <button
            onClick={onMockSetUrl}
            className="px-3 py-1 text-sm bg-yellow-700 hover:bg-yellow-600 rounded transition-colors"
          >
            Test setUrl
          </button>
        </>
      )}

      {/* Panel Controls */}
      <div className="flex items-center gap-2 ml-auto bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2">
        <input
          type="text"
          value={panelUrlInput}
          onChange={(e) => setPanelUrlInput(e.target.value)}
          placeholder="https://example.com"
          className="w-64 px-3 py-1 bg-gray-900 border border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-primary text-sm"
        />
        <button
          onClick={() => {
            onPanelUrlChange(panelUrlInput);
            onSearchPanel(panelUrlInput);
          }}
          className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 rounded transition-colors"
        >
          Search
        </button>
        <button
          onClick={() => {
            onPanelUrlChange(panelUrlInput);
            onTogglePanel(panelUrlInput);
          }}
          className="px-3 py-1 text-sm bg-blue-700 hover:bg-blue-600 rounded transition-colors"
        >
          {panelVisible ? 'Hide Panel' : 'Show Panel'}
        </button>
      </div>

      {/* Settings Button */}
      <button
        onClick={() => setShowSettings(!showSettings)}
        className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 rounded transition-colors"
        title="Settings"
      >
        ⚙️ Settings
      </button>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-dark border border-gray-700 rounded-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-4">Settings</h2>

            {/* Bridge Endpoint */}
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">
                MX Bridge Endpoint (SSE)
              </label>
              <input
                type="text"
                value={endpointInput}
                onChange={(e) => setEndpointInput(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="http://127.0.0.1:8000/stream"
              />
            </div>

            {/* Mock Mode Toggle */}
            <div className="mb-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={mockMode}
                  onChange={onToggleMockMode}
                  className="w-4 h-4"
                />
                <span className="text-sm">Enable Mock Mode (for testing)</span>
              </label>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <button
                onClick={handleSaveEndpoint}
                className="flex-1 btn btn-primary"
              >
                Save
              </button>
              <button
                onClick={() => {
                  setEndpointInput(bridgeEndpoint);
                  setShowSettings(false);
                }}
                className="flex-1 btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

export default ControlBar;

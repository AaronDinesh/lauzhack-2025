'use client';

import { useState, useEffect } from 'react';

interface WebPanelProps {
  url: string;
  onClose: () => void;
  width: number; // percentage
}

export default function WebPanel({ url, onClose, width }: WebPanelProps) {
  const [normalizedUrl, setNormalizedUrl] = useState('');
  const [iframeError, setIframeError] = useState(false);

  useEffect(() => {
    if (!url) {
      setNormalizedUrl('');
      return;
    }

    let normalized = url.trim();

    // YouTube embed rewrite
    const youtubeMatch = normalized.match(
      /(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)/
    );
    if (youtubeMatch) {
      normalized = `https://www.youtube.com/embed/${youtubeMatch[1]}`;
    }
    // Add https if no protocol
    else if (!normalized.match(/^https?:\/\//)) {
      normalized = `https://${normalized}`;
    }

    setNormalizedUrl(normalized);
    setIframeError(false);
  }, [url]);

  const handleOpenExternal = () => {
    if (normalizedUrl) {
      window.open(normalizedUrl, '_blank');
    }
  };

  const handleIframeError = () => {
    setIframeError(true);
  };

  return (
    <div
      className="flex flex-col bg-dark border-l border-gray-800"
      style={{ width: `${width}%` }}
    >
      {/* Panel Header */}
      <div className="flex items-center gap-2 p-3 bg-dark border-b border-gray-800">
        <h3 className="text-sm font-medium truncate flex-1" title={normalizedUrl}>
          {normalizedUrl || 'No URL loaded'}
        </h3>

        <button
          onClick={handleOpenExternal}
          className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          title="Open in external browser"
        >
          🔗 Open externally
        </button>

        <button
          onClick={onClose}
          className="px-3 py-1 text-xs bg-red-600 hover:bg-red-700 rounded transition-colors"
          title="Close panel"
        >
          ✕ Close
        </button>
      </div>

      {/* Panel Content */}
      <div className="flex-1 relative bg-white">
        {!normalizedUrl ? (
          <div className="flex items-center justify-center h-full text-gray-700">
            <div className="text-center">
              <div className="text-4xl mb-3">🌐</div>
              <p>No URL loaded</p>
            </div>
          </div>
        ) : iframeError ? (
          <div className="flex items-center justify-center h-full text-gray-700">
            <div className="text-center max-w-md px-4">
              <div className="text-4xl mb-3">⚠️</div>
              <p className="font-semibold mb-2">Unable to load in iframe</p>
              <p className="text-sm text-gray-600 mb-4">
                This website blocks embedding. Click "Open externally" to view it in a browser.
              </p>
              <button
                onClick={handleOpenExternal}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                Open in Browser
              </button>
            </div>
          </div>
        ) : (
          <iframe
            key={normalizedUrl}
            src={normalizedUrl}
            className="w-full h-full border-0"
            sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            onError={handleIframeError}
            title="Web Panel"
          />
        )}
      </div>
    </div>
  );
}


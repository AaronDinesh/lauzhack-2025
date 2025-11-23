'use client';

import { useEffect, useRef, useState } from 'react';

interface CameraViewProps {
  width: number; // percentage
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

export default function CameraView({ width }: CameraViewProps) {
  const [error, setError] = useState<string>('');
  const [imgUrl, setImgUrl] = useState<string>('');
  const [refreshMs, setRefreshMs] = useState<number>(1000);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchFrame = async () => {
    try {
      const url = `${BACKEND_URL.replace(/\/$/, '')}/frame?ts=${Date.now()}`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      setImgUrl((prev) => {
        if (prev && prev.startsWith('blob:')) {
          URL.revokeObjectURL(prev);
        }
        return objectUrl;
      });
      setError('');
    } catch (err) {
      console.error('Failed to fetch frame:', err);
      setError('Unable to fetch camera frame');
    }
  };

  useEffect(() => {
    fetchFrame();
    intervalRef.current = setInterval(fetchFrame, refreshMs);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      setImgUrl((prev) => {
        if (prev && prev.startsWith('blob:')) {
          URL.revokeObjectURL(prev);
        }
        return '';
      });
    };
  }, [refreshMs]);

  return (
    <div
      className="flex flex-col bg-darker border-r border-gray-800"
      style={{ width: `${width}%` }}
    >
      <div className="flex items-center gap-3 p-4 bg-dark border-b border-gray-800">
        <h2 className="text-lg font-semibold">Camera Feed</h2>
        <div className="text-xs text-gray-400">Backend: {BACKEND_URL}</div>
        <div className="ml-auto flex items-center gap-2">
          <label className="text-xs text-gray-300">Refresh (ms)</label>
          <input
            type="number"
            min={200}
            step={200}
            value={refreshMs}
            onChange={(e) => setRefreshMs(Math.max(200, Number(e.target.value) || 1000))}
            className="w-20 px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs"
          />
          <button
            onClick={fetchFrame}
            className="btn btn-secondary text-sm"
            title="Refresh now"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 relative bg-black flex items-center justify-center">
        {error && (
          <div className="absolute top-4 left-4 right-4 bg-red-900/90 text-white px-4 py-2 rounded-lg z-10">
            {error}
          </div>
        )}
        {imgUrl ? (
          <img src={imgUrl} alt="Camera frame" className="max-w-full max-h-full object-contain" />
        ) : (
          <div className="text-gray-500 text-center">
            <div className="text-lg mb-2">Awaiting frame…</div>
            <p className="text-sm">Ensure the backend camera is running.</p>
          </div>
        )}
      </div>
    </div>
  );
}

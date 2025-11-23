'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

interface CameraViewProps {
  width: number; // percentage
  frameEndpoint: string;
}

const SNAPSHOT_INTERVAL_MS = 1000;

export default function CameraView({ width, frameEndpoint }: CameraViewProps) {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [cameraActive, setCameraActive] = useState(false);
  const [error, setError] = useState<string>('');

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sendIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const enumerateDevices = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.enumerateDevices) {
      setError('Camera API unavailable');
      return;
    }
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = all.filter((d) => d.kind === 'videoinput');
      setDevices(videoDevices);
      if (videoDevices.length > 0 && !selectedDeviceId) {
        setSelectedDeviceId(videoDevices[0].deviceId);
      }
    } catch (err) {
      console.error('Failed to enumerate devices:', err);
      setError('Unable to enumerate camera devices');
    }
  }, [selectedDeviceId]);

  const requestAccess = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setError('Camera API unavailable');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      stream.getTracks().forEach((track) => track.stop());
      setError('');
      await enumerateDevices();
    } catch (err) {
      console.error('Camera permission denied:', err);
      setError('Camera permission denied');
    }
  }, [enumerateDevices]);

  const stopCamera = useCallback(() => {
    if (sendIntervalRef.current) {
      clearInterval(sendIntervalRef.current);
      sendIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  const startCamera = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setError('Camera API unavailable');
      return;
    }

    if (!selectedDeviceId && devices.length === 0) {
      await requestAccess();
      return;
    }

    try {
      if (streamRef.current) {
        stopCamera();
      }
      const constraints: MediaStreamConstraints = {
        video: {
          deviceId: selectedDeviceId ? { exact: selectedDeviceId } : undefined,
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setCameraActive(true);
      setError('');
    } catch (err) {
      console.error('Failed to start camera:', err);
      setError('Failed to start camera');
    }
  }, [devices.length, requestAccess, selectedDeviceId, stopCamera]);

  const sendFrame = useCallback(async () => {
    if (!cameraActive) return;
    if (typeof window === 'undefined' || !window.electronAPI?.sendFrame) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;
    if (!video.videoWidth || !video.videoHeight) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.8)
    );
    if (!blob) return;
    const arrayBuffer = await blob.arrayBuffer();
    const payload = new Uint8Array(arrayBuffer);
    try {
      await window.electronAPI.sendFrame(payload);
    } catch (err) {
      console.error('Failed to push frame to backend:', err);
    }
  }, [cameraActive]);

  useEffect(() => {
    enumerateDevices();
    return () => {
      stopCamera();
    };
  }, [enumerateDevices, stopCamera]);

  useEffect(() => {
    if (!cameraActive) return;
    sendFrame();
    sendIntervalRef.current = setInterval(sendFrame, SNAPSHOT_INTERVAL_MS);
    return () => {
      if (sendIntervalRef.current) {
        clearInterval(sendIntervalRef.current);
        sendIntervalRef.current = null;
      }
    };
  }, [cameraActive, sendFrame]);

  return (
    <div
      className="flex flex-col bg-darker border-r border-gray-800"
      style={{ width: `${width}%` }}
    >
      <div className="flex items-center gap-3 p-4 bg-dark border-b border-gray-800">
        <h2 className="text-lg font-semibold">Camera Feed</h2>
        <div className="text-xs text-gray-400">
          Streaming to: {frameEndpoint || 'not configured'}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {devices.length === 0 ? (
            <button onClick={requestAccess} className="btn btn-primary text-sm">
              Grant Camera Access
            </button>
          ) : (
            <>
              <select
                value={selectedDeviceId}
                onChange={(e) => setSelectedDeviceId(e.target.value)}
                className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {devices.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label || `Camera ${device.deviceId.slice(0, 8)}`}
                  </option>
                ))}
              </select>

              {cameraActive ? (
                <button onClick={stopCamera} className="btn btn-danger text-sm">
                  Stop Camera
                </button>
              ) : (
                <button onClick={startCamera} className="btn btn-success text-sm" disabled={!selectedDeviceId}>
                  Start Camera
                </button>
              )}
            </>
          )}
        </div>
      </div>

      <div className="flex-1 relative bg-black flex items-center justify-center">
        {error && (
          <div className="absolute top-4 left-4 right-4 bg-red-900/90 text-white px-4 py-2 rounded-lg z-10">
            {error}
          </div>
        )}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`max-w-full max-h-full object-contain ${cameraActive ? 'block' : 'hidden'}`}
        />
        {!cameraActive && !error && (
          <div className="text-gray-500 text-center">
            <div className="text-lg mb-2">Camera inactive</div>
            <p className="text-sm">Start the camera to display and stream frames.</p>
          </div>
        )}
        <canvas ref={canvasRef} className="hidden" />
      </div>
    </div>
  );
}

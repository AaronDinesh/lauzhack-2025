'use client';

import { useState, useEffect, useRef } from 'react';

interface CameraViewProps {
  width: number; // percentage
}

export default function CameraView({ width }: CameraViewProps) {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [cameraActive, setCameraActive] = useState(false);
  const [error, setError] = useState<string>('');
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Enumerate camera devices
  const enumerateDevices = async () => {
    try {
      const allDevices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = allDevices.filter((d) => d.kind === 'videoinput');
      setDevices(videoDevices);

      if (videoDevices.length > 0 && !selectedDeviceId) {
        setSelectedDeviceId(videoDevices[0].deviceId);
      }
    } catch (err) {
      console.error('Failed to enumerate devices:', err);
      setError('Unable to access camera devices');
    }
  };

  // Request camera permission and enumerate
  const requestCameraAccess = async () => {
    try {
      // Request permission by opening a stream
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      // Stop the stream immediately after permission is granted
      stream.getTracks().forEach((track) => track.stop());
      // Now enumerate devices
      await enumerateDevices();
      setError('');
    } catch (err) {
      console.error('Camera permission denied:', err);
      setError('Camera permission denied');
    }
  };

  // Start camera with selected device
  const startCamera = async () => {
    if (!selectedDeviceId) {
      setError('No camera selected');
      return;
    }

    try {
      // Stop existing stream if any
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
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
      setCameraActive(false);
    }
  };

  // Stop camera
  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  // Handle device change
  const handleDeviceChange = (deviceId: string) => {
    setSelectedDeviceId(deviceId);
    if (cameraActive) {
      // Restart camera with new device
      stopCamera();
      setTimeout(() => {
        setSelectedDeviceId(deviceId);
      }, 100);
    }
  };

  // Auto-start camera when device is selected and camera is active
  useEffect(() => {
    if (cameraActive && selectedDeviceId) {
      startCamera();
    }
  }, [selectedDeviceId, cameraActive]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  return (
    <div
      className="flex flex-col bg-darker border-r border-gray-800"
      style={{ width: `${width}%` }}
    >
      {/* Camera Controls */}
      <div className="flex items-center gap-3 p-4 bg-dark border-b border-gray-800">
        <h2 className="text-lg font-semibold">Camera Feed</h2>

        {devices.length === 0 ? (
          <button
            onClick={requestCameraAccess}
            className="btn btn-primary text-sm ml-auto"
          >
            Grant Camera Access
          </button>
        ) : (
          <>
            <select
              value={selectedDeviceId}
              onChange={(e) => handleDeviceChange(e.target.value)}
              className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              disabled={devices.length === 0}
            >
              {devices.map((device) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Camera ${device.deviceId.slice(0, 8)}`}
                </option>
              ))}
            </select>

            <button
              onClick={enumerateDevices}
              className="btn btn-secondary text-sm"
              title="Refresh devices"
            >
              🔄 Refresh
            </button>

            {cameraActive ? (
              <button onClick={stopCamera} className="btn btn-danger text-sm ml-auto">
                Stop Camera
              </button>
            ) : (
              <button
                onClick={startCamera}
                className="btn btn-success text-sm ml-auto"
                disabled={!selectedDeviceId}
              >
                Start Camera
              </button>
            )}
          </>
        )}
      </div>

      {/* Video Feed */}
      <div className="flex-1 relative bg-black flex items-center justify-center">
        {error && (
          <div className="absolute top-4 left-4 right-4 bg-red-900/90 text-white px-4 py-2 rounded-lg z-10">
            {error}
          </div>
        )}

        {!cameraActive && !error && (
          <div className="text-gray-500 text-center">
            <div className="text-6xl mb-4">📷</div>
            <p className="text-lg">Camera not active</p>
            <p className="text-sm mt-2">Click "Start Camera" to begin</p>
          </div>
        )}

        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`max-w-full max-h-full object-contain ${
            cameraActive ? 'block' : 'hidden'
          }`}
        />
      </div>
    </div>
  );
}


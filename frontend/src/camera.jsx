import React, { useEffect, useRef, useState } from 'react';

const CAPTURE_INTERVAL_MS = 250;
const MAX_CAPTURE_WIDTH = 640;

export default function BrowserCamera({ endpoint, onMetrics, onState, label }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let stream = null;
    let timer = null;

    const schedule = (callback) => {
      if (active) timer = window.setTimeout(callback, CAPTURE_INTERVAL_MS);
    };

    const sendFrame = async () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!active || !video || !canvas || video.readyState < 2) {
        schedule(sendFrame);
        return;
      }

      const scale = Math.min(1, MAX_CAPTURE_WIDTH / video.videoWidth);
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.72));
      if (!active || !blob) return;

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'image/jpeg' },
          body: blob,
        });
        if (response.ok) {
          const result = await response.json();
          onMetrics?.(result);
        }
      } catch (_error) {
        // The local video remains usable while the backend reconnects.
      } finally {
        schedule(sendFrame);
      }
    };

    const start = async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera API unavailable');
        stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: 'user',
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
        });
        if (!active) return;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setFailed(false);
        onState?.(true);
        sendFrame();
      } catch (_error) {
        if (!active) return;
        setFailed(true);
        onState?.(false);
      }
    };

    start();
    return () => {
      active = false;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [endpoint, onMetrics, onState]);

  return (
    <>
      <video
        className="feed"
        ref={videoRef}
        muted
        playsInline
        aria-label={label}
        style={failed ? { display: 'none' } : undefined}
      />
      <canvas ref={canvasRef} hidden />
    </>
  );
}

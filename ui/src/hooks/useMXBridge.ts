import { useEffect, useRef, useState } from 'react';

export interface MXAction {
<<<<<<< Updated upstream
  type:
    | 'setUrl'
    | 'togglePanel'
    | 'triggerStep'
    | 'setLayout'
    | 'setMockMode'
    | 'setBridgeEndpoint'
    | 'segmentationData'
    | 'segmentationVisible';
=======
  type: 'setUrl' | 'togglePanel' | 'triggerStep' | 'setLayout' | 'setMockMode' | 'setBridgeEndpoint' | 'scroll_vertical';
>>>>>>> Stashed changes
  payload?: any;
}

export interface SegmentationEventPayload {
  prompt?: string;
  imageData?: string;
  numObjects?: number;
  scores?: number[];
  timestamp?: number;
}

interface MXBridgeCallbacks {
  onSetUrl?: (url: string) => void;
  onTogglePanel?: () => void;
  onTriggerStep?: (step: string) => void;
  onSetLayout?: (layout: { dockSide?: 'left' | 'right'; workspaceSplit?: number }) => void;
  onSetMockMode?: (enabled: boolean) => void;
  onSetBridgeEndpoint?: (endpoint: string) => void;
<<<<<<< Updated upstream
  onSegmentationData?: (payload: SegmentationEventPayload) => void;
  onSegmentationVisible?: (visible: boolean) => void;
=======
  onScrollVertical?: (delta: number) => void;
>>>>>>> Stashed changes
}

export function useMXBridge(endpoint: string | undefined, callbacks: MXBridgeCallbacks) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    let isMounted = true;

    function connectSSE() {
      if (!endpoint || !endpoint.trim() || !isMounted) {
        setConnected(false);
        setError(null);
        return;
      }

      try {
        const es = new EventSource(endpoint);
        eventSourceRef.current = es;

        es.onopen = () => {
          if (isMounted) {
            console.log('[MX Bridge] Connected to', endpoint);
            setConnected(true);
            setError(null);
          }
        };

        es.onerror = (err) => {
          if (isMounted) {
            console.error('[MX Bridge] Connection error:', err);
            setConnected(false);
            setError('Connection failed');
            es.close();

            reconnectTimeoutRef.current = setTimeout(() => {
              if (isMounted) {
                console.log('[MX Bridge] Attempting to reconnect...');
                connectSSE();
              }
            }, 5000);
          }
        };

        es.onmessage = (event) => {
          if (!isMounted) return;

          try {
            const action: MXAction = JSON.parse(event.data);
            console.log('[MX Bridge] Received action:', action);

            switch (action.type) {
              case 'setUrl':
                if (callbacks.onSetUrl && action.payload?.url) {
                  callbacks.onSetUrl(action.payload.url);
                }
                break;
              case 'togglePanel':
                if (callbacks.onTogglePanel) {
                  callbacks.onTogglePanel();
                }
                break;
              case 'triggerStep':
                if (callbacks.onTriggerStep && action.payload?.step) {
                  callbacks.onTriggerStep(action.payload.step);
                }
                break;
              case 'setLayout':
                if (callbacks.onSetLayout && action.payload) {
                  callbacks.onSetLayout(action.payload);
                }
                break;
              case 'setMockMode':
                if (callbacks.onSetMockMode && typeof action.payload?.enabled === 'boolean') {
                  callbacks.onSetMockMode(action.payload.enabled);
                }
                break;
              case 'setBridgeEndpoint':
                if (callbacks.onSetBridgeEndpoint && action.payload?.endpoint) {
                  callbacks.onSetBridgeEndpoint(action.payload.endpoint);
                }
                break;
<<<<<<< Updated upstream
              case 'segmentationData':
                if (callbacks.onSegmentationData && action.payload) {
                  callbacks.onSegmentationData(action.payload);
                }
                break;
              case 'segmentationVisible':
                if (callbacks.onSegmentationVisible && typeof action.payload?.visible === 'boolean') {
                  callbacks.onSegmentationVisible(Boolean(action.payload.visible));
=======
              case 'scroll_vertical':
                if (callbacks.onScrollVertical && typeof action.payload?.delta === 'number') {
                  callbacks.onScrollVertical(action.payload.delta);
>>>>>>> Stashed changes
                }
                break;
              default:
                console.warn('[MX Bridge] Unknown action type:', action.type);
            }
          } catch (err) {
            console.error('[MX Bridge] Failed to parse message:', err);
          }
        };
      } catch (err) {
        if (isMounted) {
          console.error('[MX Bridge] Failed to create EventSource:', err);
          setError('Failed to connect');
        }
      }
    }

    connectSSE();

    return () => {
      isMounted = false;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [endpoint, callbacks]);

  return { connected, error };
}

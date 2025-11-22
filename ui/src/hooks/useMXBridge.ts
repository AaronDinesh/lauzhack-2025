import { useEffect, useState, useRef } from 'react';

export interface MXAction {
  type: 'setUrl' | 'togglePanel' | 'triggerStep' | 'setLayout' | 'setMockMode' | 'setBridgeEndpoint';
  payload?: any;
}

interface MXBridgeCallbacks {
  onSetUrl?: (url: string) => void;
  onTogglePanel?: () => void;
  onTriggerStep?: (step: string) => void;
  onSetLayout?: (layout: { dockSide?: 'left' | 'right'; workspaceSplit?: number }) => void;
  onSetMockMode?: (enabled: boolean) => void;
  onSetBridgeEndpoint?: (endpoint: string) => void;
}

export function useMXBridge(endpoint: string, callbacks: MXBridgeCallbacks) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    let isMounted = true;

    function connectSSE() {
      if (!endpoint || !isMounted) return;

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

            // Attempt to reconnect after 5 seconds
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


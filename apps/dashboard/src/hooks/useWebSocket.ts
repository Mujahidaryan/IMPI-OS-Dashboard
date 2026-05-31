import { useEffect, useRef, useState, useCallback } from "react";

export type WebSocketStatus = "connecting" | "connected" | "disconnected" | "reconnecting";

export interface UseWebSocketOptions {
  onMessage?: (type: string, data: any) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(url: string = "ws://localhost:8000/ws", options: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<WebSocketStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const reconnectTimeoutRef = useRef<any>(null);
  
  const { onMessage, reconnectInterval = 3000, maxReconnectAttempts = 20 } = options;

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN)) {
      return;
    }

    setStatus("connecting");

    try {
      // Use dynamic URL protocol if needed, otherwise default to ws://localhost:8000/ws
      let wsUrl = url;
      if (typeof window !== "undefined") {
        if (url.startsWith("/")) {
          const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
          wsUrl = `${proto}//${window.location.host}${url}`;
        }
      }

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
        reconnectAttemptsRef.current = 0;
        console.log("[WS] Connected to", wsUrl);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload && payload.type && onMessage) {
            onMessage(payload.type, payload.data || payload);
          }
        } catch (err) {
          console.error("[WS] Failed to parse message:", err);
        }
      };

      ws.onclose = (event) => {
        setStatus("disconnected");
        wsRef.current = null;
        console.log("[WS] Connection closed:", event.reason);
        
        // Attempt reconnection
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = reconnectInterval * Math.min(reconnectAttemptsRef.current + 1, 5);
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})...`);
          setStatus("reconnecting");
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      ws.onerror = (error) => {
        console.error("[WS] Connection error:", error);
      };
    } catch (err) {
      console.error("[WS] Initialization failed:", err);
      setStatus("disconnected");
    }
  }, [url, onMessage, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("disconnected");
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  const send = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof message === "string" ? message : JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  return { status, send, reconnect: connect };
}

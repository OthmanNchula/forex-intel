"use client";
import { useEffect, useRef } from "react";
import { useStore } from "@/store/useStore";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000";

export function useLivePrice(pairs: string[]) {
  const { setPrice } = useStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!pairs || pairs.length === 0) return;

    function connect() {
      try {
        const ws = new WebSocket(`${WS_URL}/ws/prices`);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log("WebSocket connected");
          ws.send(
            JSON.stringify({
              action: "subscribe",
              pairs: pairs,
            })
          );
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "price_update" && data.pair && data.price) {
              setPrice(data.pair, data.price);
            }
          } catch (err) {
            console.error("WS message parse error:", err);
          }
        };

        ws.onclose = () => {
          console.log("WebSocket disconnected — reconnecting in 5s");
          reconnectRef.current = setTimeout(connect, 5000);
        };

        ws.onerror = (err) => {
          console.error("WebSocket error:", err);
          ws.close();
        };
      } catch (err) {
        console.error("WebSocket connection failed:", err);
        reconnectRef.current = setTimeout(connect, 5000);
      }
    }

    connect();

    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [pairs.join(",")]);
}
import { create } from "zustand";
import { User, Signal } from "@/types";

interface ForexIntelStore {
  // Auth
  user: User | null;
  token: string | null;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;

  // Active pair
  activePair: string;
  setActivePair: (pair: string) => void;

  // Active timeframe
  activeTimeframe: string;
  setActiveTimeframe: (tf: string) => void;

  // Live prices
  prices: Record<string, number>;
  setPrice: (pair: string, price: number) => void;

  // Active signals
  signals: Signal[];
  setSignals: (signals: Signal[]) => void;
  addSignal: (signal: Signal) => void;

  // Notifications
  notifications: string[];
  addNotification: (msg: string) => void;
  clearNotifications: () => void;
}

export const useStore = create<ForexIntelStore>((set) => ({
  // Auth
  user: null,
  token: null,
  setUser: (user) => set({ user }),
  setToken: (token) => set({ token }),

  // Active pair
  activePair: "EUR/USD",
  setActivePair: (pair) => set({ activePair: pair }),

  // Active timeframe
  activeTimeframe: "H1",
  setActiveTimeframe: (tf) => set({ activeTimeframe: tf }),

  // Live prices
  prices: {},
  setPrice: (pair, price) =>
    set((state) => ({ prices: { ...state.prices, [pair]: price } })),

  // Signals
  signals: [],
  setSignals: (signals) => set({ signals }),
  addSignal: (signal) =>
    set((state) => ({ signals: [signal, ...state.signals] })),

  // Notifications
  notifications: [],
  addNotification: (msg) =>
    set((state) => ({
      notifications: [msg, ...state.notifications].slice(0, 10),
    })),
  clearNotifications: () => set({ notifications: [] }),
}));
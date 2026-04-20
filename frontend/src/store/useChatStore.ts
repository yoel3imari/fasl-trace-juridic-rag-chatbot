import { create } from "zustand";

/**
 * Chat store — manages cross-pane state between the Chat and PDF Document panes.
 * Zustand was chosen over React Context to prevent full sub-tree re-renders
 * during high-velocity coordinate dispatching (60fps target).
 *
 * This is a skeleton — slices will be added as features are implemented.
 */

interface ChatState {
  /** Active session ID */
  sessionId: string | null;

  /** Currently highlighted citation coordinates */
  activeCitation: {
    page: number;
    box: [number, number, number, number]; // [x, y, w, h]
  } | null;

  /** Actions */
  setSessionId: (id: string | null) => void;
  setActiveCitation: (
    citation: { page: number; box: [number, number, number, number] } | null
  ) => void;
  clearSession: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  activeCitation: null,

  setSessionId: (id) => set({ sessionId: id }),
  setActiveCitation: (citation) => set({ activeCitation: citation }),
  clearSession: () => set({ sessionId: null, activeCitation: null }),
}));

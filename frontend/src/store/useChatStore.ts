import { create } from "zustand";

// ── Utility: UUID with fallback for insecure contexts / older browsers ──
const generateId = (): string => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `fallback-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
};

// ── Message Types (SSE contract accommodation for Story 3.3) ──────────

/**
 * Citation matching the backend's RetrievalResult format (v1 — text-based).
 * Bounding-box pinning (CitationGeometry) will replace this in a later phase.
 */
export interface Citation {
  source_index: number;
  page: number;
  section: string | null;
  text: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  isStreaming?: boolean;
  citations?: Citation[];
  hasUnverifiedClaim?: boolean;
  error?: string;
  warning?: string;
  timestamp: string;
}

export interface ProcessingStep {
  id: string;
  label: string;
  status: "pending" | "active" | "complete";
}

// ── Workspace State ───────────────────────────────────────────

export type TextDirection = "ltr" | "rtl";
export type DocumentLanguage = "en" | "fr" | "ar";

const RTL_LANGUAGES = ["ar", "he", "fa", "ur"] as const;

export interface WorkspaceState {
  sessionId: string;
  selectedDocumentId: string | null;
  pdfUrl: string | null;
  selectedCollectionId: string | null;
  panelRatio: [number, number];
  chatPaneVisible: boolean;
  messages: ChatMessage[];
  processingSteps: ProcessingStep[];
  currentStreamingMessageId: string | null;
  streamingStatus: "idle" | "processing" | "streaming" | "complete" | "error";
  documentLanguage: DocumentLanguage;
  direction: TextDirection;
}

// ── Combined Store Interface ────────────────────────────────

interface ChatState {
  activeCitation: Citation | null;
  workspace: WorkspaceState;

  // Derived getters (computed, not stored state)
  getMessages: () => ChatMessage[];
  getSessionMessageCount: () => number;

  // Core actions
  setActiveCitation: (citation: Citation | null) => void;
  clearSession: () => void;

  // Workspace actions
  setSelectedDocument: (documentId: string | null, pdfUrl: string | null, language?: DocumentLanguage) => void;
  setSelectedCollection: (collectionId: string | null) => void;
  setPdfUrl: (url: string | null) => void;
  setPanelRatio: (ratio: [number, number]) => void;
  toggleChatPane: () => void;
  setDirection: (language: DocumentLanguage) => void;

  // Message actions
  addMessage: (message: ChatMessage) => void;
  addUserMessage: (content: string) => void;
  startAssistantMessage: () => void;
  appendToken: (messageId: string, tokenContent: string) => void;
  updateProcessingStep: (stepId: string, status: "pending" | "active" | "complete") => void;
  finalizeMessage: (messageId: string) => void;
  setMessageCitations: (messageId: string, citations: Citation[]) => void;
  setStreamingStatus: (status: "idle" | "processing" | "streaming" | "complete" | "error") => void;

  // SSE integration actions
  setProcessingSteps: (steps: ProcessingStep[]) => void;
  setStreamError: (messageId: string, error: string) => void;
  getCurrentStreamingMessageId: () => string | null;
}

// ── Default workspace state ─────────────────────────────────

const defaultWorkspace = (): WorkspaceState => ({
  sessionId: generateId(),
  selectedDocumentId: null,
  pdfUrl: null,
  selectedCollectionId: null,
  panelRatio: [40, 60],
  chatPaneVisible: true,
  messages: [],
  processingSteps: [],
  currentStreamingMessageId: null,
  streamingStatus: "idle",
  documentLanguage: "en",
  direction: "ltr",
});

// ── Store ───────────────────────────────────────────────────

export const useChatStore = create<ChatState>((set, get) => ({
  activeCitation: null,
  workspace: defaultWorkspace(),

  getMessages: () => {
    const msgs = get().workspace.messages;
    return [...msgs].sort((a, b) => {
      const aTime = new Date(a.timestamp).getTime();
      const bTime = new Date(b.timestamp).getTime();
      if (Number.isNaN(aTime)) return 1;
      if (Number.isNaN(bTime)) return -1;
      return aTime - bTime;
    });
  },

  getSessionMessageCount: () => get().workspace.messages.length,

  setActiveCitation: (citation) => set({ activeCitation: citation }),
  clearSession: () =>
    set((state) => ({
      activeCitation: null,
      workspace: {
        ...defaultWorkspace(),
              panelRatio: state.workspace.panelRatio,
        chatPaneVisible: state.workspace.chatPaneVisible,
      },
    })),

  setSelectedDocument: (documentId, pdfUrl, language) =>
    set((state) => {
      const validLangs: DocumentLanguage[] = ["en", "fr", "ar"];
      const resolved =
        language && validLangs.includes(language)
          ? language
          : state.workspace.documentLanguage;
      return {
        activeCitation: null,
        workspace: {
          ...state.workspace,
          selectedDocumentId: documentId,
          pdfUrl,
          documentLanguage: resolved,
          direction: RTL_LANGUAGES.includes(resolved as never) ? "rtl" : "ltr",
        },
      };
    }),

  setSelectedCollection: (collectionId) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        selectedCollectionId: collectionId,
      },
    })),

  setPdfUrl: (url) =>
    set((state) => ({
      activeCitation: null,
      workspace: {
        ...state.workspace,
        pdfUrl: url,
      },
    })),

  setPanelRatio: (ratio) =>
    set((state) => {
      const [a, b] = state.workspace.panelRatio;
      if (ratio[0] === a && ratio[1] === b) return state;
      return {
        workspace: {
          ...state.workspace,
          panelRatio: ratio,
        },
      };
    }),

  toggleChatPane: () =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        chatPaneVisible: !state.workspace.chatPaneVisible,
      },
    })),

  setDirection: (language) =>
    set((state) => {
      const validLangs: DocumentLanguage[] = ["en", "fr", "ar"];
      const resolved = validLangs.includes(language)
        ? language
        : state.workspace.documentLanguage;
      return {
        workspace: {
          ...state.workspace,
          documentLanguage: resolved,
          direction: RTL_LANGUAGES.includes(resolved as never) ? "rtl" : "ltr",
        },
      };
    }),

  addMessage: (message) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        messages: [...state.workspace.messages, message],
      },
    })),

  addUserMessage: (content) =>
    set((state) => {
      if (!content?.trim()) return state;
      const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const msg: ChatMessage = {
        id,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };
      return {
        workspace: {
          ...state.workspace,
          messages: [...state.workspace.messages, msg],
        },
      };
    }),

  startAssistantMessage: () =>
    set((state) => {
      const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const msg: ChatMessage = {
        id,
        role: "assistant",
        content: "",
        isStreaming: true,
        timestamp: new Date().toISOString(),
      };
      return {
        workspace: {
          ...state.workspace,
          messages: [...state.workspace.messages, msg],
          currentStreamingMessageId: id,
          streamingStatus: "streaming",
          processingSteps: [],
        },
      };
    }),

  appendToken: (messageId, tokenContent) =>
    set((state) => {
      const exists = state.workspace.messages.some((m) => m.id === messageId);
      if (!exists) return state;
      return {
        workspace: {
          ...state.workspace,
          messages: state.workspace.messages.map((msg) =>
            msg.id === messageId
              ? { ...msg, content: msg.content + tokenContent }
              : msg
          ),
        },
      };
    }),

  updateProcessingStep: (stepId, status) =>
    set((state) => {
      const exists = state.workspace.processingSteps.some((s) => s.id === stepId);
      if (!exists) return state;
      return {
        workspace: {
          ...state.workspace,
          processingSteps: state.workspace.processingSteps.map((s) =>
            s.id === stepId ? { ...s, status } : s
          ),
        },
      };
    }),

  finalizeMessage: (messageId) =>
    set((state) => {
      const exists = state.workspace.messages.some((m) => m.id === messageId);
      if (!exists) return state;
      return {
        workspace: {
          ...state.workspace,
          messages: state.workspace.messages.map((msg) =>
            msg.id === messageId ? { ...msg, isStreaming: false } : msg
          ),
          currentStreamingMessageId: null,
          streamingStatus: "complete",
        },
      };
    }),

  setMessageCitations: (messageId, citations) =>
    set((state) => {
      const exists = state.workspace.messages.some((m) => m.id === messageId);
      if (!exists) return state;
      return {
        workspace: {
          ...state.workspace,
          messages: state.workspace.messages.map((msg) =>
            msg.id === messageId ? { ...msg, citations } : msg
          ),
        },
      };
    }),

  setStreamingStatus: (status) =>
    set((state) => ({
      workspace: { ...state.workspace, streamingStatus: status },
    })),

  setProcessingSteps: (steps) =>
    set((state) => ({
      workspace: { ...state.workspace, processingSteps: steps },
    })),

  setStreamError: (messageId, error) =>
    set((state) => {
      const exists = state.workspace.messages.some((m) => m.id === messageId);
      if (!exists) return state;
      return {
        workspace: {
          ...state.workspace,
          messages: state.workspace.messages.map((msg) =>
            msg.id === messageId ? { ...msg, error, isStreaming: false } : msg
          ),
          currentStreamingMessageId: null,
          streamingStatus: "error",
        },
      };
    }),

  getCurrentStreamingMessageId: () => get().workspace.currentStreamingMessageId,
}));

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { BrowserRouter as Router, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import type { AxiosError } from "axios";
import AttachmentComposer from "./components/AttachmentComposer";
import AuthCallback from "./components/AuthCallback";
import GeneratedImageCard from "./components/GeneratedImageCard";
import ImageGenerationError from "./components/ImageGenerationError";
import ImageGenerationLoading from "./components/ImageGenerationLoading";
import Login from "./components/Login";
import ResearchDigest from "./pages/ResearchDigest";
import TicTacToe from "./pages/TicTacToe";
import Tickets from "./pages/Tickets";
import TicketDetailPage from "./pages/TicketDetail";
import MessageContent from "./components/MessageContent";
import RagDebugPanel from "./components/RagDebugPanel";
import { authService } from "./services/auth";
import { chatService } from "./services/chat";
import { dataQueryService } from "./services/dataQuery";
import type {
  AttachmentPreview,
  ChatMessage,
  ChatMode,
  ChatSidebarItem,
  DataQueryDatasetResponse,
  RagDebugResponse,
  User,
} from "./types";
import {
  buildAttachmentPreview,
  MAX_ATTACHMENTS_PER_MESSAGE,
  SUPPORTED_EXTENSIONS,
  toAttachmentPayload,
} from "./utils/attachments";

const IMAGE_PROMPT_PREFIX = "Generated image for:";
const CHAT_MODE_STORAGE_KEY = "chat.mode.current";
const CHAT_DEFAULT_MODE_STORAGE_KEY = "chat.mode.default";
type SpreadsheetSource = "excel_csv" | "google_sheets";
type SpreadsheetMode = "existing_chat" | "nl_sql" | "dataframe";

function normalizeMode(value: string | null | undefined): ChatMode {
  if (value === "rag" || value === "db") {
    return value;
  }
  return "normal";
}

function extractImagePrompt(content: string): string {
  if (!content.startsWith(IMAGE_PROMPT_PREFIX)) {
    return "";
  }
  const firstLine = content.split("\n")[0];
  return firstLine.replace(IMAGE_PROMPT_PREFIX, "").trim();
}

function formatSpreadsheetRequestError(error: unknown, fallbackMessage: string): string {
  const axiosErr = error as AxiosError<{ detail?: string }>;
  const backendDetail = axiosErr.response?.data?.detail;
  const rawMessage = axiosErr.message || "";

  if (axiosErr.code === "ECONNABORTED" || rawMessage.toLowerCase().includes("timeout")) {
    return "Request timed out. The sheet service took too long. Please retry with a smaller sheet or a shorter question.";
  }

  if (axiosErr.code === "ERR_NETWORK") {
    return "Cannot reach the sheet service. Start it on http://localhost:8001 and try again.";
  }

  return backendDetail || rawMessage || fallbackMessage;
}

function ChatApp() {
  type SidebarView = "chat" | "spreadsheet";

  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sidebarHistory, setSidebarHistory] = useState<ChatSidebarItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null);
  const [threadId, setThreadId] = useState<number | null>(null);
  const [attachments, setAttachments] = useState<AttachmentPreview[]>([]);
  const [attachmentHint, setAttachmentHint] = useState<string | null>(null);
  const [requestUploadProgress, setRequestUploadProgress] = useState<number>(0);
  const [imageGenerating, setImageGenerating] = useState(false);
  const [imageCapabilityAvailable, setImageCapabilityAvailable] = useState(true);
  const [imageCapabilityReason, setImageCapabilityReason] = useState<string | null>(null);
  const [imageCapabilityModel, setImageCapabilityModel] = useState<string | null>(null);
  const [imageCapabilityFallbackModels, setImageCapabilityFallbackModels] = useState<string[]>([]);
  const [ragDebug, setRagDebug] = useState<RagDebugResponse | null>(null);
  const [ragDebugLoading, setRagDebugLoading] = useState(false);
  const [ragDebugError, setRagDebugError] = useState<string | null>(null);
  const [chatMode, setChatMode] = useState<ChatMode>(() => {
    const remembered = localStorage.getItem(CHAT_MODE_STORAGE_KEY);
    if (remembered) {
      return normalizeMode(remembered);
    }
    return normalizeMode(localStorage.getItem(CHAT_DEFAULT_MODE_STORAGE_KEY));
  });
  const [defaultChatMode, setDefaultChatMode] = useState<ChatMode>(() =>
    normalizeMode(localStorage.getItem(CHAT_DEFAULT_MODE_STORAGE_KEY))
  );
  const [ragSelectedAttachmentIds, setRagSelectedAttachmentIds] = useState<number[]>([]);
  const [resetHistoryOnNextSend, setResetHistoryOnNextSend] = useState(false);
  const [sidebarView, setSidebarView] = useState<SidebarView>("chat");
  const [spreadsheetSource, setSpreadsheetSource] = useState<SpreadsheetSource>("google_sheets");
  const [spreadsheetMode, setSpreadsheetMode] = useState<SpreadsheetMode>("dataframe");
  const [spreadsheetUrl, setSpreadsheetUrl] = useState("");
  const [spreadsheetQuestion, setSpreadsheetQuestion] = useState("");
  const [spreadsheetLoading, setSpreadsheetLoading] = useState(false);
  const [spreadsheetSessionId, setSpreadsheetSessionId] = useState<string | null>(null);
  const [spreadsheetFileDataset, setSpreadsheetFileDataset] = useState<DataQueryDatasetResponse | null>(null);
  const [spreadsheetGoogleDataset, setSpreadsheetGoogleDataset] = useState<DataQueryDatasetResponse | null>(null);
  const [spreadsheetGoogleSourceUrl, setSpreadsheetGoogleSourceUrl] = useState("");
  const [spreadsheetFileName, setSpreadsheetFileName] = useState<string | null>(null);
  const [spreadsheetSelectedSheet, setSpreadsheetSelectedSheet] = useState("");
  const [spreadsheetUploadMessage, setSpreadsheetUploadMessage] = useState<string | null>(null);
  const [spreadsheetAnswer, setSpreadsheetAnswer] = useState<string | null>(null);
  const [spreadsheetPandasCode, setSpreadsheetPandasCode] = useState<string | null>(null);
  const spreadsheetFileInputRef = useRef<HTMLInputElement | null>(null);
  const imageGenerationLockRef = useRef(false);

  const activeSpreadsheetDataset = spreadsheetSource === "excel_csv" ? spreadsheetFileDataset : spreadsheetGoogleDataset;

  useEffect(() => {
    localStorage.setItem(CHAT_MODE_STORAGE_KEY, chatMode);
  }, [chatMode]);

  useEffect(() => {
    localStorage.setItem(CHAT_DEFAULT_MODE_STORAGE_KEY, defaultChatMode);
  }, [defaultChatMode]);

  const loadRagDebug = async () => {
    setRagDebugLoading(true);
    setRagDebugError(null);

    try {
      const data = await chatService.getRagDebugInfo();
      setRagDebug(data);
    } catch {
      setRagDebugError("Unable to load indexed PDF chunks.");
    } finally {
      setRagDebugLoading(false);
    }
  };

  const mapHistoryItemsToMessages = (historyItems: any[]): ChatMessage[] => {
    return historyItems.map((item) => ({
      id: item.id,
      role: item.role as "user" | "assistant" | "system",
      content: item.content,
      created_at: item.created_at,
      attachments: (item.attachments || []).map((attachment: any) => ({
        id: `history-${attachment.id}`,
        uploadId: attachment.id,
        downloadUrl: attachment.download_url,
        name: attachment.name,
        mimeType: attachment.mime_type,
        extension: attachment.name.split(".").pop()?.toLowerCase() || "",
        size: attachment.size,
        category: attachment.category,
        progress: 100,
        previewUrl: attachment.download_url,
        textContent: attachment.text_content,
        isReady: true,
      })),
      is_image_generation: (item.attachments || []).some((attachment: any) => attachment.category === "image"),
      image_prompt: extractImagePrompt(item.content),
    }));
  };

  const loadThreadMessages = async (targetThreadId: number) => {
    try {
      const history = await chatService.getChatHistory();
      const threadMessages = Array.isArray(history)
        ? history.filter((item) => item.thread_id === targetThreadId)
        : [];
      setMessages(mapHistoryItemsToMessages(threadMessages));
    } catch (historyError) {
      console.warn("Failed to load chat history:", historyError);
      setMessages([]);
      setError("Unable to load this chat history. Please try again.");
    }
  };

  useEffect(() => {
    const initializeChat = async () => {
      try {
        const currentUser = await authService.getCurrentUser();
        setUser(currentUser);

        // Load sidebar history first
        try {
          const sidebarItems = await chatService.getSidebarHistory();
          setSidebarHistory(Array.isArray(sidebarItems) ? sidebarItems : []);

          // If there are existing threads, load the first one
          if (Array.isArray(sidebarItems) && sidebarItems.length > 0) {
            const firstThread = sidebarItems[0];
            setSelectedHistoryId(firstThread.id);
            setThreadId(firstThread.id);

            // Load messages for the first thread
            await loadThreadMessages(firstThread.id);
          } else {
            // No existing threads, start fresh
            setMessages([]);
            setThreadId(Math.floor(Date.now() / 1000));
          }
        } catch (sidebarError) {
          console.warn("Failed to load sidebar history:", sidebarError);
          setSidebarHistory([]);
          setMessages([]);
          setThreadId(Math.floor(Date.now() / 1000));
        }

        try {
          const imageCapabilities = await chatService.getImageCapabilities();
          setImageCapabilityAvailable(imageCapabilities.available);
          setImageCapabilityReason(imageCapabilities.reason ?? null);
          setImageCapabilityModel(imageCapabilities.normalized_model ?? imageCapabilities.model ?? null);
          setImageCapabilityFallbackModels(imageCapabilities.fallback_models ?? []);
        } catch {
          setImageCapabilityAvailable(false);
          setImageCapabilityReason("Image generation endpoint is not enabled on this backend.");
          setImageCapabilityModel(null);
          setImageCapabilityFallbackModels([]);
        }

        try {
          await loadRagDebug();
        } catch {
          // RAG debug is optional
        }
      } catch (error) {
        console.error("Failed to initialize chat:", error);
        setError("Unable to load your account. Please login again.");
      } finally {
        setLoadingHistory(false);
      }
    };

    void initializeChat();
  }, []);

  const handleFilesAdded = async (files: File[]) => {
    setAttachmentHint(null);

    if (attachments.length >= MAX_ATTACHMENTS_PER_MESSAGE) {
      setAttachmentHint(`You can attach up to ${MAX_ATTACHMENTS_PER_MESSAGE} files in one message.`);
      return;
    }

    const allowedSlots = MAX_ATTACHMENTS_PER_MESSAGE - attachments.length;
    const filesToProcess = files.slice(0, allowedSlots);

    if (files.length > filesToProcess.length) {
      setAttachmentHint(`Only ${MAX_ATTACHMENTS_PER_MESSAGE} files are allowed per message.`);
    }

    for (const file of filesToProcess) {
      const extension = file.name.split(".").pop()?.toLowerCase() || "";
      if (!SUPPORTED_EXTENSIONS.includes(extension as (typeof SUPPORTED_EXTENSIONS)[number])) {
        setAttachmentHint(`Unsupported file type: ${file.name}`);
        continue;
      }

      const pendingId = `${file.name}-${file.lastModified}`;
      const pendingAttachment: AttachmentPreview = {
        id: pendingId,
        file,
        name: file.name,
        mimeType: file.type || "application/octet-stream",
        extension,
        size: file.size,
        category: "document",
        progress: 1,
        isReady: false,
      };

      setAttachments((prev) => [...prev, pendingAttachment]);

      try {
        const processed = await buildAttachmentPreview(file, (progress) => {
          setAttachments((prev) =>
            prev.map((item) => (item.id === pendingId ? { ...item, progress: Math.max(1, Math.round(progress * 40)) } : item))
          );
        });

        setAttachments((prev) =>
          prev.map((item) => (item.id === pendingId ? { ...processed, id: pendingId, progress: 45, isReady: false } : item))
        );

        const uploadResult = await chatService.uploadAttachment(file, processed.category, (uploadProgress) => {
          setAttachments((prev) =>
            prev.map((item) =>
              item.id === pendingId
                ? { ...item, progress: Math.max(45, 45 + Math.round(uploadProgress * 0.55)) }
                : item
            )
          );
        });

        setAttachments((prev) =>
          prev.map((item) =>
            item.id === pendingId
              ? {
                  ...processed,
                  id: pendingId,
                  uploadId: uploadResult.id,
                  downloadUrl: uploadResult.download_url,
                  progress: 100,
                  isReady: true,
                }
              : item
          )
        );

        if (chatMode === "rag") {
          setRagSelectedAttachmentIds((prev) => {
            if (prev.includes(uploadResult.id)) {
              return prev;
            }
            return [...prev, uploadResult.id];
          });
        }

        if (extension === "pdf") {
          await loadRagDebug();
        }
      } catch (fileError) {
        setAttachments((prev) =>
          prev.map((item) =>
            item.id === pendingId
              ? {
                  ...item,
                  progress: 100,
                  isReady: false,
                  error: fileError instanceof Error ? fileError.message : "File processing failed.",
                }
              : item
          )
        );
      }
    }
  };

  const handleRemoveAttachment = async (attachmentId: string) => {
    let removedAttachment: AttachmentPreview | undefined;

    setAttachments((prev) => {
      removedAttachment = prev.find((item) => item.id === attachmentId);
      if (removedAttachment?.previewUrl) {
        URL.revokeObjectURL(removedAttachment.previewUrl);
      }
      return prev.filter((item) => item.id !== attachmentId);
    });

    if (removedAttachment?.uploadId) {
      setRagSelectedAttachmentIds((prev) => prev.filter((id) => id !== removedAttachment?.uploadId));
      try {
        await chatService.deleteAttachment(removedAttachment.uploadId);
      } catch {
        setAttachmentHint("Attachment was removed locally but server cleanup failed.");
      }
      await loadRagDebug();
    }
  };

  const clearAttachments = async (deleteServerFiles: boolean = true) => {
    let removed: AttachmentPreview[] = [];

    setAttachments((prev) => {
      removed = prev;
      prev.forEach((item) => {
        if (item.previewUrl) {
          URL.revokeObjectURL(item.previewUrl);
        }
      });
      return [];
    });

    if (!deleteServerFiles) {
      setAttachmentHint(null);
      return;
    }

    const uploadIds = removed.map((item) => item.uploadId).filter((value): value is number => typeof value === "number");
    setRagSelectedAttachmentIds((prev) => prev.filter((id) => !uploadIds.includes(id)));
    if (uploadIds.length === 0) {
      setAttachmentHint(null);
      return;
    }

    const results = await Promise.allSettled(uploadIds.map((uploadId) => chatService.deleteAttachment(uploadId)));
    if (results.some((item) => item.status === "rejected")) {
      setAttachmentHint("Some attachments were cleared locally but server cleanup failed.");
    } else {
      setAttachmentHint(null);
    }

    await loadRagDebug();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const textMessage = input.trim();
    const readyAttachments = attachments.filter((item) => item.isReady && !item.error);

    if (textMessage.toLowerCase().startsWith("/image ")) {
      const slashPrompt = textMessage.slice(7).trim();
      if (!slashPrompt) {
        setError("Use /image followed by a prompt.");
        return;
      }
      void handleGenerateImage(slashPrompt);
      return;
    }

    if (!textMessage && readyAttachments.length === 0) {
      return;
    }

    if (attachments.some((item) => !item.isReady && !item.error)) {
      setAttachmentHint("Please wait for file processing to finish before sending.");
      return;
    }

    if (attachments.some((item) => item.error)) {
      setAttachmentHint("Remove failed attachments before sending.");
      return;
    }

    const userMessage: ChatMessage = {
      role: "user",
      content: textMessage || "Sent attachments",
      attachments: readyAttachments,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);
    setAttachmentHint(null);
    setRequestUploadProgress(0);

    try {
      const activeMode = chatMode;
      const selectedRagIds = activeMode === "rag" ? ragSelectedAttachmentIds : [];
      const data = await chatService.sendMessage(
        textMessage,
        readyAttachments.map(toAttachmentPayload),
        (progress) => setRequestUploadProgress(progress),
        threadId,
        activeMode,
        selectedRagIds,
        resetHistoryOnNextSend
      );
      const assistantMessage: ChatMessage = { role: "assistant", content: data.answer, mode_used: activeMode };
      setMessages((prev) => [...prev, assistantMessage]);

      const updatedSidebar = await chatService.getSidebarHistory();
      setSidebarHistory(Array.isArray(updatedSidebar) ? updatedSidebar : []);
      if (Array.isArray(updatedSidebar) && updatedSidebar.length > 0) {
        setSelectedHistoryId(updatedSidebar[0].id);
        setThreadId(updatedSidebar[0].id);
      }
      await clearAttachments(false);
    } catch (err) {
      console.error("Send message error:", err);
      const axiosErr = err as AxiosError<{ detail?: string }>;
      const backendDetail = axiosErr.response?.data?.detail;
      const errorMsg = backendDetail || (err instanceof Error ? err.message : "Unable to send message. Please try again.");
      setError(errorMsg);
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
      setRequestUploadProgress(0);
      setResetHistoryOnNextSend(false);
    }
  };

  const handleGenerateImage = async (promptOverride?: string) => {
    if (imageGenerationLockRef.current) {
      setError("Image generation is already in progress.");
      return;
    }

    imageGenerationLockRef.current = true;

    if (!imageCapabilityAvailable) {
      setError(imageCapabilityReason || "Image generation is not available right now.");
      imageGenerationLockRef.current = false;
      return;
    }

    const prompt = (promptOverride ?? input).trim();
    if (!prompt) {
      setError("Type an image prompt first.");
      imageGenerationLockRef.current = false;
      return;
    }

    if (attachments.length > 0) {
      setAttachmentHint("Clear attachments before generating an image.");
      imageGenerationLockRef.current = false;
      return;
    }

    const userMessage: ChatMessage = { role: "user", content: prompt };
    const loadingMessage: ChatMessage = {
      role: "assistant",
      content: "Generating image...",
      is_image_generation: true,
      image_prompt: prompt,
      image_loading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setInput("");
    setError(null);
    setImageGenerating(true);

    try {
      const data = await chatService.generateImage(prompt, threadId);
      const imageUrl = data.image.download_url || data.image.data_url;

      const generatedAttachment: AttachmentPreview = {
        id: `generated-${data.image.id ?? Date.now()}`,
        uploadId: data.image.id,
        downloadUrl: data.image.download_url,
        name: data.image.name,
        mimeType: data.image.mime_type,
        extension: data.image.name.split(".").pop()?.toLowerCase() || "png",
        size: data.image.size,
        category: "image",
        progress: 100,
        previewUrl: imageUrl,
        isReady: true,
      };

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.answer,
        attachments: [generatedAttachment],
        is_image_generation: true,
        image_prompt: data.prompt,
      };

      setMessages((prev) => {
        const next = [...prev];
        next.pop();
        next.push(assistantMessage);
        return next;
      });

      if (typeof data.thread_id === "number") {
        setThreadId(data.thread_id);
      }

      const updatedSidebar = await chatService.getSidebarHistory();
      setSidebarHistory(updatedSidebar);
      setSelectedHistoryId(updatedSidebar[0]?.id ?? null);
    } catch (err) {
      const backendMessage =
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof err.response === "object" &&
        err.response !== null &&
        "data" in err.response &&
        typeof err.response.data === "object" &&
        err.response.data !== null &&
        "detail" in err.response.data &&
        typeof err.response.data.detail === "string"
          ? err.response.data.detail
          : null;

      const errorMessage = backendMessage || "Unable to generate image. Please try again.";
      setError(errorMessage);
      setMessages((prev) => {
        const next = [...prev];
        next.pop();
        next.push({
          role: "assistant",
          content: `Image generation failed: ${errorMessage}`,
          is_image_generation: true,
          image_prompt: prompt,
          image_error: errorMessage,
        });
        return next;
      });
    } finally {
      setImageGenerating(false);
      imageGenerationLockRef.current = false;
    }
  };

  const handleLogout = () => {
    authService.logout();
    setUser(null);
    setMessages([]);
    setSidebarHistory([]);
    setSelectedHistoryId(null);
    void clearAttachments(false);
    window.location.href = "/login";
  };

  const handleHistorySelect = async (historyItemId: number) => {
    setError(null);
    setSelectedHistoryId(historyItemId);
    setThreadId(historyItemId);
    await loadThreadMessages(historyItemId);
  };

  const handleNewChat = async () => {
    setMessages([]);
    setInput("");
    setError(null);
    setSelectedHistoryId(null);
    setThreadId(Math.floor(Date.now() / 1000)); // Generate unique thread ID
    setChatMode(defaultChatMode);
    setRagSelectedAttachmentIds([]);
    setResetHistoryOnNextSend(false);
    setAttachmentHint(null);
    await clearAttachments(false);
  };

  const handleModeSwitch = async (nextMode: ChatMode) => {
    if (nextMode === chatMode) {
      return;
    }

    // Keep visible chat history while switching mode; only clear transient input context.
    setChatMode(nextMode);
    setError(null);
    setAttachmentHint(
      nextMode === "rag"
        ? "RAG mode enabled. Upload/select a document before asking document questions."
        : nextMode === "db"
          ? "DB Query mode enabled. Ask questions about Supabase tables and records."
          : "Normal mode enabled. Document context is cleared."
    );
    if (nextMode !== "rag") {
      // One-shot reset for backend prompt history on next send.
      setResetHistoryOnNextSend(true);
    }
    setRagSelectedAttachmentIds([]);
    await clearAttachments(false);
  };

  const handleDeleteThread = async (e: React.MouseEvent, threadId: number) => {
    e.stopPropagation();
    try {
      await chatService.deleteThread(threadId);
      // Refresh history after deletion
      const updatedSidebar = await chatService.getSidebarHistory();
      setSidebarHistory(updatedSidebar);
      // If deleted thread is selected, clear the chat
      if (selectedHistoryId === threadId) {
        setMessages([]);
        setSelectedHistoryId(null);
        setThreadId(null);
      }
    } catch {
      setError("Failed to delete thread. Please try again.");
    }
  };

  const handleSpreadsheetQuery = async () => {
    const question = spreadsheetQuestion.trim();
    if (!question) {
      setError("Enter a spreadsheet question.");
      return;
    }
    if (spreadsheetSource === "excel_csv" && !spreadsheetFileDataset) {
      setError("Upload a CSV or XLSX file first.");
      return;
    }
    if (spreadsheetSource === "google_sheets" && !spreadsheetUrl.trim()) {
      setError("Enter Google Sheets URL.");
      return;
    }

    setError(null);
    setSpreadsheetAnswer(null);
    setSpreadsheetPandasCode(null);
    setSpreadsheetLoading(true);

    try {
      let dataset = activeSpreadsheetDataset;
      let sessionId = spreadsheetSessionId ?? undefined;

      if (spreadsheetSource === "google_sheets") {
        const normalizedUrl = spreadsheetUrl.trim();
        if (!dataset || spreadsheetGoogleSourceUrl !== normalizedUrl) {
          const loadedDataset = await dataQueryService.loadGoogleSheet(normalizedUrl, sessionId);
          dataset = loadedDataset;
          sessionId = loadedDataset.session_id;
          setSpreadsheetSessionId(loadedDataset.session_id);
          setSpreadsheetGoogleDataset(loadedDataset);
          setSpreadsheetGoogleSourceUrl(normalizedUrl);
          setSpreadsheetSelectedSheet(loadedDataset.sheets[0] || "");
          setSpreadsheetUploadMessage(`Loaded Google Sheet: ${loadedDataset.source_name}`);
        }
      }

      if (!dataset) {
        throw new Error("No spreadsheet dataset is loaded.");
      }

      const sheetName =
        spreadsheetSelectedSheet && dataset.sheets.includes(spreadsheetSelectedSheet)
          ? spreadsheetSelectedSheet
          : (dataset.sheets[0] ?? undefined);

      if (sheetName && sheetName !== spreadsheetSelectedSheet) {
        setSpreadsheetSelectedSheet(sheetName);
      }

      const answer = await dataQueryService.askQuestion({
        sessionId: sessionId ?? dataset.session_id,
        datasetId: dataset.dataset_id,
        sheetName,
        question,
        includePandasCode: spreadsheetMode === "dataframe",
      });

      setSpreadsheetSessionId(answer.session_id);
      setSpreadsheetAnswer(answer.answer);
      setSpreadsheetPandasCode(answer.pandas_code ?? null);
    } catch (err) {
      setError(formatSpreadsheetRequestError(err, "Failed to run spreadsheet query."));
    } finally {
      setSpreadsheetLoading(false);
    }
  };

  const handleSpreadsheetFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const extension = file.name.split(".").pop()?.toLowerCase() || "";
    if (!["csv", "xlsx", "xls"].includes(extension)) {
      setError("Only CSV and XLSX files are supported in Spreadsheet mode.");
      return;
    }

    setError(null);
    setSpreadsheetUploadMessage("Uploading file...");
    setSpreadsheetAnswer(null);
    setSpreadsheetPandasCode(null);
    try {
      const uploadResult = await dataQueryService.uploadFile(file, spreadsheetSessionId ?? undefined);
      setSpreadsheetSessionId(uploadResult.session_id);
      setSpreadsheetFileDataset(uploadResult);
      setSpreadsheetFileName(file.name);
      setSpreadsheetSelectedSheet(uploadResult.sheets[0] || "");
      setSpreadsheetUploadMessage(`Uploaded: ${file.name} (${uploadResult.rows} rows)`);
    } catch (uploadError) {
      setSpreadsheetUploadMessage(null);
      setError(formatSpreadsheetRequestError(uploadError, "Spreadsheet upload failed."));
    } finally {
      if (event.target) {
        event.target.value = "";
      }
    }
  };

  if (loadingHistory) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading chat history...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-3xl font-bold">Gemini Chatbot</h1>
          <div className="flex items-center gap-4">
            <button
              onClick={() => window.open("http://localhost:5173/research-digest", "_blank")}
              className="inline-flex items-center gap-2 rounded-2xl border border-cyan-300 bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-700 transition hover:bg-cyan-100"
              title="Open Research Digest Agent in a new tab"
            >
              <span aria-hidden="true">✓</span>
              Research Digest Agent
            </button>
            <button
              onClick={() => window.open("http://localhost:5173/tic-tac-toe", "_blank")}
              className="inline-flex items-center gap-2 rounded-2xl border border-indigo-300 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100"
              title="Open Tic Tac Toe Agent in a new tab"
            >
              <span aria-hidden="true">🎮</span>
              Tic Tac Toe Agent
            </button>
            <a
              href="/csv-query-agent"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100"
              title="Open CSV / Google Sheets Query Agent in a new tab"
            >
              <span aria-hidden="true">▦</span>
              CSV / Sheets Agent
            </a>
            {user && <span className="text-sm text-slate-600">Welcome, {user.name}</span>}
            <button
              onClick={handleLogout}
              className="bg-red-600 hover:bg-red-700 text-white text-sm font-semibold py-2 px-4 rounded-2xl transition"
            >
              Logout
            </button>
          </div>
    </div>
        </div>
        <p className="mt-2 text-slate-600">Ask the model a question and receive an answer from the backend.</p>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <aside className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm lg:h-[70vh] lg:overflow-y-auto">
            <button
              onClick={() => {
                setSidebarView("chat");
                void handleNewChat();
              }}
              className="w-full mb-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold py-2 px-3 transition text-left"
            >
              + New Chat
            </button>
            <button
              onClick={() => {
                setSidebarView("chat");
                void handleModeSwitch("db");
              }}
              className="w-full mb-2 rounded-xl bg-slate-700 hover:bg-slate-800 text-white text-sm font-semibold py-2 px-3 transition text-left"
            >
              Query DB
            </button>
            <button
              onClick={() => {
                setSidebarView("spreadsheet");
                void handleModeSwitch("db");
              }}
              className={`w-full mb-4 rounded-xl text-white text-sm font-semibold py-2 px-3 transition text-left ${
                sidebarView === "spreadsheet" ? "bg-emerald-700" : "bg-emerald-600 hover:bg-emerald-700"
              }`}
            >
              Spreadsheet
            </button>
            <button
              onClick={() => {
                window.open(`${window.location.origin}/tickets`, "_blank", "noopener,noreferrer");
              }}
              className="w-full mb-4 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold py-2 px-3 transition text-left"
            >
              Tickets
            </button>

            <RagDebugPanel
              data={ragDebug}
              loading={ragDebugLoading}
              error={ragDebugError}
              onRefresh={() => {
                void loadRagDebug();
              }}
            />
            <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Chat Mode</h2>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    void handleModeSwitch("normal");
                  }}
                  className={`rounded-xl border px-2 py-2 text-xs font-semibold transition ${
                    chatMode === "normal"
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  Normal
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleModeSwitch("rag");
                  }}
                  className={`rounded-xl border px-2 py-2 text-xs font-semibold transition ${
                    chatMode === "rag"
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  RAG
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleModeSwitch("db");
                  }}
                  className={`rounded-xl border px-2 py-2 text-xs font-semibold transition ${
                    chatMode === "db"
                      ? "border-emerald-600 bg-emerald-600 text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  DB Query
                </button>
              </div>
            </div>
            <button
              onClick={handleNewChat}
              className="w-full mb-4 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 transition flex items-center justify-center gap-2"
            >
              <span className="text-lg">+</span>
              New Chat
            </button>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Your History</h2>
            {sidebarHistory.length === 0 ? (
              <p className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-500">No chat history yet.</p>
            ) : (
              <div className="space-y-2">
                {sidebarHistory.map((item) => (
                  <div
                    key={item.id}
                    className="group relative"
                  >
                    <button
                      type="button"
                      onClick={() => handleHistorySelect(item.id)}
                      className={`w-full rounded-2xl border p-3 text-left transition ${
                        selectedHistoryId === item.id
                          ? "border-slate-900 bg-slate-900 text-white"
                          : "border-slate-200 bg-white text-slate-900 hover:bg-slate-50"
                      }`}
                    >
                      <p className="truncate text-sm font-medium">{item.title}</p>
                      <p className={`mt-2 text-xs ${selectedHistoryId === item.id ? "text-slate-200" : "text-slate-500"}`}>
                        {new Date(item.created_at).toLocaleString()}
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteThread(e, item.id)}
                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-red-600 hover:bg-red-700 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm"
                      title="Delete this thread"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </aside>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm lg:h-[70vh] lg:overflow-y-auto">
            {sidebarView === "spreadsheet" ? (
              <div className="space-y-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-800">Query Spreadsheet</h2>
                    <p className="text-sm text-slate-500">Ask questions about your spreadsheet in plain English.</p>
                  </div>
                  <div className="inline-flex rounded-full border border-slate-200 bg-white p-1 shadow-sm">
                    <button
                      type="button"
                      onClick={() => setSpreadsheetMode("existing_chat")}
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${spreadsheetMode === "existing_chat" ? "bg-slate-100 text-slate-900" : "text-slate-500"}`}
                    >
                      Existing Chat
                    </button>
                    <button
                      type="button"
                      onClick={() => setSpreadsheetMode("nl_sql")}
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${spreadsheetMode === "nl_sql" ? "bg-slate-100 text-slate-900" : "text-slate-500"}`}
                    >
                      NL-SQL
                    </button>
                    <button
                      type="button"
                      onClick={() => setSpreadsheetMode("dataframe")}
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${spreadsheetMode === "dataframe" ? "bg-emerald-600 text-white" : "text-slate-500"}`}
                    >
                      DataFrame
                    </button>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="mb-4 flex gap-6 text-sm text-slate-700">
                    <label className="inline-flex items-center gap-2">
                      <input
                        type="radio"
                        checked={spreadsheetSource === "google_sheets"}
                        onChange={() => {
                          setSpreadsheetSource("google_sheets");
                          setSpreadsheetAnswer(null);
                          setSpreadsheetPandasCode(null);
                          setSpreadsheetSelectedSheet(spreadsheetGoogleDataset?.sheets[0] || "");
                        }}
                      />
                      Google Sheet
                    </label>
                    <label className="inline-flex items-center gap-2">
                      <input
                        type="radio"
                        checked={spreadsheetSource === "excel_csv"}
                        onChange={() => {
                          setSpreadsheetSource("excel_csv");
                          setSpreadsheetAnswer(null);
                          setSpreadsheetPandasCode(null);
                          setSpreadsheetSelectedSheet(spreadsheetFileDataset?.sheets[0] || "");
                        }}
                      />
                      CSV / XLSX File
                    </label>
                  </div>

                  {spreadsheetSource === "excel_csv" ? (
                    <div className="mb-4 space-y-2">
                      <label className="block text-sm font-semibold text-slate-700">Upload CSV / XLSX</label>
                      <div className="flex items-center gap-3">
                        <input
                          ref={spreadsheetFileInputRef}
                          type="file"
                          accept=".csv,.xlsx,.xls"
                          className="hidden"
                          onChange={handleSpreadsheetFileSelected}
                        />
                        <button
                          type="button"
                          onClick={() => spreadsheetFileInputRef.current?.click()}
                          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                        >
                          Choose File
                        </button>
                        <span className="text-sm text-slate-500">{spreadsheetFileName || "No file chosen"}</span>
                      </div>
                      {spreadsheetUploadMessage ? <p className="text-xs text-slate-500">{spreadsheetUploadMessage}</p> : null}
                    </div>
                  ) : (
                    <div className="mb-4 space-y-2">
                      <label className="block text-sm font-semibold text-slate-700">Google Sheets URL</label>
                      <input
                        value={spreadsheetUrl}
                        onChange={(e) => setSpreadsheetUrl(e.target.value)}
                        placeholder="https://docs.google.com/spreadsheets/d/..."
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                      />
                    </div>
                  )}

                  {activeSpreadsheetDataset?.sheets?.length ? (
                    <div className="mb-4 space-y-2">
                      <label className="block text-sm font-semibold text-slate-700">Worksheet</label>
                      <select
                        value={spreadsheetSelectedSheet}
                        onChange={(e) => setSpreadsheetSelectedSheet(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                      >
                        {activeSpreadsheetDataset.sheets.map((sheet) => (
                          <option key={sheet} value={sheet}>
                            {sheet}
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-slate-500">
                        {activeSpreadsheetDataset.rows} rows loaded from {activeSpreadsheetDataset.source_name}
                      </p>
                    </div>
                  ) : null}

                  <div className="space-y-2">
                    <label className="block text-sm font-semibold text-slate-700">Question</label>
                    <textarea
                      value={spreadsheetQuestion}
                      onChange={(e) => setSpreadsheetQuestion(e.target.value)}
                      placeholder="what is the payment method of Ivy Wilson?"
                      rows={4}
                      className="w-full rounded-lg border border-slate-300 px-3 py-3 text-sm focus:border-slate-500 focus:outline-none"
                    />
                  </div>

                  <div className="mt-4 flex justify-start">
                    <button
                      type="button"
                      onClick={() => {
                        void handleSpreadsheetQuery();
                      }}
                      disabled={spreadsheetLoading || loading}
                      className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                    >
                      {spreadsheetLoading ? "Analyzing..." : "Analyze"}
                    </button>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="mb-3 text-lg font-semibold text-slate-800">Answer</h3>
                  {spreadsheetAnswer ? (
                    <div className="space-y-2 text-sm text-slate-700">
                      <pre className="whitespace-pre-wrap break-words font-sans text-sm text-slate-700">{spreadsheetAnswer}</pre>
                      {spreadsheetPandasCode ? (
                        <div className="rounded-2xl bg-slate-50 p-3">
                          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Pandas Code</p>
                          <pre className="whitespace-pre-wrap break-words text-xs text-slate-700">{spreadsheetPandasCode}</pre>
                        </div>
                      ) : null}
                      {activeSpreadsheetDataset?.source_name ? (
                        <p className="text-xs text-slate-500">Source: {activeSpreadsheetDataset.source_name}</p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">Run an analysis to see the answer here.</p>
                  )}
                </div>
              </div>
            ) : null}

            {sidebarView !== "spreadsheet" ? (
            <>
            <div className="space-y-4">
              {messages.length === 0 && (
                <div className="text-center text-slate-500 py-8">
                  <p>No messages yet. Start a conversation!</p>
                </div>
              )}
              {messages.map((message, index) => (
                <div
                  key={message.id || index}
                  id={message.id ? `chat-message-${message.id}` : undefined}
                  className={message.role === "user" ? "text-right" : "text-left"}
                >
                  <div
                    className="inline-block max-w-[90%] rounded-2xl px-4 py-3 text-sm shadow-sm"
                    style={{
                      backgroundColor: message.role === "user" ? "#2563eb" : "#f8fafc",
                      color: message.role === "user" ? "white" : "#0f172a",
                    }}
                  >
                    {message.role === "assistant" && message.mode_used ? (
                      <div className="mb-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                            message.mode_used === "rag"
                              ? "bg-blue-100 text-blue-700"
                              : message.mode_used === "db"
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-slate-200 text-slate-700"
                          }`}
                        >
                          {message.mode_used === "rag" ? "RAG" : message.mode_used === "db" ? "DB" : "Normal"}
                        </span>
                      </div>
                    ) : null}
                    {message.image_loading ? (
                      <ImageGenerationLoading prompt={message.image_prompt} />
                    ) : (
                      <>
                        <MessageContent
                          content={message.content}
                          attachments={
                            message.is_image_generation
                              ? (message.attachments || []).filter((attachment) => attachment.category !== "image")
                              : message.attachments
                          }
                        />
                        {message.image_error ? <ImageGenerationError message={message.image_error} /> : null}
                        {message.is_image_generation && message.attachments && message.attachments.length > 0 && (
                          <GeneratedImageCard
                            attachment={message.attachments[0]}
                            prompt={message.image_prompt || extractImagePrompt(message.content) || ""}
                            onRegenerate={handleGenerateImage}
                            disabled={imageGenerating || loading}
                          />
                        )}
                      </>
                    )}
                  </div>
                  {message.created_at && (
                    <div className="text-xs text-slate-400 mt-1">{new Date(message.created_at).toLocaleString()}</div>
                  )}
                </div>
              ))}
            </div>

            <form className="mt-6 flex gap-3" onSubmit={handleSubmit}>
              <div className="w-full space-y-3">
                <AttachmentComposer
                  attachments={attachments}
                  disabled={loading || imageGenerating}
                  onFilesAdded={handleFilesAdded}
                  onRemoveAttachment={handleRemoveAttachment}
                  onClearAttachments={() => {
                    void clearAttachments();
                  }}
                  helperText={attachmentHint}
                />

                <div className="flex gap-3">
                  <input
                    className="flex-1 rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-slate-500 focus:outline-none"
                    placeholder={
                      chatMode === "rag"
                        ? "Ask using your indexed documents..."
                        : chatMode === "db"
                          ? "Ask about your Supabase data (e.g., users, chats, attachments)..."
                          : "Type your question..."
                    }
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={loading || imageGenerating}
                  />
                  <button
                    type="button"
                    className="rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={loading || imageGenerating || !imageCapabilityAvailable}
                    onClick={() => {
                      void handleGenerateImage();
                    }}
                    title={!imageCapabilityAvailable ? imageCapabilityReason || "Image generation unavailable" : undefined}
                  >
                    {!imageCapabilityAvailable ? "Image Unavailable" : imageGenerating ? "Generating..." : "Generate Image"}
                  </button>
                  <button
                    type="submit"
                    className="rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                    disabled={loading || imageGenerating}
                  >
                    {loading ? `Sending ${requestUploadProgress}%` : "Send"}
                  </button>
                </div>
              </div>
            </form>

            {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
            {!imageCapabilityAvailable && imageCapabilityReason ? (
              <p className="mt-2 text-sm text-amber-700">{imageCapabilityReason}</p>
            ) : null}
            {imageCapabilityModel ? (
              <p className="mt-2 text-xs text-slate-500">
                Image model: {imageCapabilityModel}
                {imageCapabilityFallbackModels.length > 0
                  ? ` | Fallbacks: ${imageCapabilityFallbackModels.join(", ")}`
                  : ""}
              </p>
            ) : null}
            <p className="mt-1 text-xs text-slate-500">
              Chat mode: {chatMode === "rag" ? "RAG (uses indexed chunks)" : chatMode === "db" ? "DB Query (Supabase)" : "Normal"}
            </p>
            {chatMode === "rag" ? (
              <p className="mt-1 text-xs text-slate-500">
                Selected RAG docs: {ragSelectedAttachmentIds.length}
              </p>
            ) : null}
            <label className="mt-2 inline-flex items-center gap-2 text-xs text-slate-600">
              Default mode:
              <select
                value={defaultChatMode}
                onChange={(event) => {
                  setDefaultChatMode(normalizeMode(event.target.value));
                }}
                className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs"
              >
                <option value="normal">Normal</option>
                <option value="rag">RAG</option>
                <option value="db">DB Query</option>
              </select>
            </label>
            </>
            ) : null}
        </div>
      </div>
    </div>
  );
}

function CsvGoogleSheetsQueryAgentScreen() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [spreadsheetSource, setSpreadsheetSource] = useState<SpreadsheetSource>("google_sheets");
  const [spreadsheetMode, setSpreadsheetMode] = useState<SpreadsheetMode>("dataframe");
  const [spreadsheetUrl, setSpreadsheetUrl] = useState("");
  const [spreadsheetQuestion, setSpreadsheetQuestion] = useState("");
  const [spreadsheetLoading, setSpreadsheetLoading] = useState(false);
  const [spreadsheetSessionId, setSpreadsheetSessionId] = useState<string | null>(null);
  const [spreadsheetFileDataset, setSpreadsheetFileDataset] = useState<DataQueryDatasetResponse | null>(null);
  const [spreadsheetGoogleDataset, setSpreadsheetGoogleDataset] = useState<DataQueryDatasetResponse | null>(null);
  const [spreadsheetGoogleSourceUrl, setSpreadsheetGoogleSourceUrl] = useState("");
  const [spreadsheetFileName, setSpreadsheetFileName] = useState<string | null>(null);
  const [spreadsheetSelectedSheet, setSpreadsheetSelectedSheet] = useState("");
  const [spreadsheetUploadMessage, setSpreadsheetUploadMessage] = useState<string | null>(null);
  const [spreadsheetAnswer, setSpreadsheetAnswer] = useState<string | null>(null);
  const [spreadsheetPandasCode, setSpreadsheetPandasCode] = useState<string | null>(null);
  const spreadsheetFileInputRef = useRef<HTMLInputElement | null>(null);

  const activeSpreadsheetDataset =
    spreadsheetSource === "excel_csv" ? spreadsheetFileDataset : spreadsheetGoogleDataset;

  const handleSpreadsheetQuery = async () => {
    const question = spreadsheetQuestion.trim();
    if (!question) {
      setError("Enter a spreadsheet question.");
      return;
    }
    if (spreadsheetSource === "excel_csv" && !spreadsheetFileDataset) {
      setError("Upload a CSV or XLSX file first.");
      return;
    }
    if (spreadsheetSource === "google_sheets" && !spreadsheetUrl.trim()) {
      setError("Enter Google Sheets URL.");
      return;
    }

    setError(null);
    setSpreadsheetAnswer(null);
    setSpreadsheetPandasCode(null);
    setSpreadsheetLoading(true);

    try {
      let dataset = activeSpreadsheetDataset;
      let sessionId = spreadsheetSessionId ?? undefined;

      if (spreadsheetSource === "google_sheets") {
        const normalizedUrl = spreadsheetUrl.trim();
        if (!dataset || spreadsheetGoogleSourceUrl !== normalizedUrl) {
          const loadedDataset = await dataQueryService.loadGoogleSheet(normalizedUrl, sessionId);
          dataset = loadedDataset;
          sessionId = loadedDataset.session_id;
          setSpreadsheetSessionId(loadedDataset.session_id);
          setSpreadsheetGoogleDataset(loadedDataset);
          setSpreadsheetGoogleSourceUrl(normalizedUrl);
          setSpreadsheetSelectedSheet(loadedDataset.sheets[0] || "");
          setSpreadsheetUploadMessage(`Loaded Google Sheet: ${loadedDataset.source_name}`);
        }
      }

      if (!dataset) {
        throw new Error("No spreadsheet dataset is loaded.");
      }

      const sheetName =
        spreadsheetSelectedSheet && dataset.sheets.includes(spreadsheetSelectedSheet)
          ? spreadsheetSelectedSheet
          : (dataset.sheets[0] ?? undefined);

      if (sheetName && sheetName !== spreadsheetSelectedSheet) {
        setSpreadsheetSelectedSheet(sheetName);
      }

      const answer = await dataQueryService.askQuestion({
        sessionId: sessionId ?? dataset.session_id,
        datasetId: dataset.dataset_id,
        sheetName,
        question,
        includePandasCode: spreadsheetMode === "dataframe",
      });

      setSpreadsheetSessionId(answer.session_id);
      setSpreadsheetAnswer(answer.answer);
      setSpreadsheetPandasCode(answer.pandas_code ?? null);
    } catch (err) {
      setError(formatSpreadsheetRequestError(err, "Failed to run spreadsheet query."));
    } finally {
      setSpreadsheetLoading(false);
    }
  };

  const handleSpreadsheetFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const extension = file.name.split(".").pop()?.toLowerCase() || "";
    if (!["csv", "xlsx", "xls"].includes(extension)) {
      setError("Only CSV and XLSX files are supported in Spreadsheet mode.");
      return;
    }

    setError(null);
    setSpreadsheetUploadMessage("Uploading file...");
    setSpreadsheetAnswer(null);
    setSpreadsheetPandasCode(null);
    try {
      const uploadResult = await dataQueryService.uploadFile(file, spreadsheetSessionId ?? undefined);
      setSpreadsheetSessionId(uploadResult.session_id);
      setSpreadsheetFileDataset(uploadResult);
      setSpreadsheetFileName(file.name);
      setSpreadsheetSelectedSheet(uploadResult.sheets[0] || "");
      setSpreadsheetUploadMessage(`Uploaded: ${file.name} (${uploadResult.rows} rows)`);
    } catch (uploadError) {
      setSpreadsheetUploadMessage(null);
      setError(formatSpreadsheetRequestError(uploadError, "Spreadsheet upload failed."));
    } finally {
      if (event.target) {
        event.target.value = "";
      }
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">CSV / Google Sheets Query Agent</h1>
            <p className="text-sm text-slate-500">Upload a file or load a Google Sheet, then query it in natural language.</p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/", { replace: true })}
            className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
          >
            <span aria-hidden="true">←</span>
            Return
          </button>
        </div>

        {error ? <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        <div className="space-y-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-slate-800">Query Spreadsheet</h2>
              <p className="text-sm text-slate-500">Ask questions about your spreadsheet in plain English.</p>
            </div>
            <div className="inline-flex rounded-full border border-slate-200 bg-white p-1 shadow-sm">
              <button
                type="button"
                onClick={() => setSpreadsheetMode("existing_chat")}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${spreadsheetMode === "existing_chat" ? "bg-slate-100 text-slate-900" : "text-slate-500"}`}
              >
                Existing Chat
              </button>
              <button
                type="button"
                onClick={() => setSpreadsheetMode("nl_sql")}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${spreadsheetMode === "nl_sql" ? "bg-slate-100 text-slate-900" : "text-slate-500"}`}
              >
                NL-SQL
              </button>
              <button
                type="button"
                onClick={() => setSpreadsheetMode("dataframe")}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${spreadsheetMode === "dataframe" ? "bg-emerald-600 text-white" : "text-slate-500"}`}
              >
                DataFrame
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap gap-6 text-sm text-slate-700">
              <label className="inline-flex items-center gap-2">
                <input
                  type="radio"
                  checked={spreadsheetSource === "google_sheets"}
                  onChange={() => {
                    setSpreadsheetSource("google_sheets");
                    setSpreadsheetAnswer(null);
                    setSpreadsheetPandasCode(null);
                    setSpreadsheetSelectedSheet(spreadsheetGoogleDataset?.sheets[0] || "");
                  }}
                />
                Google Sheet
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="radio"
                  checked={spreadsheetSource === "excel_csv"}
                  onChange={() => {
                    setSpreadsheetSource("excel_csv");
                    setSpreadsheetAnswer(null);
                    setSpreadsheetPandasCode(null);
                    setSpreadsheetSelectedSheet(spreadsheetFileDataset?.sheets[0] || "");
                  }}
                />
                CSV / XLSX File
              </label>
            </div>

            {spreadsheetSource === "excel_csv" ? (
              <div className="mb-4 space-y-2">
                <label className="block text-sm font-semibold text-slate-700">Upload CSV / XLSX</label>
                <div className="flex flex-wrap items-center gap-3">
                  <input
                    ref={spreadsheetFileInputRef}
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    className="hidden"
                    onChange={handleSpreadsheetFileSelected}
                  />
                  <button
                    type="button"
                    onClick={() => spreadsheetFileInputRef.current?.click()}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                  >
                    Choose File
                  </button>
                  <span className="text-sm text-slate-500">{spreadsheetFileName || "No file chosen"}</span>
                </div>
                {spreadsheetUploadMessage ? <p className="text-xs text-slate-500">{spreadsheetUploadMessage}</p> : null}
              </div>
            ) : (
              <div className="mb-4 space-y-2">
                <label className="block text-sm font-semibold text-slate-700">Google Sheets URL</label>
                <input
                  value={spreadsheetUrl}
                  onChange={(e) => setSpreadsheetUrl(e.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/..."
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                />
              </div>
            )}

            {activeSpreadsheetDataset?.sheets?.length ? (
              <div className="mb-4 space-y-2">
                <label className="block text-sm font-semibold text-slate-700">Worksheet</label>
                <select
                  value={spreadsheetSelectedSheet}
                  onChange={(e) => setSpreadsheetSelectedSheet(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                >
                  {activeSpreadsheetDataset.sheets.map((sheet) => (
                    <option key={sheet} value={sheet}>
                      {sheet}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500">
                  {activeSpreadsheetDataset.rows} rows loaded from {activeSpreadsheetDataset.source_name}
                </p>
              </div>
            ) : null}

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-slate-700">Question</label>
              <textarea
                value={spreadsheetQuestion}
                onChange={(e) => setSpreadsheetQuestion(e.target.value)}
                placeholder="what is the payment method of Ivy Wilson?"
                rows={4}
                className="w-full rounded-lg border border-slate-300 px-3 py-3 text-sm focus:border-slate-500 focus:outline-none"
              />
            </div>

            <div className="mt-4 flex justify-start">
              <button
                type="button"
                onClick={() => {
                  void handleSpreadsheetQuery();
                }}
                disabled={spreadsheetLoading}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                {spreadsheetLoading ? "Analyzing..." : "Analyze"}
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 text-lg font-semibold text-slate-800">Answer</h3>
            {spreadsheetAnswer ? (
              <div className="space-y-2 text-sm text-slate-700">
                <pre className="whitespace-pre-wrap break-words font-sans text-sm text-slate-700">{spreadsheetAnswer}</pre>
                {spreadsheetPandasCode ? (
                  <div className="rounded-2xl bg-slate-50 p-3">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Pandas Code</p>
                    <pre className="whitespace-pre-wrap break-words text-xs text-slate-700">{spreadsheetPandasCode}</pre>
                  </div>
                ) : null}
                {activeSpreadsheetDataset?.source_name ? (
                  <p className="text-xs text-slate-500">Source: {activeSpreadsheetDataset.source_name}</p>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-slate-400">Run an analysis to see the answer here.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      if (!authService.isAuthenticated()) {
        setIsAuthenticated(false);
        return;
      }

      try {
        await authService.getCurrentUser();
        setIsAuthenticated(true);
      } catch {
        authService.logout();
        setIsAuthenticated(false);
      }
    };

    void checkAuth();
  }, []);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/" element={isAuthenticated ? <ChatApp /> : <Navigate to="/login" replace />} />
        <Route
          path="/csv-query-agent"
          element={isAuthenticated ? <CsvGoogleSheetsQueryAgentScreen /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/research-digest"
          element={isAuthenticated ? <ResearchDigest /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/tic-tac-toe"
          element={isAuthenticated ? <TicTacToe /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/tickets"
          element={isAuthenticated ? <Tickets /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/tickets/:ticketId"
          element={isAuthenticated ? <TicketDetailPage /> : <Navigate to="/login" replace />}
        />
      </Routes>
    </Router>
  );
}

export default App;

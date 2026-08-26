import {
  ArrowRightLeft,
  BarChart3,
  Bot,
  BookOpen,
  Check,
  Copy,
  Download,
  Loader2,
  MapPin,
  MessageSquareText,
  Mic,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  ListChecks,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  UserPlus,
  Volume2,
  Waves,
} from "lucide-react";
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import ChatSections from "@/components/ChatSections";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage, type Language } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";
import { getApiError } from "@/services/api";
import { fetchStates, fetchSummary } from "@/services/groundwater";
import {
  deleteConversation,
  bulkDeleteConversations,
  exportConversation,
  listConversations,
  listMessages,
  rateMessage,
  regenerateAnswer,
  sendMessage,
  transcribeAudio,
  type ChatMessage,
  type Conversation,
} from "@/services/chat";
import { createExpertRequest } from "@/services/expert";
import type { GroundwaterState, GroundwaterSummary } from "@/types";

const LANGUAGE_LABELS: Record<string, string> = {
  en: "English",
  te: "తెలుగు",
  hi: "हिन्दी",
};

const SPEECH_LANGS: Record<Language, string> = {
  en: "en-IN",
  te: "te-IN",
  hi: "hi-IN",
};

type MicLang = Language | "auto";

const INTENT_LABELS: Record<string, string> = {
  greeting: "Greeting",
  help: "Help",
  terminology: "Terminology",
  data_query: "Data",
  forecast: "Forecast",
  scenario: "Scenario",
  recommend: "Recommendation",
  thanks: "Thanks",
  fallback: "Unclear",
};

const CATEGORY_COLORS: Record<string, string> = {
  Safe: "#16a34a",
  "Semi-critical": "#f59e0b",
  Critical: "#f97316",
  "Over-exploited": "#dc2626",
};

function formatValue(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(value);
}

function deltaOf(a: number | null | undefined, b: number | null | undefined): string | null {
  if (a === null || a === undefined || b === null || b === undefined) return null;
  const d = b - a;
  return `${d > 0 ? "+" : ""}${formatValue(d)}`;
}

function pctOf(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

const EXAMPLES = [
  { icon: Waves, text: "What is the stage of extraction in Telangana?" },
  { icon: BarChart3, text: "Recharge in Guntur district" },
  { icon: MapPin, text: "Water situation in Guntur Village" },
  { icon: BookOpen, text: "What is an aquifer?" },
];

const CAPABILITIES = [
  { label: "Recharge in a state", prompt: "What is the recharge in Telangana?" },
  { label: "Stage of extraction", prompt: "What is the stage of extraction in Andhra Pradesh?" },
  { label: "Groundwater status", prompt: "What is the groundwater status of Andhra Pradesh?" },
  { label: "Over-exploited districts", prompt: "Which districts are over-exploited in Andhra Pradesh?" },
  { label: "Why is it declining", prompt: "Why is groundwater declining in Andhra Pradesh?" },
  { label: "Measures to reduce extraction", prompt: "What measures can reduce groundwater extraction?" },
  { label: "Compare across years", prompt: "What was the stage of extraction in Telangana in 2021?" },
  { label: "Forecast a trend", prompt: "What is the predicted groundwater trend in Punjab next 5 years?" },
  { label: "What-if scenario", prompt: "What if pumping increases 10% in Telangana?" },
  { label: "Explain a term", prompt: "What is an aquifer?" },
];

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days}d`;
}

function renderInline(text: string) {
  const parts = text.split("**");
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-semibold">
        {part}
      </strong>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    )
  );
}

function MdTable({ block }: { block: string[] }) {
  const rows = block
    .map((line) =>
      line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((c) => c.trim())
    )
    .filter((cells) => !cells.every((c) => /^:?-{3,}:?$/.test(c) || c === ""));
  if (!rows.length) return null;
  const [header, ...body] = rows;
  return (
    <div className="my-1 overflow-x-auto rounded-lg border">
      <table className="w-full text-left text-xs">
        <thead className="bg-muted/40">
          <tr>
            {header.map((cell, ci) => (
              <th key={ci} className="px-2.5 py-1.5 font-semibold">
                {renderInline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((cells, ri) => (
            <tr key={ri} className="border-t">
              {cells.map((cell, ci) => (
                <td key={ci} className="px-2.5 py-1.5">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderContent(content: string) {
  const lines = content.split("\n");
  const out: JSX.Element[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.startsWith("|")) {
      const block: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        block.push(lines[i]);
        i++;
      }
      out.push(<MdTable key={`tbl-${i}`} block={block} />);
      continue;
    }
    if (trimmed.startsWith("•")) {
      out.push(
        <div key={i} className="flex gap-2">
          <span className="mt-px shrink-0 text-primary">•</span>
          <span>{renderInline(trimmed.slice(1))}</span>
        </div>
      );
      i++;
      continue;
    }
    if (!trimmed) {
      out.push(<div key={i} className="h-1" />);
      i++;
      continue;
    }
    // Markdown headings inside answers render as emphasised text.
    const headingMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
    if (headingMatch) {
      out.push(
        <div key={i} className="pt-1 text-sm font-semibold">
          {renderInline(headingMatch[2])}
        </div>
      );
      i++;
      continue;
    }
    out.push(<div key={i}>{renderInline(line)}</div>);
    i++;
  }
  return out;
}

export default function Assistant() {
  const { user } = useAuth();
  const { lang, t } = useLanguage();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [latencies, setLatencies] = useState<Record<number, number | null>>({});
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [voicePref, setVoicePref] = useState<"male" | "female">(
    () =>
      (typeof window !== "undefined" &&
        (localStorage.getItem("ingres_tts_voice") as "male" | "female" | null)) ||
      "female"
  );
  // Language the microphone listens for — independent of the UI language.
  // "auto" records audio and lets server-side Whisper detect Telugu/Hindi/
  // English automatically; a fixed language uses fast live browser dictation.
  const [micLang, setMicLang] = useState<MicLang>(() => {
    if (typeof window === "undefined") return "auto";
    const stored = localStorage.getItem("ingres_mic_lang") as MicLang | null;
    return stored === "te" || stored === "hi" || stored === "en" || stored === "auto"
      ? stored
      : "auto";
  });

  function changeMicLang(next: MicLang) {
    setMicLang(next);
    try {
      localStorage.setItem("ingres_mic_lang", next);
    } catch {
      /* ignore */
    }
  }
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [compareStates, setCompareStates] = useState<GroundwaterState[]>([]);
  const [compareResult, setCompareResult] = useState<
    { a: GroundwaterSummary; b: GroundwaterSummary } | null
  >(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [escalated, setEscalated] = useState<Record<number, boolean>>({});
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [retryText, setRetryText] = useState<Record<number, string>>({});
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recognitionRef = useRef<any>(null);
  const dictationBaseRef = useRef("");
  const lastVoiceRef = useRef(false);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordingActiveRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const speechSupported =
    typeof window !== "undefined" &&
    !!window.isSecureContext &&
    typeof MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia;

  const SPEECH_ERROR_MESSAGES: Record<string, string> = {
    "not-allowed": t(
      "Microphone permission was denied. Allow the microphone in your browser settings and try again."
    ),
    "permission-denied": t(
      "Microphone permission was denied. Allow the microphone in your browser settings and try again."
    ),
    "NotAllowedError": t(
      "Microphone permission was denied. Allow the microphone in your browser settings and try again."
    ),
    "audio-capture": t("No microphone was found. Connect a microphone and try again."),
    "NotFoundError": t("No microphone was found. Connect a microphone and try again."),
    "OverconstrainedError": t("No microphone was found. Connect a microphone and try again."),
    "NotReadableError": t("The microphone is in use by another application."),
    "no-speech": t("No speech was detected. Please speak clearly and try again."),
    "network": t("The speech service could not be reached. Check your internet connection."),
    "service-not-allowed": t(
      "Speech recognition is not allowed on this connection. Open the app via http://localhost:5173 or HTTPS."
    ),
    "aborted": "",
  };

  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 12) return t("Good morning");
    if (h < 17) return t("Good afternoon");
    return t("Good evening");
  }, [t]);

  const filteredConversations = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => (c.title ?? "").toLowerCase().includes(q));
  }, [conversations, search]);

  useEffect(() => {
    listConversations()
      .then(setConversations)
      .catch(() => undefined)
      .finally(() => setLoadingList(false));
    fetchStates()
      .then((rows) => setCompareStates(rows))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!activeId) return;
    setLoadingMsgs(true);
    listMessages(activeId)
      .then(setMessages)
      .catch(() => setMessages([]))
      .finally(() => setLoadingMsgs(false));
  }, [activeId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const stopListening = useCallback(() => {
    recordingActiveRef.current = false;
    try {
      recognitionRef.current?.abort?.();
    } catch {
      /* ignore */
    }
    recognitionRef.current = null;
    try {
      mediaRecorderRef.current?.stop();
    } catch {
      /* ignore */
    }
    try {
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    } catch {
      /* ignore */
    }
    setListening(false);
  }, []);

  useEffect(() => {
    return () => {
      stopListening();
      try {
        audioRef.current?.pause();
      } catch {
        /* ignore */
      }
    };
  }, [stopListening]);

  function stopSpeaking() {
    try {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      audioRef.current?.pause();
    } catch {
      /* ignore */
    }
  }

  function toggleListening() {
    if (listening) {
      stopListening();
      return;
    }
    // Tapping the mic interrupts whatever the assistant is saying.
    stopSpeaking();
    if (!window.isSecureContext) {
      setSpeechError(
        t(
          "Microphone access requires a secure connection. Open the app via http://localhost:5173 or HTTPS."
        )
      );
      return;
    }
    setSpeechError(null);

    // Live dictation: the browser's SpeechRecognition streams interim results
    // into the input box WHILE you speak, then auto-sends on the final result.
    // Only for a fixed mic language — "auto" uses Whisper detection below.
    const SRC = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SRC && micLang !== "auto") {
      const rec = new SRC();
      rec.lang = SPEECH_LANGS[micLang];
      rec.continuous = false;
      rec.interimResults = true;
      rec.maxAlternatives = 1;

      let finalText = "";
      let sent = false;
      const deliver = () => {
        if (sent) return;
        sent = true;
        setListening(false);
        recognitionRef.current = null;
        const text = finalText.trim() || (input || "").trim();
        if (!text) {
          setSpeechError(t("I didn't catch that. Tap the mic and try again."));
          return;
        }
        setInput(text);
        textareaRef.current?.focus();
        lastVoiceRef.current = true;
        setTimeout(() => void handleSend(text), 400);
      };

      rec.onresult = (event: any) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const r = event.results[i];
          if (r.isFinal) finalText += r[0].transcript;
          else interim += r[0].transcript;
        }
        // Live typing into the box as you speak.
        setInput((dictationBaseRef.current + " " + (finalText + " " + interim)).trim());
      };
      rec.onerror = (event: any) => {
        recognitionRef.current = null;
        setListening(false);
        const code = String(event?.error ?? "");
        if (code === "not-allowed" || code === "service-not-allowed") {
          setSpeechError(SPEECH_ERROR_MESSAGES["NotAllowedError"] ?? t("Microphone permission was denied."));
        } else if (code === "no-speech") {
          setSpeechError(t("I didn't hear anything. Tap the mic and speak again."));
        } else if (code !== "aborted") {
          setSpeechError(t("Could not record your voice. Please try again."));
        }
      };
      rec.onend = () => {
        // Chrome ends the session after a pause — deliver whatever we have.
        if (recognitionRef.current === rec) deliver();
      };

      dictationBaseRef.current = input;
      recognitionRef.current = rec;
      setListening(true);
      try {
        rec.start();
      } catch {
        recognitionRef.current = null;
        setListening(false);
      }
      return;
    }

    // Fallback / auto mode: record + server-side Whisper transcription, which
    // detects the spoken language automatically (Telugu/Hindi/English/…).
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setSpeechError(t("Microphone recording is not supported in this browser."));
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        const chunks: Blob[] = [];
        const recorder = new MediaRecorder(stream);
        let levelTimer: number | null = null;
        let analyser: AnalyserNode | null = null;
        let audioCtx: AudioContext | null = null;
        let silentMs = 0;
        let speechSeen = false;
        const startedAt = Date.now();
        const stopRecording = () => {
          try {
            recorder.stop();
          } catch {
            /* ignore */
          }
        };

        try {
          const AC = window.AudioContext || (window as any).webkitAudioContext;
          audioCtx = new AC();
          analyser = audioCtx.createAnalyser();
          analyser.fftSize = 1024;
          audioCtx.createMediaStreamSource(stream).connect(analyser);
        } catch {
          /* ignore */
        }

        const pollLevel = () => {
          if (!recordingActiveRef.current) return;
          if (analyser) {
            const buf = new Uint8Array(analyser.fftSize);
            analyser.getByteTimeDomainData(buf);
            let sum = 0;
            for (let i = 0; i < buf.length; i++) {
              const v = (buf[i] - 128) / 128;
              sum += v * v;
            }
            const rms = Math.sqrt(sum / buf.length);
            if (rms > 0.035) {
              // Real speech detected — only silence *after* this may stop us.
              speechSeen = true;
              silentMs = 0;
            } else if (speechSeen && Date.now() - startedAt > 1200) {
              silentMs += 100;
              if (silentMs >= 2200 || Date.now() - startedAt > 20000) {
                stopRecording();
                return;
              }
            } else if (Date.now() - startedAt > 20000) {
              stopRecording();
              return;
            }
          }
          levelTimer = window.setTimeout(pollLevel, 100);
        };

        recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) chunks.push(event.data);
        };
        recorder.onerror = () => {
          recordingActiveRef.current = false;
          if (levelTimer) window.clearTimeout(levelTimer);
          setListening(false);
          setSpeechError(t("Could not record your voice. Please try again."));
        };
        recorder.onstop = () => {
          recordingActiveRef.current = false;
          if (levelTimer) window.clearTimeout(levelTimer);
          if (audioCtx) audioCtx.close().catch(() => undefined);
          stream.getTracks().forEach((track) => track.stop());
          setListening(false);
          const type = recorder.mimeType || "audio/webm";
          const blob = new Blob(chunks, { type });
          if (blob.size < 1200) {
            setSpeechError(
              t(
                "Your voice was too quiet to record. Speak a little louder and try again."
              )
            );
            return;
          }
          handleVoiceSend(blob);
        };
        mediaRecorderRef.current = recorder;
        mediaStreamRef.current = stream;
        recordingActiveRef.current = true;
        setListening(true);
        recorder.start();
        pollLevel();
      })
      .catch((error: any) => {
        setListening(false);
        const code = String(error?.name ?? error?.code ?? "");
        setSpeechError(
          SPEECH_ERROR_MESSAGES[code] ??
            t("Could not access the microphone. Check the permission and try again.")
        );
      });
  }

  function speak(text: string, language: string | null) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.replace(/\*\*/g, ""));
    utterance.lang = SPEECH_LANGS[(language as Language) ?? "en"] ?? "en-IN";
    window.speechSynthesis.speak(utterance);
  }

  function changeVoicePref(pref: "male" | "female") {
    setVoicePref(pref);
    try {
      localStorage.setItem("ingres_tts_voice", pref);
    } catch {
      /* ignore */
    }
  }

  async function runCompare() {
    if (!compareA || !compareB || compareA === compareB || compareLoading) return;
    setCompareLoading(true);
    setCompareError(null);
    try {
      const [a, b] = await Promise.all([
        fetchSummary({ state: compareA }),
        fetchSummary({ state: compareB }),
      ]);
      setCompareResult({ a, b });
    } catch {
      setCompareError(t("Could not load the comparison. Please try again."));
    } finally {
      setCompareLoading(false);
    }
  }

  async function handleVoiceSend(blob: Blob) {
    if (!blob.size || sending) return;
    setSending(true);
    try {
      // 1) Speech-to-text only — the recognised words appear in the input box.
      const res = await transcribeAudio(blob);
      const text = res.text.trim();
      if (!text) throw new Error("empty");
      setInput((prev) => (prev ? `${prev} ${text}` : text));
      textareaRef.current?.focus();
      lastVoiceRef.current = true;
      // 2) Then send it through the normal text flow to get the answer.
      setTimeout(() => void handleSend(text), 450);
    } catch (err) {
      const detail = getApiError(err);
      setSpeechError(
        detail === "Something went wrong. Please try again."
          ? t("Sorry, I could not hear that clearly. Please try again.")
          : detail
      );
    } finally {
      setSending(false);
    }
  }

  function copyMessage(m: ChatMessage) {
    navigator.clipboard?.writeText(m.content).catch(() => undefined);
    setCopiedId(m.id);
    setTimeout(() => setCopiedId((id) => (id === m.id ? null : id)), 1500);
  }

  async function handleNew() {
    stopListening();
    setActiveId(null);
    setMessages([]);
    setInput("");
    setSearch("");
    setActionError(null);
    setRetryText({});
    textareaRef.current?.focus();
  }

  async function handleSend(text?: string) {
    const content = (text ?? input).trim();
    if (!content || sending) return;
    stopListening();
    stopSpeaking();

    const optimistic: ChatMessage = {
      id: -Date.now(),
      conversation_id: activeId ?? 0,
      role: "user",
      content,
      language: null,
      intent: null,
      location: null,
      sources: null,
      response_type: null,
      is_demo: false,
      sections: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setInput("");
    setSending(true);
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    try {
      const res = await sendMessage(content, activeId ?? undefined);
      setActiveId(res.conversation_id);
      setLatencies((prev) => ({
        ...prev,
        [res.assistant_message.id]: res.latency_ms,
      }));
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimistic.id),
        res.user_message,
        res.assistant_message,
      ]);
      const others = conversations.filter((c) => c.id !== res.conversation_id);
      const updated: Conversation = {
        id: res.conversation_id,
        title: content.slice(0, 60),
        language: res.language ?? "en",
        created_at: new Date().toISOString(),
      };
      setConversations([updated, ...others]);
      // Mic-initiated questions get a spoken answer.
      if (lastVoiceRef.current) {
        lastVoiceRef.current = false;
        speak(res.assistant_message.content, res.assistant_message.language);
      }
    } catch (err) {
      console.error("sendMessage failed:", err);
      const errorId = -Date.now() - 1;
      setRetryText((prev) => ({ ...prev, [errorId]: content }));
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimistic.id),
        {
          ...optimistic,
          id: errorId,
          role: "assistant",
          content:
            getApiError(err) ||
            t("Sorry, I could not reach the assistant service. Please try again."),
          response_type: "error",
          is_demo: false,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function handleRate(m: ChatMessage, rating: 1 | -1) {
    if (m.rating === rating || m.id < 0) return;
    setMessages((prev) =>
      prev.map((msg) => (msg.id === m.id ? { ...msg, rating } : msg))
    );
    try {
      const updated = await rateMessage(m.id, rating);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === m.id ? { ...msg, rating: updated.rating } : msg
        )
      );
    } catch {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === m.id ? { ...msg, rating: m.rating ?? null } : msg
        )
      );
    }
  }

  async function handleRegenerate() {
    if (!activeId || regenerating || sending) return;
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    if (!lastAssistant) return;
    setRegenerating(true);
    setActionError(null);
    try {
      const res = await regenerateAnswer(activeId);
      setLatencies((prev) => ({
        ...prev,
        [res.assistant_message.id]: res.latency_ms,
      }));
      setMessages((prev) => [
        ...prev.slice(0, prev.findIndex((m) => m.id === lastAssistant.id)),
        res.assistant_message,
      ]);
    } catch (err) {
      setActionError(getApiError(err));
    } finally {
      setRegenerating(false);
    }
  }

  async function handleExport() {
    if (!activeId || exporting) return;
    setExporting(true);
    setActionError(null);
    try {
      const blob = await exportConversation(activeId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ingres-conversation-${activeId}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(getApiError(err));
    } finally {
      setExporting(false);
    }
  }

  function handleRetry(errorMsgId: number) {
    const question = retryText[errorMsgId];
    if (!question || sending) return;
    setRetryText((prev) => {
      const next = { ...prev };
      delete next[errorMsgId];
      return next;
    });
    setMessages((prev) => prev.filter((m) => m.id !== errorMsgId));
    void handleSend(question);
  }

  async function handleDelete(id: number) {
    try {
      await deleteConversation(id);
    } catch {
      /* ignore */
    }
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) {
      setActiveId(null);
      setMessages([]);
    }
  }

  function toggleSelected(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const allVisibleSelected =
    filteredConversations.length > 0 &&
    filteredConversations.every((c) => selectedIds.has(c.id));

  function toggleSelectAll() {
    setSelectedIds(() =>
      allVisibleSelected ? new Set() : new Set(filteredConversations.map((c) => c.id))
    );
  }

  function exitSelectionMode() {
    setSelectionMode(false);
    setSelectedIds(new Set());
  }

  async function handleBulkDelete() {
    if (!selectedIds.size || bulkDeleting) return;
    setBulkDeleting(true);
    let deleted: number[] = [];
    try {
      deleted = await bulkDeleteConversations([...selectedIds]);
    } catch {
      /* keep selection so the user can retry */
    }
    setConversations((prev) => prev.filter((c) => !deleted.includes(c.id)));
    if (activeId && deleted.includes(activeId)) {
      setActiveId(null);
      setMessages([]);
    }
    setBulkDeleting(false);
    exitSelectionMode();
  }

  async function handleEscalate(m: ChatMessage) {
    if (escalated[m.id]) return;
    try {
      await createExpertRequest({
        question: m.content,
        conversation_id: activeId,
        language: m.language,
        location: m.location,
        intent: m.intent,
      });
      setEscalated((prev) => ({ ...prev, [m.id]: true }));
    } catch {
      /* ignore */
    }
  }

  function onComposerKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function onComposerInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }

  const activeTitle = useMemo(() => {
    if (!activeId) return null;
    return conversations.find((c) => c.id === activeId)?.title ?? null;
  }, [activeId, conversations]);

  return (
    <div className="flex h-[calc(100vh-7rem)] overflow-hidden rounded-xl border bg-background">
      {/* Conversation rail */}
      <div className="hidden w-72 shrink-0 flex-col border-r md:flex">
        <div className="space-y-2 border-b p-3">
          <Button className="w-full justify-start gap-2" onClick={handleNew}>
            <Plus className="h-4 w-4" />
            {t("New conversation")}
          </Button>
          {!selectionMode && (
            <Button
              variant="outline"
              className="w-full justify-start gap-2"
              onClick={() => setSelectionMode(true)}
              disabled={!conversations.length}
            >
              <ListChecks className="h-4 w-4" />
              {t("Select conversations")}
            </Button>
          )}
          {selectionMode && (
            <div className="flex items-center gap-1.5">
              <label className="flex flex-1 cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-accent/50">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleSelectAll}
                  className="h-3.5 w-3.5 accent-[hsl(var(--primary))]"
                />
                {t("Select all")}
              </label>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleBulkDelete}
                disabled={!selectedIds.size || bulkDeleting}
                title={t("Delete selected conversations")}
              >
                {bulkDeleting ? (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="mr-1 h-3.5 w-3.5" />
                )}
                {t("Delete")} ({selectedIds.size})
              </Button>
              <Button variant="ghost" size="icon" onClick={exitSelectionMode} title={t("Cancel")}>
                <Square className="h-3 w-3" />
              </Button>
            </div>
          )}
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("Search conversations")}
              className="pl-8"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {loadingList && (
            <div className="flex justify-center py-8 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          )}
          {!loadingList && filteredConversations.length === 0 && (
            <p className="px-3 py-8 text-center text-xs text-muted-foreground">
              {t("No conversations yet.")}
            </p>
          )}
          {filteredConversations.map((c) => (
            <div
              key={c.id}
              className={cn(
                "group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 transition-colors",
                c.id === activeId
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-accent/50",
                selectionMode && selectedIds.has(c.id) && "bg-primary/10"
              )}
              onClick={() =>
                selectionMode ? toggleSelected(c.id) : setActiveId(c.id)
              }
            >
              {selectionMode ? (
                <input
                  type="checkbox"
                  checked={selectedIds.has(c.id)}
                  onChange={() => toggleSelected(c.id)}
                  onClick={(e) => e.stopPropagation()}
                  className="h-3.5 w-3.5 shrink-0 accent-[hsl(var(--primary))]"
                />
              ) : (
                <MessageSquareText className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">
                  {c.title || t("new_chat")}
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {relativeTime(c.created_at)}
                </div>
              </div>
              <button
                className={cn(
                  "transition-opacity hover:text-destructive",
                  selectionMode
                    ? "hidden"
                    : "opacity-0 group-hover:opacity-100"
                )}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(c.id);
                }}
                title={t("Delete conversation")}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
        <div className="border-t p-3 text-center text-[11px] text-muted-foreground">
          <Waves className="mx-auto mb-1 h-4 w-4 text-primary" />
          IN-GRES AI · {t("Synthetic demo data")}
        </div>
      </div>

      {/* Chat column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Chat header */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b px-4 py-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-primary to-sky-500 text-primary-foreground">
            <Bot className="h-5 w-5" />
            <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-background bg-emerald-500" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">IN-GRES Assistant</span>
              <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
                {LANGUAGE_LABELS[lang] ?? lang}
              </Badge>
            </div>
            <div className="truncate text-xs text-muted-foreground">
              {activeTitle ?? t("Ask anything about India's groundwater")}
            </div>
          </div>
          {activeId && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExport}
                disabled={exporting}
                title={t("Export as Markdown")}
              >
                {exporting ? (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="mr-1 h-3.5 w-3.5" />
                )}
                {t("Export")}
              </Button>
              <Button variant="outline" size="sm" onClick={handleNew}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                {t("new_chat")}
              </Button>
            </>
          )}
        </div>

        {/* Body */}
        {messages.length === 0 && !loadingMsgs ? (
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-2xl px-6 pb-8 pt-10">
              <div className="text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-sky-500 shadow-lg shadow-primary/20">
                  <Bot className="h-8 w-8 text-primary-foreground" />
                </div>
                <p className="mt-6 text-sm font-medium text-primary">{greeting}</p>
                <h2 className="mt-2 text-3xl font-bold tracking-tight">
                  {t("How can I help you with groundwater today?")}
                </h2>
                <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">
                  {t(
                    "Ask about recharge, extraction, stage of extraction or assessment categories for any state, district or village in India — in English, Telugu or Hindi. Use the microphone to speak your question."
                  )}
                </p>
              </div>

              <div className="mt-8 grid gap-2 sm:grid-cols-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex.text}
                    onClick={() => handleSend(ex.text)}
                    disabled={sending}
                    className="group flex items-start gap-3 rounded-xl border bg-card p-4 text-left transition-all hover:border-primary/50 hover:bg-accent/40 hover:shadow-sm"
                  >
                    <ex.icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span className="text-sm text-muted-foreground group-hover:text-foreground">
                      {ex.text}
                    </span>
                  </button>
                ))}
              </div>

              <div className="mt-6">
                <div className="mb-2 text-center text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                  {t("Or try")}
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  {CAPABILITIES.map((cap) => (
                    <button
                      key={cap.label}
                      onClick={() => handleSend(cap.prompt)}
                      disabled={sending}
                      className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
                    >
                      <Sparkles className="h-3 w-3" />
                      {t(cap.label)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-8 rounded-2xl border bg-card p-4 text-left">
                <div className="mb-3 flex items-center gap-2">
                  <ArrowRightLeft className="h-4 w-4 text-primary" />
                  <span className="text-sm font-semibold">{t("Compare two regions")}</span>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <div className="min-w-[150px] flex-1">
                    <label className="mb-1 block text-[11px] text-muted-foreground">
                      {t("Region A")}
                    </label>
                    <Select
                      value={compareA}
                      onChange={(e) => setCompareA(e.target.value)}
                      aria-label={t("Region A")}
                    >
                      <option value="">{t("Choose a state")}</option>
                      {compareStates.map((s) => (
                        <option key={s.id} value={s.name}>
                          {s.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="min-w-[150px] flex-1">
                    <label className="mb-1 block text-[11px] text-muted-foreground">
                      {t("Region B")}
                    </label>
                    <Select
                      value={compareB}
                      onChange={(e) => setCompareB(e.target.value)}
                      aria-label={t("Region B")}
                    >
                      <option value="">{t("Choose a state")}</option>
                      {compareStates.map((s) => (
                        <option key={s.id} value={s.name}>
                          {s.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <Button
                    size="sm"
                    onClick={runCompare}
                    disabled={
                      !compareA || !compareB || compareA === compareB || compareLoading
                    }
                  >
                    {compareLoading ? (
                      <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <ArrowRightLeft className="mr-1 h-3.5 w-3.5" />
                    )}
                    {t("Compare")}
                  </Button>
                </div>
                {compareError && (
                  <p className="mt-2 text-xs text-destructive">{compareError}</p>
                )}
                {compareResult && (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b text-muted-foreground">
                          <th className="py-1.5 font-medium">{t("Metric")}</th>
                          <th className="py-1.5 text-right font-medium">
                            {compareResult.a.state}
                          </th>
                          <th className="py-1.5 text-right font-medium">
                            {compareResult.b.state}
                          </th>
                          <th className="py-1.5 text-right font-medium">
                            {t("Difference")}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          {
                            label: t("Assessment units"),
                            a: formatValue(compareResult.a.assessment_units),
                            b: formatValue(compareResult.b.assessment_units),
                            delta: null,
                          },
                          {
                            label: t("Total recharge (hm³)"),
                            a: formatValue(compareResult.a.total_recharge),
                            b: formatValue(compareResult.b.total_recharge),
                            delta: deltaOf(
                              compareResult.a.total_recharge,
                              compareResult.b.total_recharge
                            ),
                          },
                          {
                            label: t("Total extraction (hm³)"),
                            a: formatValue(compareResult.a.total_extraction),
                            b: formatValue(compareResult.b.total_extraction),
                            delta: deltaOf(
                              compareResult.a.total_extraction,
                              compareResult.b.total_extraction
                            ),
                          },
                          {
                            label: t("Avg stage of extraction"),
                            a: pctOf(compareResult.a.average_stage_of_extraction),
                            b: pctOf(compareResult.b.average_stage_of_extraction),
                            delta: deltaOf(
                              compareResult.a.average_stage_of_extraction,
                              compareResult.b.average_stage_of_extraction
                            ),
                          },
                        ].map((row) => (
                          <tr key={row.label} className="border-b last:border-0">
                            <td className="py-1.5 text-muted-foreground">{row.label}</td>
                            <td className="py-1.5 text-right font-medium">{row.a}</td>
                            <td className="py-1.5 text-right font-medium">{row.b}</td>
                            <td className="py-1.5 text-right text-primary">
                              {row.delta ?? "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="mt-3 space-y-1">
                      {["Safe", "Semi-critical", "Critical", "Over-exploited"].map(
                        (cat) => {
                          const countA =
                            compareResult.a.category_counts.find((c) => c.category === cat)
                              ?.count ?? 0;
                          const countB =
                            compareResult.b.category_counts.find((c) => c.category === cat)
                              ?.count ?? 0;
                          if (!countA && !countB) return null;
                          return (
                            <div
                              key={cat}
                              className="flex items-center gap-2 text-[11px]"
                            >
                              <span
                                className="h-2.5 w-2.5 rounded-full"
                                style={{ backgroundColor: CATEGORY_COLORS[cat] ?? "#94a3b8" }}
                              />
                              <span className="w-24 text-muted-foreground">
                                {t(cat)}
                              </span>
                              <span className="text-right">{countA}</span>
                              <span className="text-right">{countB}</span>
                            </div>
                          );
                        }
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-10 flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                {t(
                  "Answers come from a labelled synthetic demo dataset — never official IN-GRES/CGWB data."
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-4 py-5">
            {loadingMsgs && (
              <div className="flex justify-center py-8 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            )}
            <div className="mx-auto max-w-3xl space-y-5">
              {messages.map((m, idx) => {
                const isError = m.role === "assistant" && m.response_type === "error";
                const isLastAssistant =
                  m.role === "assistant" &&
                  !isError &&
                  !messages.slice(idx + 1).some((x) => x.role === "assistant");
                return m.role === "user" ? (
                  <div key={m.id} className="flex justify-end">
                    <div className="min-w-0 max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground shadow-sm whitespace-pre-line [overflow-wrap:anywhere]">
                      {m.content}
                      <div className="mt-1 text-right text-[10px] text-primary-foreground/70">
                        {formatTime(m.created_at)}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div key={m.id} className="flex gap-3">
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-sky-500 text-primary-foreground">
                      <Bot className="h-4 w-4" />
                    </div>
                    <div
                      className={cn(
                        "min-w-0 max-w-[min(85%,calc(100%-2.75rem))] rounded-2xl rounded-tl-sm border bg-card px-4 py-2.5 shadow-sm [overflow-wrap:anywhere]",
                        isError && "border-destructive/40 bg-destructive/5"
                      )}
                    >
                      <div className="mb-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="font-semibold text-foreground">IN-GRES</span>
                        {m.language && (
                          <span>{LANGUAGE_LABELS[m.language] ?? m.language}</span>
                        )}
                        {m.response_type && <span>· {m.response_type}</span>}
                      </div>
                      <div className="space-y-1 text-sm whitespace-pre-line">
                        {renderContent(m.content)}
                      </div>
                      {m.sections && <ChatSections sections={m.sections} />}
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        {m.location && (
                          <Badge variant="outline" className="text-[10px]">
                            <MapPin className="mr-1 h-2.5 w-2.5" />
                            {m.location}
                          </Badge>
                        )}
                        {m.intent && (
                          <Badge variant="outline" className="text-[10px]">
                            {t(INTENT_LABELS[m.intent] ?? m.intent)}
                          </Badge>
                        )}
                        {m.is_demo && (
                          <Badge variant="warning" className="text-[10px]">
                            {t("demo_data")}
                          </Badge>
                        )}
                        {latencies[m.id] != null && (
                          <Badge variant="outline" className="text-[10px]">
                            {latencies[m.id]} ms
                          </Badge>
                        )}
                      </div>
                      {m.sources?.some((s) => /^https?:\/\//.test(s)) && (
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                            {t("Web sources")}:
                          </span>
                          {m.sources
                            .filter((s) => /^https?:\/\//.test(s))
                            .slice(0, 4)
                            .map((s) => {
                              let host = s;
                              try {
                                host = new URL(s).hostname.replace(/^www\./, "");
                              } catch {
                                /* keep raw */
                              }
                              return (
                                <a
                                  key={s}
                                  href={s}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="max-w-[180px] truncate rounded-full border bg-background px-2 py-0.5 text-[10px] text-primary hover:underline"
                                >
                                  {host}
                                </a>
                              );
                            })}
                        </div>
                      )}
                      {isError ? (
                        <div className="mt-2 border-t pt-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRetry(m.id)}
                            disabled={sending}
                            className="gap-1.5"
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                            {t("Retry")}
                          </Button>
                        </div>
                      ) : (
                        <div className="mt-2 flex items-center gap-1 border-t pt-2">
                          <button
                            onClick={() => copyMessage(m)}
                            title={t("Copy")}
                            className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                          >
                            {copiedId === m.id ? (
                              <Check className="h-3.5 w-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                          </button>
                          <button
                            onClick={() => speak(m.content, m.language)}
                            title={t("Read aloud")}
                            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                          >
                            <Volume2 className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleRate(m, 1)}
                            disabled={sending || m.rating === 1}
                            title={t("Helpful answer")}
                            className={cn(
                              "rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50",
                              m.rating === 1 && "text-emerald-600"
                            )}
                          >
                            <ThumbsUp className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleRate(m, -1)}
                            disabled={sending || m.rating === -1}
                            title={t("Not helpful")}
                            className={cn(
                              "rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50",
                              m.rating === -1 && "text-red-500"
                            )}
                          >
                            <ThumbsDown className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleEscalate(m)}
                            disabled={escalated[m.id]}
                            title={
                              escalated[m.id]
                                ? t("Escalated to expert desk")
                                : t("Escalate to an expert")
                            }
                            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
                          >
                            <UserPlus className="h-3.5 w-3.5" />
                          </button>
                          {isLastAssistant && (
                            <button
                              onClick={handleRegenerate}
                              disabled={regenerating || sending || m.id < 0}
                              title={t("Regenerate answer")}
                              className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
                            >
                              <RefreshCw
                                className={cn(
                                  "h-3.5 w-3.5",
                                  regenerating && "animate-spin"
                                )}
                              />
                            </button>
                          )}
                          <span className="ml-auto text-[10px] text-muted-foreground">
                            {formatTime(m.created_at)}
                          </span>
                        </div>
                      )}
                      {isLastAssistant &&
                        m.followups &&
                        m.followups.length > 0 &&
                        !sending &&
                        !regenerating && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {m.followups.map((q) => (
                              <button
                                key={q}
                                onClick={() => void handleSend(q)}
                                className="inline-flex items-center gap-1 rounded-full border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
                              >
                                <Sparkles className="h-3 w-3 shrink-0" />
                                {q}
                              </button>
                            ))}
                          </div>
                        )}
                    </div>
                  </div>
                );
              })}
              {(sending || regenerating) && (
                <div className="flex gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-primary to-sky-500 text-primary-foreground">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border bg-card px-4 py-3">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60"
                        style={{ animationDelay: `${i * 120}ms` }}
                      />
                    ))}
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>
        )}

        {/* Composer */}
        <div className="border-t p-3">
          <div className="mx-auto max-w-3xl">
            {actionError && (
              <p className="mb-1.5 text-xs text-destructive">{actionError}</p>
            )}
            <div className="flex items-end gap-2 rounded-2xl border bg-background p-2 shadow-sm focus-within:border-primary/60 focus-within:ring-1 focus-within:ring-ring">
              {speechSupported && (
                <Button
                  type="button"
                  variant={listening ? "destructive" : "ghost"}
                  size="icon"
                  onClick={toggleListening}
                  title={listening ? t("Stop listening") : t("Speak your question")}
                  className="shrink-0"
                >
                  {listening ? (
                    <Square className="h-4 w-4" />
                  ) : (
                    <Mic className="h-4 w-4" />
                  )}
                </Button>
              )}
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onInput={onComposerInput}
                onKeyDown={onComposerKeyDown}
                placeholder={t("ask_about_gw")}
                disabled={sending}
                rows={1}
                className="min-h-0 min-w-0 flex-1 resize-none border-0 bg-transparent px-1 py-2 shadow-none focus-visible:ring-0"
              />
              <Button
                type="submit"
                size="icon"
                disabled={sending || !input.trim()}
                onClick={() => handleSend()}
                title={t("Send")}
                className="shrink-0 rounded-xl"
              >
                {sending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
            {speechError && (
              <p className="mt-1 text-xs text-destructive">{speechError}</p>
            )}
            {listening && (
              <p className="mt-1 text-xs text-primary">
                {t("Recording… speak your question, it sends automatically")}
              </p>
            )}
            <div className="mt-1.5 flex flex-wrap items-center justify-center gap-2 text-[11px] text-muted-foreground">
              <span>{t("Mic language")}:</span>
              {(
                [
                  ["auto", "Auto-detect"],
                  ["en", "English"],
                  ["te", "తెలుగు"],
                  ["hi", "हिन्दी"],
                ] as [MicLang, string][]
              ).map(([code, label]) => (
                <button
                  key={code}
                  onClick={() => changeMicLang(code)}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 font-medium transition-colors",
                    micLang === code
                      ? "border-primary bg-primary/10 text-primary"
                      : "hover:border-primary/40 hover:text-primary"
                  )}
                  title={t("Speak in this language")}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="mt-1.5 flex items-center justify-center gap-2 text-[11px] text-muted-foreground">
              <span>{t("Voice")}:</span>
              {(["female", "male"] as const).map((pref) => (
                <button
                  key={pref}
                  onClick={() => changeVoicePref(pref)}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 font-medium transition-colors",
                    voicePref === pref
                      ? "border-primary bg-primary/10 text-primary"
                      : "hover:border-primary/40 hover:text-primary"
                  )}
                  title={t(pref === "female" ? "Female voice" : "Male voice")}
                >
                  {pref === "female" ? "♀" : "♂"} {t(pref)}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-center text-[11px] text-muted-foreground">
              {t("Enter to send · Shift+Enter for a new line")}
              <span className="mx-1.5">·</span>
              {user?.role}
              <span className="mx-1.5">·</span>
              {t("Synthetic demo data")}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
import {
  BookOpen,
  FileUp,
  Loader2,
  Search,
  SearchX,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useNotifications } from "@/contexts/NotificationContext";
import {
  deleteKnowledgeDocument,
  fetchDocuments,
  searchKnowledge,
  uploadKnowledgeDocument,
  type KnowledgeDocumentInfo,
  type RagSearchResult,
} from "@/services/rag";

function scoreVariant(score: number): "success" | "warning" | "secondary" {
  if (score >= 0.5) return "success";
  if (score >= 0.25) return "warning";
  return "secondary";
}

export default function Knowledge() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const { toast } = useNotifications();
  const isAdmin = user?.role === "admin";

  const [documents, setDocuments] = useState<KnowledgeDocumentInfo[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RagSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(() => {
    fetchDocuments()
      .then(setDocuments)
      .catch(() => setDocuments([]));
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (q.length < 2) return;
    setSearching(true);
    setSearchError(null);
    setSearched(true);
    try {
      setResults(await searchKnowledge(q));
    } catch {
      setSearchError(t("Search failed. Check that the knowledge base is available."));
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function handleUpload(file: File) {
    if (!file) return;
    setUploading(true);
    try {
      await uploadKnowledgeDocument(file);
      toast(t("Document added to the knowledge base."), "success");
      loadDocuments();
    } catch (err) {
      const detail =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: unknown }).detail)
          : null;
      toast(
        detail || t("Failed to upload the document."),
        "error"
      );
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await deleteKnowledgeDocument(id);
      toast(t("Document removed."), "success");
      loadDocuments();
    } catch {
      toast(t("Failed to remove the document."), "error");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <BookOpen className="h-6 w-6 text-primary" />
            {t("Knowledge base")}
          </h2>
          <p className="mt-1 text-muted-foreground">
            {t(
              "Browse the groundwater reference documents used by the AI assistant. Search returns verbatim excerpts with their sources."
            )}
          </p>
        </div>
        <Badge variant="secondary">{t("RAG")}</Badge>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("Search the knowledge base")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("Ask about recharge, stage of extraction, conservation…")}
                className="pl-9"
              />
            </div>
            <Button type="submit" disabled={searching || query.trim().length < 2}>
              {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              {t("Search")}
            </Button>
          </form>
        </CardContent>
      </Card>

      {searchError && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {searchError}
        </div>
      )}

      {searched && !searching && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              {results.length
                ? t("{count} result(s) for “{query}”", { count: results.length, query })
                : t("No matches")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {results.length === 0 && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <SearchX className="h-4 w-4" />
                {t("Nothing found. Try different wording.")}
              </div>
            )}
            {results.map((r, i) => (
              <div key={i} className="rounded-md border p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant={scoreVariant(r.score)}>
                    {t("Relevance")}: {Math.round(r.score * 100)}%
                  </Badge>
                  {r.document_title && (
                    <span className="text-sm font-medium">{r.document_title}</span>
                  )}
                  {r.section && (
                    <span className="text-xs text-muted-foreground">→ {r.section}</span>
                  )}
                  {r.source && (
                    <span className="ml-auto text-xs text-muted-foreground">{r.source}</span>
                  )}
                </div>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                  {r.content}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle className="text-sm">{t("Documents")}</CardTitle>
            <CardDescription>
              {t("{count} document(s), {chunks} chunk(s) indexed", {
                count: documents.length,
                chunks: documents.reduce((sum, d) => sum + d.chunk_count, 0),
              })}
            </CardDescription>
          </div>
          {isAdmin && (
            <div className="flex items-center gap-2">
              <input
                ref={fileRef}
                type="file"
                accept=".md,.txt"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleUpload(file);
                }}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={uploading}
                onClick={() => fileRef.current?.click()}
              >
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
                {t("Add document")}
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("No documents yet.")}</p>
          ) : (
            <ul className="divide-y">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-center gap-3 py-3">
                  <BookOpen className="h-4 w-4 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{doc.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {doc.source ?? t("knowledge base")} · {doc.chunk_count}{" "}
                      {t("chunks")}
                    </p>
                  </div>
                  {isAdmin && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive"
                      disabled={deletingId === doc.id}
                      onClick={() => void handleDelete(doc.id)}
                      title={t("Remove document")}
                    >
                      {deletingId === doc.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {!isAdmin && (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
              <ShieldAlert className="h-3.5 w-3.5" />
              {t("Only admins can add or remove documents.")}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
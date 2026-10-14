import { useEffect, useRef, useState, type ClipboardEvent } from "react";
import {
  Paperclip,
  UploadCloud,
  X,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
} from "lucide-react";
import { api, bytes, type Attachment } from "../shared/api";

type Props = {
  scope: string;
  ticketId?: string;
  visibility?: string;
  onDraft: (id: string) => void;
  onBusy: (busy: boolean) => void;
  pasteFiles?: File[];
};
export function clipboardImages(event: ClipboardEvent): File[] {
  return Array.from(event.clipboardData.items)
    .filter((x) => x.kind === "file" && x.type.startsWith("image/"))
    .map((x) => x.getAsFile())
    .filter((x): x is File => !!x);
}
export function AttachmentComposer({
  scope,
  ticketId,
  visibility = "public",
  onDraft,
  onBusy,
  pasteFiles,
}: Props) {
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const previewUrls = useRef<string[]>([]);
  useEffect(
    () => () => {
      previewUrls.current.forEach((url) => URL.revokeObjectURL(url));
    },
    [],
  );
  const input = useRef<HTMLInputElement>(null);
  const draftPromise = useRef<Promise<string> | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const getDraft = async () => {
    if (!draftPromise.current)
      draftPromise.current = api<{ id: string }>(scope + "/drafts", {
        method: "POST",
        body: JSON.stringify({ ticketId, visibility }),
      })
        .then((x) => {
          if (alive.current) {
            setDraft(x.id);
            onDraft(x.id);
          }
          return x.id;
        })
        .catch((e) => {
          draftPromise.current = null;
          throw e;
        });
    return draftPromise.current;
  };
  const upload = async (list: File[]) => {
    if (!list.length || uploading) return;
    setUploading(true);
    onBusy(true);
    setError("");
    try {
      const id = await getDraft();
      for (const file of list) {
        const body = new FormData();
        body.append("file", file);
        const item = await api<Attachment>(
          scope + "/drafts/" + id + "/uploads",
          { method: "POST", body },
        );
        if (alive.current) {
          setFiles((old) => [...old, item]);
          if (
            file.type.startsWith("image/") &&
            typeof URL.createObjectURL === "function"
          ) {
            const url = URL.createObjectURL(file);
            previewUrls.current.push(url);
            setPreviews((old) => ({ ...old, [item.id]: url }));
          }
        }
      }
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setUploading(false);
    }
  };
  useEffect(() => {
    if (pasteFiles?.length) void upload(pasteFiles);
  }, [pasteFiles]);
  useEffect(() => {
    if (!draft) return;
    let disposed = false;
    const refresh = () =>
      api<Attachment[]>(scope + "/drafts/" + draft + "/uploads")
        .then((result) => {
          if (!disposed) setFiles(result);
        })
        .catch(() => {});
    const timer = setInterval(refresh, 2000);
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [draft, scope]);
  const blocked = uploading || files.some((f) => f.state !== "clean");
  useEffect(() => {
    onBusy(blocked);
  }, [blocked, onBusy]);
  return (
    <div className="attachment-composer">
      <div
        className="dropzone"
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDrop={(e) => {
          e.preventDefault();
          void upload(Array.from(e.dataTransfer.files));
        }}
      >
        <UploadCloud size={23} />
        <div>
          <strong>Dosyaları buraya bırakın</strong>
          <span>
            veya dosya seçin · Resimleri yanıt alanına yapıştırabilirsiniz
          </span>
        </div>
        <button
          type="button"
          className="button ghost small"
          disabled={uploading}
          onClick={() => input.current?.click()}
        >
          <Paperclip size={15} />
          Dosya seç
        </button>
        <input
          ref={input}
          type="file"
          multiple
          accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.csv"
          hidden
          onChange={(e) => {
            void upload(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />
      </div>
      {uploading && (
        <p className="muted inline">
          <LoaderCircle size={16} className="spin" />
          Dosyalar yükleniyor…
        </p>
      )}
      {files.map((file) => (
        <div className="attachment" key={file.id}>
          {previews[file.id] && (
            <img
              className="attachment-preview"
              src={previews[file.id]}
              alt={file.filename + " yerel önizleme"}
            />
          )}
          {file.mimeType.startsWith("image/") ? (
            <ImageIcon size={18} />
          ) : (
            <FileText size={18} />
          )}
          <div>
            <strong>{file.filename}</strong>
            <small>
              {bytes(file.size)} ·{" "}
              {file.state === "clean"
                ? "Güvenli"
                : file.state === "rejected"
                  ? "Reddedildi"
                  : "Taranıyor"}
              {file.reason && " · " + file.reason}
            </small>
          </div>
          <button
            type="button"
            className="icon-button"
            aria-label={file.filename + " dosyasını kaldır"}
            onClick={() =>
              api(scope + "/attachments/" + file.id, { method: "DELETE" })
                .then(() =>
                  setFiles((old) => old.filter((f) => f.id !== file.id)),
                )
                .catch((e) => setError(e.message))
            }
          >
            <X size={16} />
          </button>
        </div>
      ))}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <small className="muted">
        PNG, JPG, WebP, PDF, TXT, CSV · Dosya başına en fazla 20 MB. Hassas
        bilgileri göndermeden önce maskeleyin.
      </small>
    </div>
  );
}
export function AttachmentList({
  scope,
  files,
}: {
  scope: string;
  files: Attachment[];
}) {
  return (
    <div className="attachments">
      {files.map((file) => (
        <a
          className="attachment"
          href={"/api/v1/" + scope + "/attachments/" + file.id}
          key={file.id}
          download
        >
          {file.mimeType.startsWith("image/") ? (
            <ImageIcon size={19} />
          ) : (
            <FileText size={19} />
          )}
          <div>
            <strong>{file.filename}</strong>
            <small>{bytes(file.size)}</small>
          </div>
        </a>
      ))}
    </div>
  );
}

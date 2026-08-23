import { downloadDocument } from "@/lib/exportDocument";

export function DownloadActions({
  content,
  basename,
  disabled,
}: {
  content: string;
  basename: string;
  disabled?: boolean;
}) {
  const ready = Boolean(content.trim()) && !disabled;
  return (
    <div className="download-actions">
      <button type="button" disabled={!ready} onClick={() => downloadDocument(basename, content, "docx")}>
        Word
      </button>
      <button type="button" disabled={!ready} onClick={() => downloadDocument(basename, content, "pdf")}>
        PDF
      </button>
    </div>
  );
}

import { downloadDocument, ExportBlock } from "@/lib/exportDocument";

export function DownloadActions({
  content,
  blocks,
  basename,
  disabled,
}: {
  content?: string;
  blocks?: ExportBlock[];
  basename: string;
  disabled?: boolean;
}) {
  const payload = blocks?.length ? blocks : content || "";
  const ready = (blocks?.some((row) => row.text.trim()) || Boolean(content?.trim())) && !disabled;
  return (
    <div className="download-actions">
      <button type="button" disabled={!ready} onClick={() => downloadDocument(basename, payload, "docx")}>
        Word
      </button>
      <button type="button" disabled={!ready} onClick={() => downloadDocument(basename, payload, "pdf")}>
        PDF
      </button>
    </div>
  );
}

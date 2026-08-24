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
  const hint = ready ? null : "Önce taslak üretin.";
  return (
    <div className="download-actions">
      <button
        type="button"
        disabled={!ready}
        title={hint ?? "Word indir"}
        onClick={() => downloadDocument(basename, payload, "docx")}
      >
        Word
      </button>
      <button
        type="button"
        disabled={!ready}
        title={hint ?? "PDF indir"}
        onClick={() => downloadDocument(basename, payload, "pdf")}
      >
        PDF
      </button>
      {hint ? <span className="download-hint">{hint}</span> : null}
    </div>
  );
}

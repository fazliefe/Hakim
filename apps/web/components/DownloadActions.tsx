import { downloadDocument, ExportBlock, UDF_EXPORT_TRIAL } from "@/lib/exportDocument";

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
      {UDF_EXPORT_TRIAL ? (
        <button
          type="button"
          disabled={!ready}
          title="UYAP Editör denemesi. Açılmazsa exportDocument.ts içinde UDF_EXPORT_TRIAL=false yapın."
          onClick={() => downloadDocument(basename, payload, "udf")}
        >
          UDF (deneme)
        </button>
      ) : null}
    </div>
  );
}

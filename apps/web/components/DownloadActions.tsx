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
      {UDF_EXPORT_TRIAL ? (
        <button
          type="button"
          disabled={!ready}
          title="UYAP Editör için UDF indir. Açılmazsa exportDocument.ts içinde UDF_EXPORT_TRIAL=false yapın."
          onClick={() => downloadDocument(basename, payload, "udf")}
        >
          UDF
        </button>
      ) : null}
      {hint ? <span className="download-hint">{hint}</span> : null}
    </div>
  );
}

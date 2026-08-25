import { PetitionView } from "@/lib/api";

export type ExportBlock = {
  text: string;
  align?: "left" | "center" | "right";
  bold?: boolean;
};

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) {
    crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function u16(value: number): Uint8Array {
  return new Uint8Array([value & 0xff, (value >>> 8) & 0xff]);
}

function u32(value: number): Uint8Array {
  return new Uint8Array([value & 0xff, (value >>> 8) & 0xff, (value >>> 16) & 0xff, (value >>> 24) & 0xff]);
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function zipStore(
  files: Array<{ name: string; data: Uint8Array }>,
  mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
): Blob {
  const locals: Uint8Array[] = [];
  const centrals: Uint8Array[] = [];
  let offset = 0;
  const encoder = new TextEncoder();
  for (const file of files) {
    const name = encoder.encode(file.name);
    const crc = crc32(file.data);
    const local = concat([
      new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
      u32(crc),
      u32(file.data.length),
      u32(file.data.length),
      u16(name.length),
      u16(0),
      name,
      file.data,
    ]);
    locals.push(local);
    centrals.push(
      concat([
        new Uint8Array([0x50, 0x4b, 0x01, 0x02, 0x14, 0x00, 0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
        u32(crc),
        u32(file.data.length),
        u32(file.data.length),
        u16(name.length),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(0),
        u32(offset),
        name,
      ]),
    );
    offset += local.length;
  }
  const central = concat(centrals);
  const end = concat([
    new Uint8Array([0x50, 0x4b, 0x05, 0x06, 0x00, 0x00, 0x00, 0x00]),
    u16(files.length),
    u16(files.length),
    u32(central.length),
    u32(offset),
    u16(0),
  ]);
  const packed = concat([...locals, central, end]);
  return new Blob([packed as unknown as BlobPart], { type: mime });
}

/** UYAP UDF denemesi. Editör açmazsa `false` yapın; buton kaybolur. */
export const UDF_EXPORT_TRIAL = true;

const UDF_ZWSP = "\u200B";

function udfAlign(align?: ExportBlock["align"]): string {
  if (align === "center") return "1";
  if (align === "right") return "2";
  return "0";
}

function runeCount(text: string): number {
  return [...text].length;
}

function udfSafeLine(text: string): string {
  return (text || "").replace(/]]>/g, "]] >");
}

function udfBlob(blocks: ExportBlock[]): Blob {
  const encoder = new TextEncoder();
  let cdata = "";
  const paragraphs: Array<{ offset: number; length: number; align: string; bold: boolean }> = [];
  blocks.forEach((block, index) => {
    if (index > 0) cdata += "\n";
    const line = udfSafeLine(block.text) || UDF_ZWSP;
    const offset = runeCount(cdata);
    cdata += line;
    paragraphs.push({
      offset,
      length: runeCount(line),
      align: udfAlign(block.align),
      bold: Boolean(block.bold),
    });
  });
  if (!paragraphs.length) {
    cdata = UDF_ZWSP;
    paragraphs.push({ offset: 0, length: 1, align: "0", bold: false });
  }
  const elements = paragraphs
    .map(
      (row) =>
        `    <paragraph Alignment="${row.align}" resolver="hvl-default">\n` +
        `      <content Alignment="${row.align}" resolver="hvl-default"${row.bold ? ' bold="true"' : ""} size="12" family="Times New Roman" foreground="-16777216" background="-1" startOffset="${row.offset}" length="${row.length}" />\n` +
        "    </paragraph>",
    )
    .join("\n");
  const xml =
    `<?xml version="1.0" encoding="UTF-8" ?>\n` +
    `<template format_id="1.8">\n` +
    `  <content><![CDATA[${cdata}]]></content>\n` +
    "  <properties>\n" +
    `    <pageFormat mediaSizeName="1" leftMargin="56.7" rightMargin="56.7" topMargin="56.7" bottomMargin="56.7" paperOrientation="1" headerFOffset="20.0" footerFOffset="20.0" />\n` +
    "  </properties>\n" +
    "  <styles>\n" +
    `    <style name="default" description="Geçerli" italic="false" bold="false" size="12" family="Times New Roman" />\n` +
    `    <style name="hvl-default" description="Gövde" size="12" family="Times New Roman" />\n` +
    "  </styles>\n" +
    `  <elements resolver="hvl-default">\n${elements}\n  </elements>\n` +
    "</template>\n";
  return zipStore([{ name: "content.xml", data: encoder.encode(xml) }], "application/octet-stream");
}

function xmlEscape(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function petitionToBlocks(petition: PetitionView): ExportBlock[] {
  const blocks: ExportBlock[] = [{ text: "T.C.", align: "center", bold: true }];
  if (petition.via) blocks.push({ text: petition.via, align: "center" });
  if (petition.hitap) blocks.push({ text: petition.hitap, align: "center" });
  if (petition.sehir) blocks.push({ text: petition.sehir, align: "center" });
  blocks.push({ text: "" });
  for (const row of petition.meta || []) {
    if (!row.label || !row.value) continue;
    blocks.push({ text: `${row.label} : ${row.value}` });
  }
  if ((petition.meta || []).length) blocks.push({ text: "" });
  const sections = (petition.sections || []).filter(
    (section) => section.kind !== "eksik" && section.text?.trim(),
  );
  if (sections.length) {
    sections.forEach((section, idx) => {
      if (section.label) blocks.push({ text: `${section.label} :` });
      blocks.push({ text: idx === 0 ? `     ${section.text}` : section.text });
      blocks.push({ text: "" });
    });
  } else {
    const paragraphs =
      petition.paragraphs?.length
        ? petition.paragraphs
        : (petition.sections || [])
            .filter((section) => section.kind !== "eksik" && section.text?.trim())
            .map((section) => section.text);
    paragraphs.forEach((paragraph, idx) => {
      blocks.push({ text: idx === 0 ? `     ${paragraph}` : paragraph });
      blocks.push({ text: "" });
    });
  }
  if (petition.closing) {
    blocks.push({ text: `     ${petition.closing}` });
    blocks.push({ text: "" });
  }
  const adresLines = (petition.adres || "«[adres]»").split(/[\n;]+/).map((part) => part.trim()).filter(Boolean);
  blocks.push({ text: "Adres:" });
  for (const line of adresLines.length ? adresLines : ["«[adres]»"]) {
    blocks.push({ text: line });
  }
  if (petition.tarih) blocks.push({ text: petition.tarih, align: "right" });
  blocks.push({ text: "(imza)", align: "right" });
  blocks.push({ text: petition.signature?.name || "«[ad soyad]»", align: "right" });
  blocks.push({ text: "" });
  blocks.push({ text: "EKLER:" });
  const ekler = petition.ekler?.length ? petition.ekler : ["—"];
  ekler.forEach((item, idx) => {
    blocks.push({ text: `EK-${idx + 1}  ${item}` });
  });
  return blocks;
}

export function textToBlocks(text: string): ExportBlock[] {
  return text.replace(/\r\n/g, "\n").split("\n").map((line) => ({ text: line }));
}

function asBlocks(content: string | ExportBlock[]): ExportBlock[] {
  return typeof content === "string" ? textToBlocks(content) : content;
}

function docxParagraph(block: ExportBlock): string {
  const align = block.align || "left";
  const after = block.text ? 160 : 80;
  const body = xmlEscape(block.text || " ");
  const bold = block.bold ? "<w:b/>" : "";
  const font = "Arial";
  return `<w:p><w:pPr><w:jc w:val="${align}"/><w:spacing w:after="${after}" w:line="276" w:lineRule="auto"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="${font}" w:hAnsi="${font}" w:cs="${font}"/><w:sz w:val="22"/><w:szCs w:val="22"/>${bold}</w:rPr><w:t xml:space="preserve">${body}</w:t></w:r></w:p>`;
}

function docxBlob(blocks: ExportBlock[]): Blob {
  const encoder = new TextEncoder();
  const document = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${blocks.map(docxParagraph).join("")}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418"/></w:sectPr></w:body></w:document>`;
  const types = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`;
  const rels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;
  return zipStore([
    { name: "[Content_Types].xml", data: encoder.encode(types) },
    { name: "_rels/.rels", data: encoder.encode(rels) },
    { name: "word/document.xml", data: encoder.encode(document) },
  ]);
}

function pdfEscape(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function toWin1254(text: string): string {
  const map: Record<string, string> = {
    Ğ: "\\320",
    Ü: "\\334",
    Ş: "\\336",
    İ: "\\335",
    Ö: "\\326",
    Ç: "\\307",
    ğ: "\\360",
    ü: "\\374",
    ş: "\\376",
    ı: "\\375",
    ö: "\\366",
    ç: "\\347",
  };
  return [...text].map((ch) => {
    if (map[ch]) return map[ch];
    const code = ch.charCodeAt(0);
    if (code < 128) return pdfEscape(ch);
    return map[ch] ?? "?";
  }).join("");
}

function wrapText(text: string, max = 78): string[] {
  if (!text) return [""];
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length > max && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) lines.push(current);
  return lines.length ? lines : [""];
}

function pdfStream(blocks: ExportBlock[]): string[] {
  const pages: string[] = [];
  let commands: string[] = [];
  let y = 790;
  const flush = () => {
    pages.push(`BT /F1 12 Tf\n${commands.join("\n")}\nET`);
    commands = [];
    y = 790;
  };
  for (const block of blocks) {
    const lines = wrapText(block.text);
    for (const line of lines) {
      if (y < 64) flush();
      const width = [...line].reduce((sum, ch) => sum + (ch === " " ? 3.4 : 6.2), 0);
      let x = 56;
      if (block.align === "center") x = Math.max(56, 297.5 - width / 2);
      if (block.align === "right") x = Math.max(56, 539 - width);
      commands.push(`1 0 0 1 ${x.toFixed(1)} ${y} Tm (${toWin1254(line || " ")}) Tj`);
      y -= block.bold && line ? 18 : 16;
    }
    if (!block.text) y -= 6;
  }
  if (commands.length) flush();
  return pages.length ? pages : ["BT /F1 12 Tf\nET"];
}

function pdfBlob(blocks: ExportBlock[]): Blob {
  const streams = pdfStream(blocks);
  const fontId = 3 + streams.length * 2;
  const kids = streams.map((_, i) => `${3 + i * 2} 0 R`).join(" ");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    `<< /Type /Pages /Kids [${kids}] /Count ${streams.length} >>`,
  ];
  for (let i = 0; i < streams.length; i += 1) {
    const pageId = 3 + i * 2;
    const contentId = pageId + 1;
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents ${contentId} 0 R /Resources << /Font << /F1 ${fontId} 0 R >> >> >>`,
    );
    objects.push(`<< /Length ${streams[i].length} >>\nstream\n${streams[i]}\nendstream`);
  }
  objects.push(
    "<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [208 /Gbreve 221 /Idotaccent 222 /Scedilla 240 /gbreve 253 /dotlessi 254 /scedilla] >> >>",
  );
  let body = "%PDF-1.4\n";
  const offsets = [0];
  for (let i = 0; i < objects.length; i += 1) {
    offsets.push(body.length);
    body += `${i + 1} 0 obj\n${objects[i]}\nendobj\n`;
  }
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (let i = 1; i <= objects.length; i += 1) {
    body += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  body += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new Blob([body], { type: "application/pdf" });
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadDocument(
  basename: string,
  content: string | ExportBlock[],
  format: "docx" | "pdf" | "udf",
) {
  const stem = basename.replace(/\.[^.]+$/, "") || "hakim-evrak";
  const blocks = asBlocks(content);
  if (format === "docx") {
    triggerDownload(docxBlob(blocks), `${stem}.docx`);
    return;
  }
  if (format === "udf") {
    triggerDownload(udfBlob(blocks), `${stem}.udf`);
    return;
  }
  triggerDownload(pdfBlob(blocks), `${stem}.pdf`);
}

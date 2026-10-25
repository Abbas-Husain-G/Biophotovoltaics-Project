// Render a report spec (JSON list of blocks, written by build_report.py) to .docx.
// Usage: node render_docx.js spec.json out.docx
// Inline markup in text: **bold**, *italic*, _{subscript}, ^{superscript}
const fs = require("fs");
const path = require("path");
const d = require("docx");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
        ShadingType, ImageRun, PageBreak, Footer, Header, PageNumber, TableOfContents, LevelFormat, BorderStyle,
        TabStopType } = d;

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const base = path.dirname(path.resolve(process.argv[2]));
const FONT = "Calibri", PAGE_W = 11906, MARGIN = 1300, TEXT_W = PAGE_W - 2 * MARGIN;   // A4

function runs(text, opts = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]+\}|\^\{[^}]+\})/g;
  let last = 0, m;
  const push = (t, o) => { if (t) out.push(new TextRun({ text: t, font: FONT, size: opts.size, color: opts.color, ...o })); };
  while ((m = re.exec(text)) !== null) {
    push(text.slice(last, m.index), { bold: opts.bold, italics: opts.italics });
    const s = m[0];
    if (s.startsWith("**")) push(s.slice(2, -2), { bold: true, italics: opts.italics });
    else if (s.startsWith("*")) push(s.slice(1, -1), { italics: true, bold: opts.bold });
    else if (s.startsWith("_{")) push(s.slice(2, -1), { subScript: true, bold: opts.bold });
    else push(s.slice(2, -1), { superScript: true, bold: opts.bold });
    last = m.index + s.length;
  }
  push(text.slice(last), { bold: opts.bold, italics: opts.italics });
  return out;
}

let fig = 0, tab = 0;
const children = [];
const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };

for (const b of spec.blocks) {
  switch (b.type) {
    case "title":
      children.push(new Paragraph({ spacing: { before: 2400, after: 300 }, alignment: AlignmentType.CENTER,
        children: runs(b.text, { bold: true, size: 40 }) }));
      if (b.subtitle) children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 900 },
        children: runs(b.subtitle, { size: 26, color: "404040" }) }));
      for (const l of b.lines || []) children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
        children: runs(l, { size: 22 }) }));
      children.push(new Paragraph({ children: [new PageBreak()] }));
      break;
    case "toc":
      children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs("Contents") }));
      children.push(new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }));
      children.push(new Paragraph({ children: [new PageBreak()] }));
      break;
    case "h1": case "h2": case "h3":
      children.push(new Paragraph({ heading: { h1: HeadingLevel.HEADING_1, h2: HeadingLevel.HEADING_2, h3: HeadingLevel.HEADING_3 }[b.type],
        pageBreakBefore: !!b.newpage, children: runs(b.text) }));
      break;
    case "p":
      children.push(new Paragraph({ spacing: { after: 120, line: 276 }, alignment: b.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
        children: runs(b.text, { italics: b.italic, size: b.size }) }));
      break;
    case "eq":
      children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 120 },
        tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }],
        children: [...runs(b.text, { italics: true }), ...(b.label ? [new TextRun({ text: `\t(${b.label})`, font: FONT })] : [])] }));
      break;
    case "bullets":
      for (const t of b.items) children.push(new Paragraph({ numbering: { reference: b.numbered ? "num" : "bul", level: 0 },
        spacing: { after: 60 }, children: runs(t) }));
      break;
    case "figure": {
      fig++;
      const buf = fs.readFileSync(path.resolve(base, b.path));
      const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);            // PNG header
      const widthPx = Math.round((b.width || 1.0) * TEXT_W / 15);           // DXA -> px at 96 dpi
      children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, keepNext: true,
        children: [new ImageRun({ type: "png", data: buf, transformation: { width: widthPx, height: Math.round(widthPx * h / w) },
          altText: { title: `Figure ${fig}`, description: b.caption, name: `fig${fig}` } })] }));
      children.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 200 },
        children: [new TextRun({ text: `Figure ${fig}. `, bold: true, font: FONT, size: 19 }), ...runs(b.caption, { size: 19 })] }));
      break;
    }
    case "table": {
      tab++;
      const n = b.header.length;
      const widths = b.widths ? b.widths.map(x => Math.round(x * TEXT_W)) : Array(n).fill(Math.floor(TEXT_W / n));
      const tw = widths.reduce((a, c) => a + c, 0);
      children.push(new Paragraph({ keepNext: true, spacing: { before: 160, after: 80 },
        children: [new TextRun({ text: `Table ${tab}. `, bold: true, font: FONT, size: 19 }), ...runs(b.caption, { size: 19 })] }));
      const mk = (cells, head) => new TableRow({ tableHeader: head, cantSplit: true, children: cells.map((c, i) => new TableCell({
        borders, width: { size: widths[i], type: WidthType.DXA },
        shading: head ? { fill: "E7EEF7", type: ShadingType.CLEAR, color: "auto" } : undefined,
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: [new Paragraph({ alignment: (i > 0 && !head && b.align !== "left") ? AlignmentType.RIGHT : AlignmentType.LEFT,
          children: runs(String(c), { bold: head, size: b.font || 17 }) })] })) });
      children.push(new Table({ width: { size: tw, type: WidthType.DXA }, columnWidths: widths,
        rows: [mk(b.header, true), ...b.rows.map(r => mk(r, false))] }));
      if (b.note) children.push(new Paragraph({ spacing: { before: 60, after: 200 }, children: runs(b.note, { size: 16, italics: true }) }));
      else children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      break;
    }
    case "refs":
      for (const r of b.items) children.push(new Paragraph({ spacing: { after: 80 }, indent: { left: 400, hanging: 400 },
        children: runs(r, { size: 19 }) }));
      break;
    case "pagebreak":
      children.push(new Paragraph({ children: [new PageBreak()] }));
      break;
  }
}

const doc = new Document({
  creator: spec.author || "", title: spec.doc_title || "", description: spec.description || "",
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: "1F3864" }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 25, bold: true, font: FONT, color: "2E5597" }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, italics: true, font: FONT }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] } ] },
  features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: 1300, bottom: 1300, left: MARGIN, right: MARGIN } },
                  titlePage: true },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: spec.running_head || "", font: FONT, size: 16, color: "7F7F7F" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(process.argv[3], buf); console.log("wrote", process.argv[3]); });

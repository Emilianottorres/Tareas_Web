#!/usr/bin/env python3
"""
Cuadro Sinóptico - Unidades 1 y 2
Tecnologías para Desarrollo de Aplicaciones Web
ESCOM - IPN | Torres Casas Emiliano
"""
import io
import zlib
import struct


def esc(text):
    """Escape PDF text with Spanish chars."""
    text = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    table = {
        '\u00e1': '\\341', '\u00e9': '\\351', '\u00ed': '\\355',
        '\u00f3': '\\363', '\u00fa': '\\372', '\u00c1': '\\301',
        '\u00c9': '\\311', '\u00cd': '\\315', '\u00d3': '\\323',
        '\u00da': '\\332', '\u00f1': '\\361', '\u00d1': '\\321',
        '\u00fc': '\\374', '\u00bf': '\\277', '\u00a1': '\\241',
        '\u2022': '\\267', '\u2013': '-', '\u2014': '--',
    }
    for c, r in table.items():
        text = text.replace(c, r)
    return text


def txt(s, x, y, font='F1', size=9):
    return f"BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({esc(s)}) Tj ET"


def rect(x, y, w, h, r, g, b):
    return f"{r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f"


def stroke_rect(x, y, w, h, r, g, b, lw=1):
    return f"{r:.3f} {g:.3f} {b:.3f} RG {lw} w {x:.1f} {y:.1f} {w:.1f} {h:.1f} re S"


def line(x1, y1, x2, y2, r, g, b, lw=1):
    return f"{r:.3f} {g:.3f} {b:.3f} RG {lw} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S"



def brace(x, y_top, y_bot, rgb, lw=1.5):
    """Draw a right-facing curly brace."""
    r, g, b = rgb
    mid = (y_top + y_bot) / 2
    tip = x + 12
    cmds = [
        f"{r:.3f} {g:.3f} {b:.3f} RG {lw} w",
        f"{x:.1f} {y_top:.1f} m {tip:.1f} {y_top:.1f} {tip:.1f} {mid:.1f} {tip:.1f} {mid:.1f} c S",
        f"{x:.1f} {y_bot:.1f} m {tip:.1f} {y_bot:.1f} {tip:.1f} {mid:.1f} {tip:.1f} {mid:.1f} c S",
    ]
    return "\n".join(cmds)


class PDFWriter:
    """Simple PDF writer with correct object numbering."""

    def __init__(self, page_w=792, page_h=612):
        self.page_w = page_w
        self.page_h = page_h
        self.buf = io.BytesIO()
        self.offsets = {}
        self.obj_num = 0
        self.page_ids = []

        # Write header
        self.buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        # Reserve objects 1=Catalog, 2=Pages, 3=F1, 4=F2, 5=F3
        self.obj_num = 5

    def _write_obj_start(self, obj_id):
        self.offsets[obj_id] = self.buf.tell()
        self.buf.write(f"{obj_id} 0 obj\n".encode())

    def _write_obj_end(self):
        self.buf.write(b"endobj\n")

    def new_obj(self):
        self.obj_num += 1
        return self.obj_num

    def add_page(self, stream_text):
        """Add a page with the given content stream."""
        page_id = self.new_obj()
        content_id = self.new_obj()

        stream_bytes = stream_text.encode('latin-1', errors='replace')
        compressed = zlib.compress(stream_bytes)

        # Write content stream object
        self._write_obj_start(content_id)
        self.buf.write(f"<< /Length {len(compressed)} /Filter /FlateDecode >>\n".encode())
        self.buf.write(b"stream\n")
        self.buf.write(compressed)
        self.buf.write(b"\nendstream\n")
        self._write_obj_end()

        # Write page object
        self._write_obj_start(page_id)
        self.buf.write(
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {self.page_w} {self.page_h}] "
            f"/Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> >>\n".encode()
        )
        self._write_obj_end()

        self.page_ids.append(page_id)


    def finish(self, filename):
        """Write catalog, pages, fonts, xref and trailer."""
        # Write fonts (objects 3, 4, 5)
        self._write_obj_start(3)
        self.buf.write(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\n")
        self._write_obj_end()

        self._write_obj_start(4)
        self.buf.write(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\n")
        self._write_obj_end()

        self._write_obj_start(5)
        self.buf.write(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>\n")
        self._write_obj_end()

        # Write Pages (object 2)
        kids = " ".join(f"{pid} 0 R" for pid in self.page_ids)
        self._write_obj_start(2)
        self.buf.write(f"<< /Type /Pages /Kids [{kids}] /Count {len(self.page_ids)} >>\n".encode())
        self._write_obj_end()

        # Write Catalog (object 1)
        self._write_obj_start(1)
        self.buf.write(b"<< /Type /Catalog /Pages 2 0 R >>\n")
        self._write_obj_end()

        # Write xref
        xref_offset = self.buf.tell()
        max_obj = max(self.offsets.keys())
        self.buf.write(f"xref\n0 {max_obj + 1}\n".encode())
        self.buf.write(b"0000000000 65535 f \n")
        for i in range(1, max_obj + 1):
            off = self.offsets.get(i, 0)
            self.buf.write(f"{off:010d} 00000 n \n".encode())

        # Trailer
        self.buf.write(f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\n".encode())
        self.buf.write(f"startxref\n{xref_offset}\n%%EOF\n".encode())

        with open(filename, 'wb') as f:
            f.write(self.buf.getvalue())

        print(f"PDF: {filename} ({len(self.buf.getvalue())} bytes, {len(self.page_ids)} pages)")



def build_page_portada():
    """Page 1: Cover page."""
    c = []
    # Background decorative bar at top
    c.append(rect(0, 570, 792, 42, 0.5, 0.0, 0.2))
    c.append(txt("INSTITUTO POLIT\u00c9CNICO NACIONAL", 270, 585, 'F2', 14))

    # Title block
    c.append(txt("CUADRO SIN\u00d3PTICO", 280, 470, 'F2', 22))
    c.append(txt("Unidades 1 y 2", 330, 435, 'F2', 16))

    c.append(txt("Tecnolog\u00edas para Desarrollo de Aplicaciones Web",
                 210, 380, 'F2', 13))

    c.append(txt("Torres Casas Emiliano", 320, 320, 'F1', 13))
    c.append(txt("Cuadro Sin\u00f3ptico 1", 330, 285, 'F1', 12))
    c.append(txt("Sandra Morales", 340, 250, 'F1', 12))
    c.append(txt("27 de junio de 2026", 335, 210, 'F1', 12))

    # Bottom bar
    c.append(rect(0, 0, 792, 20, 0.0, 0.35, 0.55))
    return "\n".join(c)



def build_page_unit1():
    """Page 2: Synoptic chart for Unit 1."""
    c = []

    # Colors
    M = (0.50, 0.00, 0.20)  # Maroon - main
    T = (0.00, 0.40, 0.60)  # Teal - subtopics
    G = (0.15, 0.55, 0.30)  # Green - details

    # Title bar
    c.append(rect(20, 575, 752, 28, *M))
    c.append("1 1 1 rg")
    c.append(txt("UNIDAD 1: Aspectos b\u00e1sicos del desarrollo de aplicaciones web",
                 160, 583, 'F2', 12))
    c.append("0 0 0 rg")

    # Main box (left)
    mx, my, mw, mh = 30, 270, 105, 280
    c.append(rect(mx, my, mw, mh, *M))
    c.append("1 1 1 rg")
    c.append(txt("Aspectos", mx+18, my+mh-40, 'F2', 10))
    c.append(txt("b\u00e1sicos del", mx+12, my+mh-58, 'F2', 10))
    c.append(txt("desarrollo", mx+14, my+mh-76, 'F2', 10))
    c.append(txt("de apps web", mx+10, my+mh-94, 'F2', 10))
    c.append("0 0 0 rg")

    # Main brace
    bx = mx + mw + 3
    c.append(brace(bx, my + mh - 15, my + 15, M, 2))

    # Subtopics
    topics = [
        ("1.1 Evoluci\u00f3n hist\u00f3rica de Internet y la WWW", [
            "ARPANET (1969) - Red descentralizada",
            "TCP/IP adoptado en 1983",
            "WWW creada por Tim Berners-Lee (1989)",
            "HTML + URI/URL + HTTP",
            "Web 1.0 \u2013> Web 2.0 \u2013> Web 3.0",
        ]),
        ("1.2 La Internet y la WWW", [
            "Arquitectura Cliente/Servidor",
            "TCP/IP: 4 capas (Red, Internet, Transporte, Aplicaci\u00f3n)",
            "HTTP: M\u00e9todos GET/POST/PUT/DELETE, C\u00f3digos 1xx-5xx",
            "HTTPS: Cifrado TLS/SSL",
            "Navegadores: Mosaic, Netscape, Chrome, Firefox, Edge",
        ]),
        ("1.3 Est\u00e1ndares para la Web", [
            "W3C: HTML, CSS, XML, WCAG",
            "WHATWG: HTML Living Standard",
            "IETF: HTTP, TCP/IP, DNS",
            "ECMA: ECMAScript (JavaScript)",
            "HTML5, CSS3, ES6+, WAI-ARIA",
        ]),
        ("1.4 Entornos de desarrollo", [
            "IDEs: VS Code, WebStorm",
            "Control de versiones: Git, GitHub",
            "Frontend: React, Angular, Vue, Vite",
            "Backend: Node.js, Django, Laravel, Spring",
            "Testing y CI/CD: Jest, Docker, GitHub Actions",
        ]),
    ]

    sx = bx + 18
    sw = 175
    n = len(topics)
    each_h = 62
    gap = 6
    total = n * each_h + (n - 1) * gap
    base_y = my + (mh - total) / 2

    for i, (title, details) in enumerate(topics):
        # Position from top to bottom (reverse for PDF coords)
        sy = base_y + (n - 1 - i) * (each_h + gap)

        # Subtopic box
        c.append(rect(sx, sy, sw, each_h, *T))
        c.append("1 1 1 rg")
        c.append(txt(title, sx + 5, sy + each_h - 13, 'F2', 7))
        c.append("0 0 0 rg")

        # Connector line
        mid_y = sy + each_h / 2
        c.append(line(bx + 12, mid_y, sx, mid_y, *M, 1))

        # Brace from subtopic
        dbx = sx + sw + 3
        c.append(brace(dbx, sy + each_h - 5, sy + 5, T, 1.2))

        # Detail boxes
        dx = dbx + 16
        dw = 230
        n_d = len(details)
        d_spacing = each_h / (n_d + 0.5)

        for j, detail in enumerate(details):
            dy = sy + each_h - 10 - (j + 0.5) * d_spacing
            c.append(rect(dx, dy - 2, dw, 10, *G))
            c.append("1 1 1 rg")
            c.append(txt(detail, dx + 3, dy, 'F1', 6.5))
            c.append("0 0 0 rg")

    # Footer
    c.append(rect(0, 0, 792, 12, *M))
    c.append("1 1 1 rg")
    c.append(txt("Torres Casas Emiliano | ESCOM - IPN | Tecnolog\u00edas para Desarrollo de Aplicaciones Web",
                 220, 2, 'F1', 7))
    c.append("0 0 0 rg")
    return "\n".join(c)



def build_page_unit2():
    """Page 3: Synoptic chart for Unit 2."""
    c = []

    # Colors for Unit 2
    M = (0.00, 0.35, 0.55)  # Dark blue - main
    T = (0.55, 0.10, 0.40)  # Purple - subtopics
    G = (0.10, 0.50, 0.40)  # Teal-green - details

    # Title bar
    c.append(rect(20, 575, 752, 28, *M))
    c.append("1 1 1 rg")
    c.append(txt("UNIDAD 2: P\u00e1ginas Web con HTML", 270, 583, 'F2', 12))
    c.append("0 0 0 rg")

    # Main box
    mx, my, mw, mh = 30, 250, 105, 300
    c.append(rect(mx, my, mw, mh, *M))
    c.append("1 1 1 rg")
    c.append(txt("P\u00e1ginas", mx+22, my+mh-40, 'F2', 10))
    c.append(txt("Web con", mx+22, my+mh-58, 'F2', 10))
    c.append(txt("HTML", mx+30, my+mh-76, 'F2', 10))
    c.append("0 0 0 rg")

    # Main brace
    bx = mx + mw + 3
    c.append(brace(bx, my + mh - 15, my + 15, M, 2))

    # Subtopics Unit 2
    topics = [
        ("2.1 Evoluci\u00f3n del lenguaje HTML", [
            "HTML 1.0 (1991) - Estructura b\u00e1sica",
            "HTML 2.0 - 4.01: Formularios, tablas, CSS",
            "XHTML: Sintaxis estricta basada en XML",
            "HTML5 (2014): Sem\u00e1ntica, multimedia, APIs",
        ]),
        ("2.2 Estructura de un documento HTML", [
            "<!DOCTYPE html> - Declaraci\u00f3n del tipo",
            "<html>, <head>, <body> - Estructura ra\u00edz",
            "<meta>: charset, viewport, description",
            "<title>, <link>, <script> en head",
        ]),
        ("2.3 Elementos de HTML", [
            "Encabezados: h1-h6, P\u00e1rrafos: <p>",
            "Listas: <ul>, <ol>, <li>, <dl>",
            "Enlaces: <a href>, Im\u00e1genes: <img src>",
            "Sem\u00e1nticos: <header>, <nav>, <section>, <article>",
            "Multimedia: <audio>, <video>, <canvas>",
        ]),
        ("2.4 Tablas, contenedores y formularios", [
            "Tablas: <table>, <tr>, <th>, <td>, <thead>, <tbody>",
            "Contenedores: <div>, <span>, <figure>",
            "Forms: <form>, <input>, <select>, <textarea>",
            "Input types HTML5: email, date, range, color",
            "Validaci\u00f3n: required, pattern, min/max",
        ]),
        ("2.5 Creaci\u00f3n de archivos HTML est\u00e1ticos", [
            "Estructura b\u00e1sica de un archivo .html",
            "Buenas pr\u00e1cticas: indentaci\u00f3n, sem\u00e1ntica",
            "Enlace de CSS y JS externos",
            "Publicaci\u00f3n en servidor web",
        ]),
    ]

    sx = bx + 18
    sw = 185
    n = len(topics)
    each_h = 55
    gap = 4
    total = n * each_h + (n - 1) * gap
    base_y = my + (mh - total) / 2

    for i, (title, details) in enumerate(topics):
        sy = base_y + (n - 1 - i) * (each_h + gap)

        c.append(rect(sx, sy, sw, each_h, *T))
        c.append("1 1 1 rg")
        c.append(txt(title, sx + 5, sy + each_h - 13, 'F2', 7))
        c.append("0 0 0 rg")

        mid_y = sy + each_h / 2
        c.append(line(bx + 12, mid_y, sx, mid_y, *M, 1))

        dbx = sx + sw + 3
        c.append(brace(dbx, sy + each_h - 5, sy + 5, T, 1.2))

        dx = dbx + 16
        dw = 220
        n_d = len(details)
        d_spacing = each_h / (n_d + 0.5)

        for j, detail in enumerate(details):
            dy = sy + each_h - 10 - (j + 0.5) * d_spacing
            c.append(rect(dx, dy - 2, dw, 10, *G))
            c.append("1 1 1 rg")
            c.append(txt(detail, dx + 3, dy, 'F1', 6.2))
            c.append("0 0 0 rg")

    # Footer
    c.append(rect(0, 0, 792, 12, *M))
    c.append("1 1 1 rg")
    c.append(txt("Torres Casas Emiliano | ESCOM - IPN | Tecnolog\u00edas para Desarrollo de Aplicaciones Web",
                 220, 2, 'F1', 7))
    c.append("0 0 0 rg")
    return "\n".join(c)



def main():
    pdf = PDFWriter(page_w=792, page_h=612)  # Landscape

    pdf.add_page(build_page_portada())
    pdf.add_page(build_page_unit1())
    pdf.add_page(build_page_unit2())

    pdf.finish("MapaMental-Emiliano-Torres.pdf")


if __name__ == "__main__":
    main()

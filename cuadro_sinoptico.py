#!/usr/bin/env python3
"""
Cuadro Sinóptico - Unidades 1 y 2
Tecnologías para Desarrollo de Aplicaciones Web
ESCOM - IPN | Torres Casas Emiliano

Genera un PDF en formato apaisado (landscape) con un cuadro sinóptico
visual usando colores y estructura jerárquica con llaves.
"""
import io
import zlib
import struct
import math


class SynopticPDF:
    """Genera PDF landscape con cuadro sinóptico."""

    def __init__(self):
        self.objects = []
        self.pages_info = []
        self.obj_counter = 0
        self.image_objs = {}
        # Landscape letter: 792 x 612
        self.page_w = 792
        self.page_h = 612

    def _next_obj(self):
        self.obj_counter += 1
        return self.obj_counter

    def _add_obj(self, obj_id, content):
        self.objects.append((obj_id, content))


    def _load_png(self, filepath, name):
        """Load PNG and create PDF image XObject."""
        with open(filepath, 'rb') as f:
            data = f.read()
        pos = 8
        width = height = 0
        color_type = bit_depth = 0
        idat_chunks = []
        while pos < len(data):
            length = struct.unpack('>I', data[pos:pos+4])[0]
            chunk_type = data[pos+4:pos+8]
            chunk_data = data[pos+8:pos+8+length]
            pos += 12 + length
            if chunk_type == b'IHDR':
                width = struct.unpack('>I', chunk_data[0:4])[0]
                height = struct.unpack('>I', chunk_data[4:8])[0]
                bit_depth = chunk_data[8]
                color_type = chunk_data[9]
            elif chunk_type == b'IDAT':
                idat_chunks.append(chunk_data)
        compressed = b''.join(idat_chunks)
        raw = zlib.decompress(compressed)
        channels = 4 if color_type == 6 else 3 if color_type == 2 else 1
        has_alpha = color_type == 6
        stride = width * channels + 1
        rgb_data = bytearray()
        alpha_data = bytearray()
        for y in range(height):
            row_start = y * stride + 1
            for x in range(width):
                px_start = row_start + x * channels
                if has_alpha:
                    rgb_data.extend(raw[px_start:px_start+3])
                    alpha_data.append(raw[px_start+3])
                elif channels == 3:
                    rgb_data.extend(raw[px_start:px_start+3])
                else:
                    rgb_data.append(raw[px_start])
        rgb_compressed = zlib.compress(bytes(rgb_data), 9)
        img_obj_id = self._next_obj()
        smask_id = None
        if has_alpha:
            smask_id = self._next_obj()
            alpha_compressed = zlib.compress(bytes(alpha_data), 9)
            smask_content = (
                f"{smask_id} 0 obj\n<< /Type /XObject /Subtype /Image "
                f"/Width {width} /Height {height} /ColorSpace /DeviceGray "
                f"/BitsPerComponent 8 /Filter /FlateDecode "
                f"/Length {len(alpha_compressed)} >>\nstream\n"
            ).encode() + alpha_compressed + b"\nendstream\nendobj\n"
            self._add_obj(smask_id, smask_content)
        smask_ref = f"/SMask {smask_id} 0 R " if smask_id else ""
        cs = '/DeviceRGB' if channels >= 3 else '/DeviceGray'
        img_content = (
            f"{img_obj_id} 0 obj\n<< /Type /XObject /Subtype /Image "
            f"/Width {width} /Height {height} /ColorSpace {cs} "
            f"/BitsPerComponent {bit_depth} {smask_ref}"
            f"/Filter /FlateDecode /Length {len(rgb_compressed)} >>\nstream\n"
        ).encode() + rgb_compressed + b"\nendstream\nendobj\n"
        self._add_obj(img_obj_id, img_content)
        self.image_objs[name] = (img_obj_id, width, height)


    def _make_page(self, content_lines, images_used=None):
        """Create a landscape page."""
        page_id = self._next_obj()
        content_id = self._next_obj()
        stream_text = "\n".join(content_lines)
        stream_bytes = stream_text.encode('latin-1', errors='replace')
        compressed = zlib.compress(stream_bytes)
        xobject_str = ""
        if images_used:
            refs = " ".join(
                f"/{name} {self.image_objs[name][0]} 0 R"
                for name in images_used if name in self.image_objs
            )
            xobject_str = f"/XObject << {refs} >>"
        page_content = (
            f"{page_id} 0 obj\n<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {self.page_w} {self.page_h}] "
            f"/Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> "
            f"{xobject_str} >> >>\nendobj\n"
        ).encode()
        self._add_obj(page_id, page_content)
        content_obj = (
            f"{content_id} 0 obj\n<< /Filter /FlateDecode "
            f"/Length {len(compressed)} >>\nstream\n"
        ).encode() + compressed + b"\nendstream\nendobj\n"
        self._add_obj(content_id, content_obj)
        self.pages_info.append(page_id)


    def build(self, filename):
        """Assemble final PDF."""
        output = io.BytesIO()
        output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        cat_offset = output.tell()
        output.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        pages_offset = output.tell()
        kids = " ".join(f"{pid} 0 R" for pid in self.pages_info)
        output.write(f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(self.pages_info)} >>\nendobj\n".encode())
        f1_offset = output.tell()
        output.write(b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n")
        f2_offset = output.tell()
        output.write(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n")
        f3_offset = output.tell()
        output.write(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>\nendobj\n")
        obj_offsets = {1: cat_offset, 2: pages_offset, 3: f1_offset, 4: f2_offset, 5: f3_offset}
        for obj_id, content in self.objects:
            obj_offsets[obj_id] = output.tell()
            output.write(content)
        xref_offset = output.tell()
        max_obj = max(obj_offsets.keys())
        output.write(f"xref\n0 {max_obj + 1}\n".encode())
        output.write(b"0000000000 65535 f \n")
        for i in range(1, max_obj + 1):
            offset = obj_offsets.get(i, 0)
            output.write(f"{offset:010d} 00000 n \n".encode())
        output.write(f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\n".encode())
        output.write(f"startxref\n{xref_offset}\n%%EOF\n".encode())
        with open(filename, 'wb') as f:
            f.write(output.getvalue())
        print(f"PDF generado: {filename} ({len(output.getvalue())} bytes, {len(self.pages_info)} paginas)")



def esc(text):
    """Escape PDF text."""
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


def text_cmd(txt, x, y, font='F1', size=9):
    """Generate PDF text command."""
    return f"BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({esc(txt)}) Tj ET"


def rect_cmd(x, y, w, h, r, g, b, fill=True):
    """Generate colored rectangle."""
    if fill:
        return f"{r:.2f} {g:.2f} {b:.2f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f"
    else:
        return f"{r:.2f} {g:.2f} {b:.2f} RG 1 w {x:.1f} {y:.1f} {w:.1f} {h:.1f} re S"


def rounded_rect(x, y, w, h, r, g, b, radius=5):
    """Rounded rectangle with fill."""
    cmds = []
    cmds.append(f"{r:.2f} {g:.2f} {b:.2f} rg")
    # Simple approximation: rectangle + corner circles
    cmds.append(f"{x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")
    return "\n".join(cmds)


def line_cmd(x1, y1, x2, y2, r, g, b, width=1):
    """Draw a line."""
    return f"{r:.2f} {g:.2f} {b:.2f} RG {width} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S"


def brace_right(x, y_top, y_bottom, color_rgb, width=1.5):
    """Draw a right-facing brace { using bezier curves."""
    r, g, b = color_rgb
    mid_y = (y_top + y_bottom) / 2
    h = y_top - y_bottom
    tip_x = x + 12
    cmds = []
    cmds.append(f"{r:.2f} {g:.2f} {b:.2f} RG {width} w")
    # Top half curve
    cmds.append(f"{x:.1f} {y_top:.1f} m")
    cmds.append(f"{tip_x:.1f} {y_top:.1f} {tip_x:.1f} {mid_y:.1f} {tip_x:.1f} {mid_y:.1f} c S")
    # Bottom half curve
    cmds.append(f"{x:.1f} {y_bottom:.1f} m")
    cmds.append(f"{tip_x:.1f} {y_bottom:.1f} {tip_x:.1f} {mid_y:.1f} {tip_x:.1f} {mid_y:.1f} c S")
    return "\n".join(cmds)



def create_synoptic_chart():
    """Create the synoptic chart PDF."""
    pdf = SynopticPDF()

    # Load logos
    pdf._load_png('logo_ipn.png', 'logoIPN')
    pdf._load_png('logo_escom.png', 'logoESCOM')

    # ============================================================
    # PAGE 1: PORTADA
    # ============================================================
    lines = []
    # Logos
    lines.append(f"q 60 0 0 80 50 500 cm /logoIPN Do Q")
    lines.append(f"q 90 0 0 70 640 510 cm /logoESCOM Do Q")
    # Title
    lines.append(text_cmd("CUADRO SIN\u00d3PTICO", 260, 440, 'F2', 22))
    lines.append(text_cmd("Unidades 1 y 2", 310, 410, 'F2', 16))
    lines.append(text_cmd("Tecnolog\u00edas para Desarrollo de Aplicaciones Web", 200, 360, 'F2', 14))
    lines.append(text_cmd("Torres Casas Emiliano", 310, 310, 'F1', 13))
    lines.append(text_cmd("Cuadro Sin\u00f3ptico 1", 320, 270, 'F1', 12))
    lines.append(text_cmd("Sandra Morales", 330, 230, 'F1', 12))
    lines.append(text_cmd("27 de junio de 2026", 325, 180, 'F1', 12))
    pdf._make_page(lines, images_used=['logoIPN', 'logoESCOM'])


    # ============================================================
    # PAGE 2: CUADRO SINOPTICO - UNIDAD 1
    # ============================================================
    lines = []

    # Colors (RGB 0-1)
    c_main = (0.5, 0.0, 0.2)     # Maroon (main topic)
    c_sub1 = (0.0, 0.4, 0.6)     # Teal (subtopics)
    c_sub2 = (0.2, 0.5, 0.2)     # Green (details)
    c_sub3 = (0.6, 0.3, 0.0)     # Orange (sub-details)

    # Title bar
    lines.append(rounded_rect(20, 575, 752, 30, *c_main))
    lines.append("1.0 1.0 1.0 rg")
    lines.append(text_cmd("UNIDAD 1: Aspectos b\u00e1sicos del desarrollo de aplicaciones web", 150, 585, 'F2', 13))
    lines.append("0 0 0 rg")

    # Main topic box (left side)
    main_x = 30
    main_y = 300
    main_w = 100
    main_h = 240
    lines.append(rounded_rect(main_x, main_y, main_w, main_h, *c_main))
    lines.append("1.0 1.0 1.0 rg")
    lines.append(text_cmd("Aspectos", main_x+15, main_y+main_h-30, 'F2', 9))
    lines.append(text_cmd("b\u00e1sicos del", main_x+10, main_y+main_h-45, 'F2', 9))
    lines.append(text_cmd("desarrollo", main_x+15, main_y+main_h-60, 'F2', 9))
    lines.append(text_cmd("de apps", main_x+20, main_y+main_h-75, 'F2', 9))
    lines.append(text_cmd("web", main_x+32, main_y+main_h-90, 'F2', 9))
    lines.append("0 0 0 rg")

    # Brace from main box
    brace_x = main_x + main_w + 5
    lines.append(brace_right(brace_x, main_y + main_h - 10, main_y + 10, c_main, 2))

    # Level 2: Four subtopics
    subtopics = [
        ("1.1 Evoluci\u00f3n hist\u00f3rica", [
            "ARPANET (1969)",
            "TCP/IP (1983)",
            "WWW - Tim Berners-Lee (1989)",
            "Web 1.0 -> 2.0 -> 3.0"
        ]),
        ("1.2 Internet y WWW", [
            "Arq. Cliente/Servidor",
            "Protocolo TCP/IP (4 capas)",
            "HTTP (m\u00e9todos, c\u00f3digos)",
            "Navegadores web"
        ]),
        ("1.3 Est\u00e1ndares Web", [
            "W3C, WHATWG, IETF, ECMA",
            "HTML5, CSS3, ES6+",
            "WAI-ARIA (accesibilidad)"
        ]),
        ("1.4 Entornos de desarrollo", [
            "IDEs (VS Code)",
            "Git / GitHub",
            "Frontend/Backend",
            "Testing y CI/CD"
        ]),
    ]

    sub_x = brace_x + 20
    sub_w = 155
    sub_h_each = 52
    gap = 6
    total_h = len(subtopics) * sub_h_each + (len(subtopics)-1) * gap
    start_y = main_y + (main_h - total_h) / 2

    for i, (title, details) in enumerate(subtopics):
        sy = start_y + (len(subtopics) - 1 - i) * (sub_h_each + gap)

        # Subtopic box
        lines.append(rounded_rect(sub_x, sy, sub_w, sub_h_each, *c_sub1))
        lines.append("1.0 1.0 1.0 rg")
        lines.append(text_cmd(title, sub_x + 8, sy + sub_h_each - 15, 'F2', 8))
        lines.append("0 0 0 rg")

        # Connector line from main brace to subtopic
        conn_y = sy + sub_h_each / 2
        lines.append(line_cmd(brace_x + 12, conn_y, sub_x, conn_y, *c_main, 1))

        # Brace from subtopic to details
        detail_brace_x = sub_x + sub_w + 3
        detail_top = sy + sub_h_each - 5
        detail_bot = sy + 5
        lines.append(brace_right(detail_brace_x, detail_top, detail_bot, c_sub1, 1.5))

        # Detail items
        detail_x = detail_brace_x + 18
        detail_start_y = sy + sub_h_each - 12
        line_spacing = sub_h_each / (len(details) + 1)

        for j, detail in enumerate(details):
            dy = detail_start_y - (j + 0.5) * line_spacing
            # Small colored bullet box
            lines.append(rounded_rect(detail_x, dy - 3, 180, 12, *c_sub2))
            lines.append("1.0 1.0 1.0 rg")
            lines.append(text_cmd(detail, detail_x + 4, dy - 1, 'F1', 7))
            lines.append("0 0 0 rg")

    pdf._make_page(lines)


    # ============================================================
    # PAGE 3: CUADRO SINOPTICO - UNIDAD 2
    # ============================================================
    lines = []

    # Colors for Unit 2
    c_main2 = (0.0, 0.35, 0.55)   # Dark blue
    c_sub2a = (0.6, 0.1, 0.4)     # Purple
    c_sub2b = (0.1, 0.5, 0.4)     # Teal-green
    c_sub2c = (0.7, 0.4, 0.0)     # Dark orange

    # Title bar
    lines.append(rounded_rect(20, 575, 752, 30, *c_main2))
    lines.append("1.0 1.0 1.0 rg")
    lines.append(text_cmd("UNIDAD 2: P\u00e1ginas Web con HTML", 250, 585, 'F2', 13))
    lines.append("0 0 0 rg")

    # Main topic box
    main_x = 30
    main_y = 280
    main_w = 100
    main_h = 270
    lines.append(rounded_rect(main_x, main_y, main_w, main_h, *c_main2))
    lines.append("1.0 1.0 1.0 rg")
    lines.append(text_cmd("P\u00e1ginas", main_x+20, main_y+main_h-30, 'F2', 9))
    lines.append(text_cmd("Web con", main_x+20, main_y+main_h-45, 'F2', 9))
    lines.append(text_cmd("HTML", main_x+28, main_y+main_h-60, 'F2', 9))
    lines.append("0 0 0 rg")

    # Brace
    brace_x = main_x + main_w + 5
    lines.append(brace_right(brace_x, main_y + main_h - 10, main_y + 10, c_main2, 2))

    # Level 2: Five subtopics for Unit 2
    subtopics2 = [
        ("2.1 Evoluci\u00f3n de HTML", [
            "HTML 1.0 a HTML5",
            "XHTML, HTML Living Standard",
            "Nuevas APIs y elementos"
        ]),
        ("2.2 Estructura documento", [
            "<!DOCTYPE html>",
            "<html>, <head>, <body>",
            "Meta tags, t\u00edtulo, enlaces"
        ]),
        ("2.3 Elementos de HTML", [
            "Encabezados, p\u00e1rrafos, listas",
            "Enlaces e im\u00e1genes",
            "Sem\u00e1ntica: header, nav, section",
            "Audio, video, canvas"
        ]),
        ("2.4 Tablas y formularios", [
            "table, tr, th, td",
            "form, input, select, textarea",
            "Validaci\u00f3n de formularios",
            "Tipos de input HTML5"
        ]),
        ("2.5 Archivos HTML est\u00e1ticos", [
            "Creaci\u00f3n y estructura",
            "Buenas pr\u00e1cticas",
            "Publicaci\u00f3n en servidor"
        ]),
    ]

    sub_x = brace_x + 20
    sub_w = 160
    sub_h_each = 48
    gap = 5
    total_h = len(subtopics2) * sub_h_each + (len(subtopics2)-1) * gap
    start_y = main_y + (main_h - total_h) / 2

    for i, (title, details) in enumerate(subtopics2):
        sy = start_y + (len(subtopics2) - 1 - i) * (sub_h_each + gap)

        # Subtopic box
        lines.append(rounded_rect(sub_x, sy, sub_w, sub_h_each, *c_sub2a))
        lines.append("1.0 1.0 1.0 rg")
        lines.append(text_cmd(title, sub_x + 8, sy + sub_h_each - 15, 'F2', 8))
        lines.append("0 0 0 rg")

        # Connector
        conn_y = sy + sub_h_each / 2
        lines.append(line_cmd(brace_x + 12, conn_y, sub_x, conn_y, *c_main2, 1))

        # Brace to details
        detail_brace_x = sub_x + sub_w + 3
        detail_top = sy + sub_h_each - 5
        detail_bot = sy + 5
        lines.append(brace_right(detail_brace_x, detail_top, detail_bot, c_sub2a, 1.5))

        # Details
        detail_x = detail_brace_x + 18
        detail_start_y = sy + sub_h_each - 10
        line_spacing = sub_h_each / (len(details) + 1)

        for j, detail in enumerate(details):
            dy = detail_start_y - (j + 0.5) * line_spacing
            lines.append(rounded_rect(detail_x, dy - 3, 195, 11, *c_sub2b))
            lines.append("1.0 1.0 1.0 rg")
            lines.append(text_cmd(detail, detail_x + 4, dy - 1, 'F1', 7))
            lines.append("0 0 0 rg")

    pdf._make_page(lines)


    # Build PDF
    pdf.build("MapaMental-Emiliano-Torres.pdf")


if __name__ == "__main__":
    create_synoptic_chart()

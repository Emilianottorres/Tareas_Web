#!/usr/bin/env python3
"""
Generador de PDF - Resumen Unidad 1
Tecnologías para Desarrollo de Aplicaciones Web
ESCOM - IPN | Torres Casas Emiliano
"""
import io
import zlib
import struct


class PDF:
    def __init__(self):
        self.objects = []  # (obj_number, content_bytes)
        self.pages_info = []  # list of (page_obj_id, content_obj_id)
        self.obj_counter = 0
        self.image_objs = {}  # name -> (obj_id, width, height)

    def _next_obj(self):
        self.obj_counter += 1
        return self.obj_counter

    def _add_obj(self, obj_id, content):
        self.objects.append((obj_id, content))


    def _load_png(self, filepath, name):
        """Load PNG and create PDF image XObject."""
        with open(filepath, 'rb') as f:
            data = f.read()

        # Parse PNG
        pos = 8  # Skip signature
        width = height = 0
        color_type = 0
        bit_depth = 0
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

        # Decompress image data
        compressed = b''.join(idat_chunks)
        raw = zlib.decompress(compressed)


        # Determine channels
        if color_type == 2:  # RGB
            channels = 3
            cs = '/DeviceRGB'
        elif color_type == 6:  # RGBA
            channels = 4
            cs = '/DeviceRGB'
        elif color_type == 0:  # Grayscale
            channels = 1
            cs = '/DeviceGray'
        else:
            channels = 3
            cs = '/DeviceRGB'

        # Remove PNG filter bytes and separate alpha
        stride = width * channels + 1
        rgb_data = bytearray()
        alpha_data = bytearray()
        has_alpha = (color_type == 6)

        for y in range(height):
            row_start = y * stride + 1  # skip filter byte
            for x in range(width):
                px_start = row_start + x * channels
                if has_alpha:
                    rgb_data.extend(raw[px_start:px_start+3])
                    alpha_data.append(raw[px_start+3])
                elif channels == 3:
                    rgb_data.extend(raw[px_start:px_start+3])
                elif channels == 1:
                    rgb_data.append(raw[px_start])


        # Compress RGB data
        rgb_compressed = zlib.compress(bytes(rgb_data), 9)

        img_obj_id = self._next_obj()
        smask_id = None

        if has_alpha:
            # Create soft mask for alpha
            smask_id = self._next_obj()
            alpha_compressed = zlib.compress(bytes(alpha_data), 9)
            smask_content = (
                f"{smask_id} 0 obj\n"
                f"<< /Type /XObject /Subtype /Image "
                f"/Width {width} /Height {height} "
                f"/ColorSpace /DeviceGray /BitsPerComponent 8 "
                f"/Filter /FlateDecode /Length {len(alpha_compressed)} >>\n"
                f"stream\n"
            ).encode() + alpha_compressed + b"\nendstream\nendobj\n"
            self._add_obj(smask_id, smask_content)

        # Create image XObject
        smask_ref = f"/SMask {smask_id} 0 R " if smask_id else ""
        img_content = (
            f"{img_obj_id} 0 obj\n"
            f"<< /Type /XObject /Subtype /Image "
            f"/Width {width} /Height {height} "
            f"/ColorSpace {cs} /BitsPerComponent {bit_depth} "
            f"{smask_ref}"
            f"/Filter /FlateDecode /Length {len(rgb_compressed)} >>\n"
            f"stream\n"
        ).encode() + rgb_compressed + b"\nendstream\nendobj\n"
        self._add_obj(img_obj_id, img_content)

        self.image_objs[name] = (img_obj_id, width, height)
        return img_obj_id


    def _escape(self, text):
        """Escape text for PDF strings."""
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

    def _make_page(self, content_lines, images_used=None):
        """Create a page with text content and optional images."""
        page_id = self._next_obj()
        content_id = self._next_obj()

        stream_text = "\n".join(content_lines)
        stream_bytes = stream_text.encode('latin-1', errors='replace')
        compressed = zlib.compress(stream_bytes)


        # Build XObject references for images on this page
        xobject_str = ""
        if images_used:
            refs = " ".join(
                f"/{name} {self.image_objs[name][0]} 0 R"
                for name in images_used if name in self.image_objs
            )
            xobject_str = f"/XObject << {refs} >>"

        page_content = (
            f"{page_id} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R "
            f"/Resources << /Font << "
            f"/F1 3 0 R /F2 4 0 R /F3 5 0 R >> "
            f"{xobject_str} >> >>\n"
            f"endobj\n"
        ).encode()
        self._add_obj(page_id, page_content)

        content_obj = (
            f"{content_id} 0 obj\n"
            f"<< /Filter /FlateDecode /Length {len(compressed)} >>\n"
            f"stream\n"
        ).encode() + compressed + b"\nendstream\nendobj\n"
        self._add_obj(content_id, content_obj)

        self.pages_info.append(page_id)


    def build(self, filename):
        """Assemble and write the final PDF."""
        output = io.BytesIO()

        # Header
        output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        # Reserve obj 1=Catalog, 2=Pages, 3-5=Fonts
        # Catalog
        cat_offset = output.tell()
        output.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Pages placeholder - write later
        pages_offset = output.tell()
        kids = " ".join(f"{pid} 0 R" for pid in self.pages_info)
        pages_str = (
            f"2 0 obj\n<< /Type /Pages /Kids [{kids}] "
            f"/Count {len(self.pages_info)} >>\nendobj\n"
        )
        output.write(pages_str.encode())

        # Fonts
        f1_offset = output.tell()
        output.write(b"3 0 obj\n<< /Type /Font /Subtype /Type1 "
                     b"/BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n")
        f2_offset = output.tell()
        output.write(b"4 0 obj\n<< /Type /Font /Subtype /Type1 "
                     b"/BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n")
        f3_offset = output.tell()
        output.write(b"5 0 obj\n<< /Type /Font /Subtype /Type1 "
                     b"/BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>\nendobj\n")


        # Write all other objects and record offsets
        obj_offsets = {1: 9, 2: pages_offset, 3: f1_offset, 4: f2_offset, 5: f3_offset}
        for obj_id, content in self.objects:
            obj_offsets[obj_id] = output.tell()
            output.write(content)

        # Need to rewrite pages with correct kids
        # Actually we already wrote it - but we need offsets correct
        # Let's just track all offsets and write xref

        # Cross-reference table
        xref_offset = output.tell()
        max_obj = max(obj_offsets.keys())
        output.write(f"xref\n0 {max_obj + 1}\n".encode())
        output.write(b"0000000000 65535 f \n")
        for i in range(1, max_obj + 1):
            offset = obj_offsets.get(i, 0)
            output.write(f"{offset:010d} 00000 n \n".encode())

        # Trailer
        output.write(f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\n".encode())
        output.write(f"startxref\n{xref_offset}\n%%EOF\n".encode())

        with open(filename, 'wb') as f:
            f.write(output.getvalue())

        size = len(output.getvalue())
        print(f"PDF generado: {filename} ({size} bytes, {len(self.pages_info)} paginas)")



class PageBuilder:
    """Helper to build page content streams."""
    def __init__(self):
        self.lines = []
        self.y = 750
        self.font_size = 11
        self.line_h = 14
        self.margin_l = 72
        self.margin_r = 540
        self.page_w = 612

    def reset(self):
        self.lines = []
        self.y = 750

    def text(self, txt, font='F1', size=None, x=None, centered=False):
        if size is None:
            size = self.font_size
        if x is None:
            x = self.margin_l
        if centered:
            tw = len(txt) * size * 0.45
            x = (self.page_w - tw) / 2
        escaped = self._esc(txt)
        self.lines.append(
            f"BT /{font} {size} Tf {x:.1f} {self.y:.1f} Td ({escaped}) Tj ET"
        )
        self.y -= self.line_h

    def _esc(self, text):
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


    def image(self, name, x, y, w, h):
        """Place image on page."""
        self.lines.append(f"q {w:.1f} 0 0 {h:.1f} {x:.1f} {y:.1f} cm /{name} Do Q")

    def space(self, n=1):
        self.y -= self.line_h * n

    def title(self, txt, size=18):
        self.y -= 10
        self.text(txt, font='F2', size=size, centered=True)
        self.y -= 10

    def subtitle(self, txt, size=14):
        self.y -= 8
        self.text(txt, font='F2', size=size)
        self.y -= 4

    def subsubtitle(self, txt, size=12):
        self.y -= 6
        self.text(txt, font='F2', size=size)
        self.y -= 2

    def para(self, txt, indent=0):
        words = txt.split()
        if not words:
            self.y -= self.line_h
            return
        x = self.margin_l + indent
        max_w = self.margin_r - x
        cw = self.font_size * 0.48
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if len(test) * cw > max_w:
                if line:
                    self.text(line, x=x)
                line = word
            else:
                line = test
        if line:
            self.text(line, x=x)
        self.y -= 4

    def bullet(self, txt, level=0):
        indent = 20 + level * 20
        self.para(f"\u2022 {txt}", indent=indent)

    def numbered(self, n, txt):
        self.para(f"{n}. {txt}", indent=20)

    def get_lines(self):
        return self.lines[:]



def create_document():
    pdf = PDF()

    # Load images
    pdf._load_png('logo_ipn.png', 'logoIPN')
    pdf._load_png('logo_escom.png', 'logoESCOM')

    p = PageBuilder()

    # ========== PAGE 1: PORTADA ==========
    # Place logos
    p.image('logoIPN', 72, 640, 80, 110)      # left side
    p.image('logoESCOM', 430, 660, 110, 90)    # right side

    p.y = 620
    p.space(3)
    p.title("RESUMEN UNIDAD 1", size=20)
    p.space(2)
    p.text("Tecnolog\u00edas para Desarrollo de Aplicaciones Web",
           font='F2', size=13, centered=True)
    p.space(2)
    p.text("Torres Casas Emiliano", size=12, centered=True)
    p.space(2)
    p.text("Resumen: Aspectos b\u00e1sicos del desarrollo", size=12, centered=True)
    p.text("de aplicaciones web", size=12, centered=True)
    p.space(2)
    p.text("Sandra Morales", size=12, centered=True)
    p.space(2)
    p.text("27 de junio de 2026", size=12, centered=True)

    pdf._make_page(p.get_lines(), images_used=['logoIPN', 'logoESCOM'])


    # ========== PAGE 2: INDICE ==========
    p.reset()
    p.title("\u00cdNDICE", size=16)
    p.space(1)
    p.para("1. Evoluci\u00f3n hist\u00f3rica de Internet y la WWW")
    p.para("2. La Internet y la WWW")
    p.para("    2.1 Arquitectura Cliente/Servidor")
    p.para("    2.2 Protocolo TCP/IP")
    p.para("    2.3 Protocolo de Transferencia de Hipertexto (HTTP)")
    p.para("    2.4 Evoluci\u00f3n de Navegadores Web")
    p.para("3. Est\u00e1ndares para la Web")
    p.para("4. Entornos de desarrollo para Aplicaciones Web")
    p.para("5. Conclusiones")
    pdf._make_page(p.get_lines())

    # ========== PAGE 3: SECCION 1 ==========
    p.reset()
    p.subtitle("1. Evoluci\u00f3n hist\u00f3rica de Internet y la WWW")
    p.space(0.5)
    p.para("Internet tiene sus or\u00edgenes en ARPANET, una red creada en 1969 por el "
           "Departamento de Defensa de los Estados Unidos con el fin de interconectar "
           "universidades e instituciones de investigaci\u00f3n. El objetivo principal era "
           "crear una red descentralizada capaz de resistir fallos parciales.")
    p.para("En 1983, se adopt\u00f3 el protocolo TCP/IP como est\u00e1ndar de comunicaci\u00f3n, lo "
           "que permiti\u00f3 la interconexi\u00f3n de redes heterog\u00e9neas y marc\u00f3 el nacimiento "
           "formal de Internet tal como la conocemos.")
    p.para("La World Wide Web (WWW) fue inventada por Tim Berners-Lee en 1989 en el "
           "CERN (Organizaci\u00f3n Europea para la Investigaci\u00f3n Nuclear). Su propuesta "
           "combinaba tres tecnolog\u00edas fundamentales:")
    p.bullet("HTML (HyperText Markup Language): lenguaje de marcado para crear documentos.")
    p.bullet("URI/URL (Uniform Resource Identifier/Locator): sistema de direccionamiento \u00fanico.")
    p.bullet("HTTP (HyperText Transfer Protocol): protocolo de transferencia de hipertexto.")
    p.para("En 1991 se public\u00f3 la primera p\u00e1gina web, y en 1993 el navegador Mosaic "
           "populariz\u00f3 el acceso gr\u00e1fico a la Web. Desde entonces, la Web ha evolucionado "
           "desde p\u00e1ginas est\u00e1ticas (Web 1.0) hasta aplicaciones interactivas y "
           "colaborativas (Web 2.0), y actualmente hacia la Web sem\u00e1ntica e inteligente (Web 3.0).")
    pdf._make_page(p.get_lines())


    # ========== PAGE 4: SECCION 2.1 y 2.2 ==========
    p.reset()
    p.subtitle("2. La Internet y la WWW")
    p.subsubtitle("2.1 Arquitectura Cliente/Servidor")
    p.para("La arquitectura Cliente/Servidor es el modelo fundamental sobre el que operan "
           "las aplicaciones web. En este modelo:")
    p.bullet("Cliente: Es el programa (generalmente un navegador web) que realiza peticiones "
             "de recursos o servicios. El cliente inicia la comunicaci\u00f3n y presenta la "
             "informaci\u00f3n al usuario.")
    p.bullet("Servidor: Es el programa que espera y responde a las peticiones de los clientes. "
             "Proporciona recursos, procesa datos y ejecuta la l\u00f3gica de negocio.")
    p.para("Caracter\u00edsticas principales:")
    p.numbered(1, "El cliente inicia las solicitudes (requests).")
    p.numbered(2, "El servidor est\u00e1 en espera permanente de peticiones.")
    p.numbered(3, "La comunicaci\u00f3n es de tipo solicitud-respuesta.")
    p.numbered(4, "Los roles son asim\u00e9tricos: el cliente solicita y el servidor provee.")
    p.numbered(5, "Es un modelo escalable: un servidor puede atender m\u00faltiples clientes.")
    p.para("En el contexto web, el navegador act\u00faa como cliente, enviando peticiones HTTP "
           "al servidor web, el cual responde con documentos HTML, im\u00e1genes, datos JSON, "
           "entre otros recursos.")
    p.space(1)
    p.subsubtitle("2.2 Protocolo TCP/IP")
    p.para("TCP/IP (Transmission Control Protocol / Internet Protocol) es la suite de "
           "protocolos que permite la comunicaci\u00f3n en Internet. Se organiza en cuatro capas:")
    p.numbered(1, "Capa de Acceso a Red: Maneja la transmisi\u00f3n f\u00edsica de datos (Ethernet, Wi-Fi).")
    p.numbered(2, "Capa de Internet (IP): Direccionamiento l\u00f3gico y enrutamiento de paquetes.")
    p.numbered(3, "Capa de Transporte (TCP/UDP): TCP es orientado a conexi\u00f3n con entrega "
                  "ordenada. UDP es sin conexi\u00f3n, m\u00e1s r\u00e1pido pero sin garant\u00eda.")
    p.numbered(4, "Capa de Aplicaci\u00f3n: Protocolos como HTTP, FTP, SMTP, DNS.")
    p.para("Conceptos clave:")
    p.bullet("Direcci\u00f3n IP: Identificador num\u00e9rico \u00fanico (IPv4: 32 bits, IPv6: 128 bits).")
    p.bullet("Puerto: N\u00famero que identifica un servicio espec\u00edfico (HTTP: 80, HTTPS: 443).")
    p.bullet("DNS: Sistema que traduce nombres de dominio a direcciones IP.")
    pdf._make_page(p.get_lines())


    # ========== PAGE 5: SECCION 2.3 y 2.4 ==========
    p.reset()
    p.subsubtitle("2.3 Protocolo de Transferencia de Hipertexto (HTTP)")
    p.para("HTTP es el protocolo de la capa de aplicaci\u00f3n que permite la comunicaci\u00f3n entre "
           "clientes y servidores web. Es un protocolo sin estado (stateless).")
    p.para("Estructura de una petici\u00f3n HTTP:")
    p.bullet("L\u00ednea de petici\u00f3n: m\u00e9todo + URI + versi\u00f3n (ej: GET /index.html HTTP/1.1)")
    p.bullet("Cabeceras (Headers): metadatos de la petici\u00f3n.")
    p.bullet("Cuerpo (Body): datos enviados (en POST, PUT, etc.)")
    p.para("M\u00e9todos HTTP principales:")
    p.bullet("GET: Solicita un recurso (solo lectura).")
    p.bullet("POST: Env\u00eda datos al servidor para crear un recurso.")
    p.bullet("PUT: Actualiza un recurso existente completamente.")
    p.bullet("DELETE: Elimina un recurso.")
    p.bullet("PATCH: Actualiza parcialmente un recurso.")
    p.para("C\u00f3digos de respuesta HTTP:")
    p.bullet("1xx: Informativo.")
    p.bullet("2xx: \u00c9xito (200 OK, 201 Created).")
    p.bullet("3xx: Redirecci\u00f3n (301, 302).")
    p.bullet("4xx: Error del cliente (400 Bad Request, 404 Not Found).")
    p.bullet("5xx: Error del servidor (500 Internal Server Error).")
    p.para("HTTPS es la versi\u00f3n segura de HTTP que utiliza cifrado TLS/SSL.")
    p.space(1)
    p.subsubtitle("2.4 Evoluci\u00f3n de Navegadores Web")
    p.para("Los navegadores web han sido fundamentales en la evoluci\u00f3n de las aplicaciones web:")
    p.bullet("1990 - WorldWideWeb: Primer navegador creado por Tim Berners-Lee.")
    p.bullet("1993 - Mosaic: Primer navegador gr\u00e1fico popular.")
    p.bullet("1994 - Netscape Navigator: Domin\u00f3 el mercado en los 90s.")
    p.bullet("1995 - Internet Explorer: Inici\u00f3 la Guerra de los Navegadores.")
    p.bullet("2004 - Mozilla Firefox: C\u00f3digo abierto, promovi\u00f3 est\u00e1ndares web.")
    p.bullet("2008 - Google Chrome: Motor V8, revolucion\u00f3 el rendimiento.")
    p.bullet("2015 - Microsoft Edge: Reemplazo de IE, migrado a Chromium.")
    p.para("Componentes de un navegador moderno:")
    p.numbered(1, "Motor de renderizado (Blink, WebKit, Gecko).")
    p.numbered(2, "Motor de JavaScript (V8, SpiderMonkey, JavaScriptCore).")
    p.numbered(3, "Capa de red para peticiones HTTP.")
    p.numbered(4, "Int\u00e9rprete de HTML/CSS.")
    p.numbered(5, "Herramientas de desarrollo integradas.")
    pdf._make_page(p.get_lines())


    # ========== PAGE 6: SECCION 3 ==========
    p.reset()
    p.subtitle("3. Est\u00e1ndares para la Web")
    p.para("Los est\u00e1ndares web son especificaciones t\u00e9cnicas que definen c\u00f3mo deben funcionar "
           "las tecnolog\u00edas web. Son desarrollados principalmente por:")
    p.bullet("W3C (World Wide Web Consortium): Fundado por Tim Berners-Lee, define est\u00e1ndares "
             "para HTML, CSS, XML, accesibilidad (WCAG).")
    p.bullet("WHATWG (Web Hypertext Application Technology Working Group): Mantiene el "
             "est\u00e1ndar vivo de HTML (HTML Living Standard).")
    p.bullet("IETF (Internet Engineering Task Force): Define protocolos de Internet como "
             "HTTP, TCP/IP, DNS.")
    p.bullet("ECMA International: Define el est\u00e1ndar ECMAScript (JavaScript).")
    p.para("Est\u00e1ndares fundamentales:")
    p.bullet("HTML5: Elementos sem\u00e1nticos, multimedia nativa, APIs de geolocalizaci\u00f3n, "
             "almacenamiento local, Canvas.")
    p.bullet("CSS3: Animaciones, flexbox, grid, media queries para dise\u00f1o responsivo.")
    p.bullet("ECMAScript (ES6+): M\u00f3dulos, clases, promesas, async/await.")
    p.bullet("WAI-ARIA: Est\u00e1ndares de accesibilidad web.")
    p.para("La importancia de seguir est\u00e1ndares radica en garantizar la interoperabilidad, "
           "accesibilidad, mantenibilidad y compatibilidad entre diferentes navegadores y dispositivos.")
    pdf._make_page(p.get_lines())


    # ========== PAGE 7: SECCION 4 ==========
    p.reset()
    p.subtitle("4. Entornos de desarrollo para Aplicaciones Web")
    p.para("Un entorno de desarrollo web comprende las herramientas y tecnolog\u00edas necesarias "
           "para crear, probar y desplegar aplicaciones web.")
    p.para("Componentes de un entorno de desarrollo:")
    p.para("Editor de c\u00f3digo / IDE:", indent=10)
    p.bullet("Visual Studio Code, WebStorm, Sublime Text.", level=1)
    p.bullet("Caracter\u00edsticas: resaltado de sintaxis, autocompletado, depuraci\u00f3n.", level=1)
    p.para("Control de versiones:", indent=10)
    p.bullet("Git como sistema distribuido. Plataformas: GitHub, GitLab, Bitbucket.", level=1)
    p.para("Tecnolog\u00edas Frontend:", indent=10)
    p.bullet("HTML5, CSS3, JavaScript/TypeScript.", level=1)
    p.bullet("Frameworks: React, Angular, Vue.js, Svelte.", level=1)
    p.bullet("Empaquetadores: Webpack, Vite, Parcel.", level=1)
    p.para("Tecnolog\u00edas Backend:", indent=10)
    p.bullet("Node.js (Express), Python (Django, Flask), PHP (Laravel), Java (Spring).", level=1)
    p.bullet("Bases de datos: MySQL, PostgreSQL, MongoDB, Redis.", level=1)
    p.para("Herramientas de prueba:", indent=10)
    p.bullet("Unitarias: Jest, Mocha, Pytest.", level=1)
    p.bullet("Integraci\u00f3n: Cypress, Selenium, Playwright.", level=1)
    p.para("Herramientas de despliegue:", indent=10)
    p.bullet("Docker, Kubernetes. Cloud: AWS, Azure, GCP.", level=1)
    p.bullet("CI/CD: GitHub Actions, Jenkins, GitLab CI.", level=1)
    p.para("Herramientas del navegador:", indent=10)
    p.bullet("DevTools: inspector de elementos, consola, red, rendimiento.", level=1)
    p.para("Metodolog\u00edas de desarrollo:")
    p.bullet("Desarrollo \u00e1gil (Scrum, Kanban).")
    p.bullet("Integraci\u00f3n y despliegue continuo (CI/CD).")
    p.bullet("Desarrollo guiado por pruebas (TDD).")
    pdf._make_page(p.get_lines())


    # ========== PAGE 8: CONCLUSIONES ==========
    p.reset()
    p.subtitle("5. Conclusiones")
    p.space(0.5)
    p.para("La Unidad 1 establece los fundamentos esenciales para comprender el desarrollo "
           "de aplicaciones web modernas. Los puntos clave son:")
    p.space(0.5)
    p.numbered(1, "La evoluci\u00f3n de Internet y la WWW demuestra c\u00f3mo las tecnolog\u00edas web "
                  "han pasado de ser simples sistemas de hipertexto a plataformas complejas "
                  "de aplicaciones interactivas.")
    p.numbered(2, "La arquitectura Cliente/Servidor sigue siendo el modelo dominante en la web, "
                  "donde el navegador y el servidor interact\u00faan mediante protocolos bien definidos.")
    p.numbered(3, "El conocimiento de TCP/IP y HTTP es fundamental para entender c\u00f3mo viajan "
                  "los datos en la red y c\u00f3mo se comunican las aplicaciones web.")
    p.numbered(4, "Los est\u00e1ndares web garantizan la interoperabilidad y accesibilidad, siendo "
                  "responsabilidad del desarrollador seguirlos para crear aplicaciones compatibles.")
    p.numbered(5, "Los entornos de desarrollo modernos proporcionan un ecosistema rico de "
                  "herramientas que facilitan la productividad, desde editores inteligentes "
                  "hasta pipelines de despliegue automatizado.")
    p.space(1)
    p.para("Estos conceptos constituyen la base sobre la cual se construyen las competencias "
           "necesarias para el desarrollo profesional de aplicaciones web, y su comprensi\u00f3n "
           "permite tomar decisiones informadas sobre tecnolog\u00edas y arquitecturas en proyectos reales.")
    pdf._make_page(p.get_lines())

    # Build final PDF
    pdf.build("Resumen_Unidad1_TorresCasas.pdf")


if __name__ == "__main__":
    create_document()

import uuid
from pathlib import Path
from pypdf import PdfReader
from docx import Document


def _leer_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _leer_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _leer_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def leer_archivo(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _leer_pdf(path)
    if ext in (".docx", ".doc"):
        return _leer_docx(path)
    if ext == ".txt":
        return _leer_txt(path)
    raise ValueError(f"Formato no soportado: {ext}")


def chunkear(texto: str, tam: int = 500, solapamiento: int = 50) -> list[str]:
    """
    Divide el texto en fragmentos de `tam` caracteres
    con `solapamiento` caracteres de contexto compartido entre chunks.
    """
    chunks = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + tam
        chunks.append(texto[inicio:fin].strip())
        inicio += tam - solapamiento
    return [c for c in chunks if c]


def chunkear_archivo(
    path: Path,
    tam: int = 500,
    solapamiento: int = 50,
    nombre_original: str = "",
    proyecto: str = "",
    tags: list[str] | None = None,
) -> list[dict]:
    texto = leer_archivo(path)
    fragmentos = chunkear(texto, tam, solapamiento)
    fuente = nombre_original or path.name
    return [
        {
            "id": str(uuid.uuid4()),
            "texto": fragmento,
            "metadata": {
                "fuente": fuente,
                "tipo": "archivo",
                "proyecto": proyecto,
                "tags": tags or [],
            },
        }
        for fragmento in fragmentos
    ]


def chunkear_texto_web(
    texto: str,
    url: str,
    tam: int = 500,
    solapamiento: int = 50,
    proyecto: str = "",
    tags: list[str] | None = None,
) -> list[dict]:
    fragmentos = chunkear(texto, tam, solapamiento)
    return [
        {
            "id": str(uuid.uuid4()),
            "texto": fragmento,
            "metadata": {
                "fuente": url,
                "tipo": "web",
                "proyecto": proyecto,
                "tags": tags or [],
            },
        }
        for fragmento in fragmentos
    ]

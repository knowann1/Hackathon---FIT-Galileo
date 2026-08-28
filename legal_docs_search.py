"""
============================================================
BÚSQUEDA EN DOCUMENTOS LEGALES (PDF)
============================================================

Este módulo indexa un pequeño set de PDFs de referencia legal
(fundamentos legales para emprendedores, formalización laboral)
y expone una función de búsqueda por palabras clave para que
NexoAI pueda citarlos cuando el usuario pregunte sobre temas
relacionados, sin necesidad de prompts fijos por tema.

Cómo funciona:

1. Al arrancar el proceso (primera llamada), se leen los PDFs
   desde disco y se extrae su texto con pypdf.
2. El texto se trocea en "chunks" (por párrafo, con un tamaño
   máximo). Cada chunk guarda de qué documento y página viene.
3. Cuando llega una pregunta del usuario, se calcula un score
   simple de coincidencia de palabras entre la pregunta y cada
   chunk (sin embeddings, sin librerías externas).
4. Se devuelven los chunks con mejor score (si superan un
   umbral mínimo) para que se inyecten como contexto adicional
   en el prompt de la IA.

El indexado se hace una sola vez y se cachea en memoria
mientras el proceso esté corriendo (variable de módulo).
Si el PDF cambia, hay que reiniciar el proceso para que se
vuelva a indexar (o llamar reset_legal_docs_cache()).
"""

import os
import re
import unicodedata

from pypdf import PdfReader


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Carpeta donde viven los PDFs dentro del repo. Ajusta esta
# ruta si tu carpeta tiene otro nombre o está en otro nivel.
LEGAL_DOCS_DIR = os.getenv(
    "LEGAL_DOCS_DIR",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "legal_docs"
    )
)

# Nombre de archivo -> etiqueta legible que se le mostrará
# a la IA (y opcionalmente al usuario) como fuente.
LEGAL_DOCS_FILES = {
    "fundamentos-legales-para-emprendedores-en-guatemala.pdf":
        "Fundamentos legales para emprendedores en Guatemala",
    "Guia para la Formalizacion Laboral-5.pdf":
        "Guía para la Formalización Laboral",
}

# Tamaño máximo aproximado (en caracteres) de cada chunk.
CHUNK_MAX_CHARS = 900

# Cuántos chunks como máximo se devuelven por búsqueda.
DEFAULT_TOP_K = 4

# Score mínimo para considerar que un chunk es relevante.
# Si nada supera esto, no se inyecta nada (evita ruido).
MIN_SCORE_THRESHOLD = 1

# Palabras demasiado comunes en español como para aportar
# señal en el matching (se ignoran al puntuar).
STOPWORDS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del",
    "se", "las", "por", "un", "para", "con", "no", "una",
    "su", "al", "lo", "como", "mas", "o", "pero", "sus",
    "le", "ya", "este", "si", "porque", "esta", "entre",
    "cuando", "muy", "sin", "sobre", "tambien", "me", "hasta",
    "donde", "quien", "desde", "todo", "nos", "durante",
    "todos", "uno", "les", "ni", "contra", "otros", "ese",
    "eso", "ante", "ellos", "e", "esto", "mi", "antes",
    "algunos", "que", "unos", "yo", "otro", "otras", "otra",
    "el", "tanto", "esa", "estos", "mucho", "quienes", "nada",
    "muchos", "cual", "poco", "ella", "estar", "estas",
    "algunas", "algo", "nosotros", "es", "son", "soy", "eres",
    "puedo", "puede", "quiero", "quisiera", "necesito", "hola",
    "gracias", "por favor",
}


# ============================================================
# ESTADO EN MEMORIA (CACHÉ DE ÍNDICE)
# ============================================================

_INDEX_CACHE = None  # lista de chunks indexados, o None si aún no se construyó
_INDEX_ERRORS = []   # errores de lectura (archivo faltante, etc.), para debug


# ============================================================
# UTILIDADES DE TEXTO
# ============================================================

def _normalize(text: str) -> str:
    """
    Baja a minúsculas y quita acentos, para que el matching
    de palabras clave no falle por 'formalización' vs
    'formalizacion'.
    """

    if not text:
        return ""

    text = text.lower()

    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )

    return text


def _tokenize(text: str):

    normalized = _normalize(text)

    words = re.findall(r"[a-z0-9]+", normalized)

    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def _split_into_chunks(page_text: str, max_chars: int):
    """
    Trocea el texto de una página en chunks por párrafo,
    agrupando párrafos cortos consecutivos hasta acercarse
    a max_chars, y partiendo los párrafos larguísimos.
    """

    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", page_text)
        if p.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:

        # Párrafo individual ya es más largo que el límite:
        # se parte solo, en trozos de max_chars.
        if len(paragraph) > max_chars:

            if current:
                chunks.append(current.strip())
                current = ""

            for i in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[i:i + max_chars].strip())

            continue

        if len(current) + len(paragraph) + 1 <= max_chars:
            current = (current + "\n" + paragraph).strip()
        else:
            if current:
                chunks.append(current.strip())
            current = paragraph

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]


# ============================================================
# INDEXADO DE LOS PDFs
# ============================================================

def _build_index():
    """
    Lee todos los PDFs configurados en LEGAL_DOCS_FILES desde
    LEGAL_DOCS_DIR, extrae su texto página por página, y arma
    una lista de chunks indexados en memoria.

    Cada chunk es un dict:
        {
            "doc_label": "Guía para la Formalización Laboral",
            "filename": "Guia para la Formalizacion Laboral-5.pdf",
            "page": 3,
            "text": "...",
            "tokens": {"formalizacion", "patronal", ...}  # set
        }

    Si un archivo no existe o no se puede leer, se registra el
    error en _INDEX_ERRORS pero no se interrumpe el resto del
    indexado (el otro PDF puede seguir funcionando).
    """

    global _INDEX_ERRORS

    _INDEX_ERRORS = []
    index = []

    if not os.path.isdir(LEGAL_DOCS_DIR):

        _INDEX_ERRORS.append(
            f"No existe la carpeta de documentos legales: "
            f"{LEGAL_DOCS_DIR}"
        )

        return index

    for filename, doc_label in LEGAL_DOCS_FILES.items():

        file_path = os.path.join(LEGAL_DOCS_DIR, filename)

        if not os.path.isfile(file_path):

            _INDEX_ERRORS.append(
                f"No se encontró el archivo: {file_path}"
            )

            continue

        try:

            reader = PdfReader(file_path)

            for page_number, page in enumerate(reader.pages, start=1):

                try:
                    page_text = page.extract_text() or ""
                except Exception as e:

                    _INDEX_ERRORS.append(
                        f"Error extrayendo texto de "
                        f"{filename} página {page_number}: "
                        f"{type(e).__name__}: {e}"
                    )

                    continue

                if not page_text.strip():
                    continue

                for chunk_text in _split_into_chunks(
                    page_text,
                    CHUNK_MAX_CHARS
                ):

                    index.append({
                        "doc_label": doc_label,
                        "filename": filename,
                        "page": page_number,
                        "text": chunk_text,
                        "tokens": set(_tokenize(chunk_text)),
                    })

        except Exception as e:

            _INDEX_ERRORS.append(
                f"Error abriendo {filename}: "
                f"{type(e).__name__}: {e}"
            )

    return index


def _get_index():
    """
    Devuelve el índice cacheado, construyéndolo la primera vez
    que se necesita (lazy loading).
    """

    global _INDEX_CACHE

    if _INDEX_CACHE is None:
        _INDEX_CACHE = _build_index()

    return _INDEX_CACHE


def reset_legal_docs_cache():
    """
    Fuerza a que el índice se reconstruya en la próxima
    búsqueda. Útil si reemplazas los PDFs sin reiniciar el
    proceso (por ejemplo, en un entorno con hot-reload).
    """

    global _INDEX_CACHE

    _INDEX_CACHE = None


def get_index_status():
    """
    Info de diagnóstico: cuántos chunks se indexaron por
    documento y qué errores hubo. Útil para un endpoint de
    salud o para debug manual, no es necesario llamarlo en
    el flujo normal del chat.
    """

    index = _get_index()

    counts = {}

    for chunk in index:
        counts[chunk["doc_label"]] = counts.get(chunk["doc_label"], 0) + 1

    return {
        "total_chunks": len(index),
        "chunks_by_document": counts,
        "errors": list(_INDEX_ERRORS),
        "legal_docs_dir": LEGAL_DOCS_DIR,
    }


# ============================================================
# BÚSQUEDA POR PALABRAS CLAVE
# ============================================================

def _score_chunk(query_tokens: set, chunk_tokens: set) -> int:
    """
    Score simple: cantidad de palabras clave de la pregunta
    que aparecen en el chunk. No pondera por frecuencia ni
    posición — es intencionalmente simple.
    """

    return len(query_tokens & chunk_tokens)


def search_legal_docs(query: str, top_k: int = DEFAULT_TOP_K):
    """
    Busca en el índice los chunks más relevantes para `query`.

    Devuelve una lista (posiblemente vacía) de dicts:
        {
            "doc_label": str,
            "page": int,
            "text": str,
            "score": int,
        }

    ordenada de mayor a menor score. Si ningún chunk supera
    MIN_SCORE_THRESHOLD, devuelve lista vacía — es la señal de
    "esto no es un tema legal/laboral, no inyectes nada".
    """

    if not query or not query.strip():
        return []

    query_tokens = set(_tokenize(query))

    if not query_tokens:
        return []

    index = _get_index()

    if not index:
        return []

    scored = []

    for chunk in index:

        score = _score_chunk(query_tokens, chunk["tokens"])

        if score >= MIN_SCORE_THRESHOLD:

            scored.append({
                "doc_label": chunk["doc_label"],
                "page": chunk["page"],
                "text": chunk["text"],
                "score": score,
            })

    scored.sort(key=lambda c: c["score"], reverse=True)

    return scored[:top_k]


def build_legal_context_block(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    """
    Conveniencia: llama a search_legal_docs y arma directamente
    el bloque de texto listo para insertar en el prompt de la
    IA, con las citas de documento y página. Si no hay
    resultados relevantes, devuelve string vacío (para que el
    prompt simplemente no incluya la sección).
    """

    results = search_legal_docs(query, top_k=top_k)

    if not results:
        return ""

    parts = []

    for r in results:

        parts.append(
            f"[Fuente: {r['doc_label']}, página {r['page']}]\n"
            f"{r['text']}"
        )

    return "\n\n---\n\n".join(parts)

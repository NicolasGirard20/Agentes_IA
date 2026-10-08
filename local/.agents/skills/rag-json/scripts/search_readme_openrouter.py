import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from collections import Counter
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models


def load_dotenv(path: Path = Path(__file__).with_name(".env")) -> None:
    """Carga variables simples KEY=VALUE del archivo .env si existe."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        if key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


load_dotenv()

# Configuraciones por defecto
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_EMBED_MODEL = "openai/text-embedding-3-small"
DEFAULT_EMBED_BATCH = 64
OPENROUTER_TIMEOUT = 60.0
OPENROUTER_MAX_RETRIES = 3
OPENROUTER_TITLE = "project-map-search"
OPENROUTER_REFERER = os.environ.get("OPENROUTER_REFERER", "http://localhost")

DENSE_FLOOR = 0.25
W_DENSE = 0.40
W_LEXICAL = 0.40
W_BOOST = 0.20

# Filtros universales por defecto (agnósticos al proyecto)
DEFAULT_SKIP_PREFIXES = (
    ".git/",
    "node_modules/",
    "venv/",
    ".venv/",
    "__pycache__/",
    ".next/",
    "dist/",
    "build/",
    "coverage/",
    ".idea/",
    ".vscode/",
)

DEFAULT_SKIP_EXTENSIONS = (
    ".docx", ".xlsx", ".xls", ".pdf", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".ico", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf",
    ".eot", ".mp4", ".webm", ".lock", ".min.js", ".min.css", ".map",
)

DEFAULT_SKIP_BASENAMES = {
    ".gitignore", ".ds_store", "thumbs.db", ".env", ".env.local",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock"
}

# Stopwords estándar de desarrollo y búsqueda (español e inglés)
STOPWORDS = {
    "que", "cual", "cuales", "como", "donde", "quien", "quienes", "cuando",
    "los", "las", "del", "por", "para", "con", "una", "uno", "unos", "unas",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel",
    "son", "ser", "estan", "hay", "mas", "muy", "todo", "todos", "toda",
    "todas", "tambien", "pero", "sin", "sobre", "entre", "desde", "hasta",
    "cuanto", "cuantos", "me", "te", "se", "lo", "la", "el", "un", "al", "e",
    "y", "o", "u", "a", "de", "en", "es", "su", "sus", "mi",
    "the", "and", "for", "with", "this", "that", "from", "are", "was",
    "how", "what", "where", "who", "which", "when", "why", "not", "you",
    "your", "our", "has", "have", "had", "can", "will", "would", "should",
    "dime", "dame", "muestra", "muestro", "haz", "hacer", "necesito",
    "quiero", "podrias", "puede", "deberia", "existe", "existen", "tiene",
}

GENERIC_WORDS = {
    "get", "set", "new", "use", "add", "del", "delete", "remove", "create",
    "update", "list", "find", "load", "save", "fetch", "make", "build", "edit",
    "show", "hide", "open", "close", "init", "render", "handle", "check",
    "calc", "process", "run", "start", "main", "data", "validar", "obtener",
}

# Sinónimos técnicos universales de desarrollo de software
TECH_SYNONYMS = {
    "auth": ["autenticacion", "authentication", "login", "sesion", "session", "jwt", "token", "password", "clave"],
    "autenticacion": ["auth", "login", "sesion", "session", "jwt", "token"],
    "sesion": ["session", "auth"],
    "session": ["sesion", "auth"],
    "usuario": ["user", "account", "profile"],
    "user": ["usuario", "account", "profile"],
    "db": ["database", "base_datos", "sql", "prisma", "schema", "model", "modelo"],
    "database": ["db", "sql", "prisma", "schema"],
    "config": ["configuration", "settings", "ajustes", "env", "options"],
    "configuracion": ["config", "settings", "options"],
    "test": ["prueba", "spec", "testing"],
    "prueba": ["test", "spec"],
    "ruta": ["route", "path", "endpoint", "url", "api"],
    "route": ["ruta", "endpoint", "path", "api"],
    "api": ["endpoint", "route", "handler", "controller"],
    "servicio": ["service"],
    "service": ["servicio"],
    "controlador": ["controller", "handler"],
    "controller": ["controlador", "handler"],
    "cliente": ["client"],
    "servidor": ["server"],
    "error": ["exception", "fallo", "err"],
    "log": ["registro", "logger", "historial"],
    "doc": ["documentacion", "readme", "guide"],
}

CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
NON_ALNUM = re.compile(r"[^\w]+")


def _safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip("_")
    return slug or "project"


def _get_file_hash(filepath: str) -> str:
    return hashlib.sha256(Path(filepath).read_bytes()).hexdigest()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def _stem(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("es"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s"):
        return tok[:-1]
    return tok


def tokenize(text: str, stems: bool = True) -> list[str]:
    if not text:
        return []
    clean = normalize_text(text)
    spaced = CAMEL_BOUNDARY.sub(" ", clean)
    words = NON_ALNUM.sub(" ", spaced).split()
    tokens = []
    for w in words:
        if len(w) <= 1 or w in STOPWORDS:
            continue
        tokens.append(w)
        if stems:
            st = _stem(w)
            if st != w and len(st) > 2 and st not in STOPWORDS:
                tokens.append(st)
    return tokens


def expand_query_tokens(tokens: list[str], custom_synonyms: dict[str, list[str]] | None = None) -> list[str]:
    out = list(tokens)
    synonyms_map = dict(TECH_SYNONYMS)
    if custom_synonyms:
        synonyms_map.update(custom_synonyms)

    for tok in tokens:
        for syn in synonyms_map.get(tok, []):
            out.append(syn)
            # Buscar también por stem
            st = _stem(syn)
            if st != syn:
                out.append(st)
    return list(dict.fromkeys(out))


def token_index(token: str) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % 1_000_000 + 1


def is_junk_path(path: str, extra_skip_prefixes: tuple[str, ...] = ()) -> bool:
    p = path.replace("\\", "/").strip().lower()
    name = Path(p).name
    if name in DEFAULT_SKIP_BASENAMES:
        return True
    all_prefixes = DEFAULT_SKIP_PREFIXES + extra_skip_prefixes
    if any(p.startswith(pref) or f"/{pref}" in f"/{p}" for pref in all_prefixes):
        return True
    return any(p.endswith(ext) for ext in DEFAULT_SKIP_EXTENSIONS)


def extract_symbols(entry: dict) -> list[str]:
    """Extrae nombres de funciones, clases y exportaciones tolerando formato string u objeto."""
    names = []
    for item in entry.get("functions", []):
        name = item.get("name") if isinstance(item, dict) else item
        if name and isinstance(name, str):
            names.append(name.strip())
    for item in entry.get("classes", []):
        name = item.get("name") if isinstance(item, dict) else item
        if name and isinstance(name, str):
            names.append(name.strip())
    for item in entry.get("exports", []):
        name = item.get("name") if isinstance(item, dict) else item
        if name and isinstance(name, str):
            names.append(name.strip())
    return [n for n in names if n]


def flatten_file_entry(file_entry: dict, dependents: list[str] | None = None) -> str:
    """Convierte una entrada de archivo en un texto estructurado y rico para embeddings."""
    path = file_entry.get("path", "")
    summary = file_entry.get("summary", "Sin resumen")
    language = file_entry.get("language", "desconocido")
    symbols = extract_symbols(file_entry)
    imports = file_entry.get("imports", [])
    complexity = file_entry.get("complexity", "")

    parts = [
        f"Archivo: {path}",
        f"Nombre: {Path(path).stem}",
        f"Lenguaje: {language}",
        f"Resumen: {summary}",
    ]
    if symbols:
        parts.append(f"Símbolos (funciones/clases/exports): {', '.join(symbols)}")
    if imports:
        parts.append(f"Importaciones: {', '.join(imports)}")
    if dependents:
        parts.append(f"Utilizado por: {', '.join(dependents[:10])}")
    if complexity:
        parts.append(f"Complejidad: {complexity}")

    return "\n".join(parts)


def build_meta_docs(data: dict) -> list[dict]:
    """Genera documentos de contexto meta sobre la arquitectura general del proyecto de forma dinámica."""
    docs = []
    project = data.get("project_name", "Proyecto")
    arch = data.get("architecture", {}) or {}

    # Generación dinámica para cualquier categoría de arquitectura existente en el mapa
    for category_name, items in arch.items():
        if not items or not isinstance(items, list):
            continue
        readable_title = category_name.replace("_", " ").title()
        if category_name == "all_directories":
            summary = f"Directorios principales del proyecto {project}: {', '.join(items[:20])}"
        else:
            summary = f"Componentes de {readable_title} en {project}: {', '.join(items)}"

        docs.append({
            "path": f"[arquitectura] {readable_title}",
            "language": "meta",
            "size_lines": len(items),
            "summary": summary,
            "imports": [],
            "exports": [],
            "classes": [],
            "functions": items if all(isinstance(x, str) for x in items) else [],
            "complexity": "low",
        })

    # Resumen global del proyecto
    docs.append({
        "path": f"[proyecto] {project}",
        "language": "meta",
        "size_lines": data.get("total_files", 0),
        "summary": (
            f"Visión general del proyecto {project}: {data.get('total_files', '?')} archivos, "
            f"{data.get('total_symbols', '?')} símbolos analizados."
        ),
        "imports": [],
        "exports": [],
        "classes": [],
        "functions": [project],
        "complexity": "low",
    })
    return docs


def compute_idf(docs_tokens: list[list[str]]) -> dict[str, float]:
    n_docs = len(docs_tokens)
    if n_docs == 0:
        return {}
    df = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    return {t: math.log(max(1.0, n_docs) / max(1.0, n)) for t, n in df.items()}


def sparse_from_fields(fields: dict[str, list[str]], idf: dict[str, float]) -> models.SparseVector:
    tf = Counter()
    weights = {"symbols": 4, "path": 3, "summary": 2, "imports": 1, "dependents": 1}
    for name, toks in fields.items():
        w = weights.get(name, 1)
        for tok in toks:
            tf[tok] += w

    indices = []
    values = []
    for tok, freq in tf.items():
        weight = idf.get(tok, 1.0)
        effective = freq if freq <= 1.0 else 1.0 + math.log(freq)
        indices.append(token_index(tok))
        values.append(effective * weight)

    if not indices:
        return models.SparseVector(indices=[0], values=[0.0])
    return models.SparseVector(indices=indices, values=values)


def _openrouter_post(payload: dict, headers: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(OPENROUTER_MAX_RETRIES):
        request = urllib.request.Request(OPENROUTER_EMBED_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=OPENROUTER_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            last_err = RuntimeError(f"OpenRouter HTTP {exc.code}: {detail}")
            if exc.code in {429, 500, 502, 503, 529} and attempt < OPENROUTER_MAX_RETRIES - 1:
                time.sleep(2.0 ** attempt)
                continue
            raise last_err from exc
        except urllib.error.URLError as exc:
            last_err = RuntimeError(f"Error conectando a OpenRouter: {exc.reason}")
            if attempt < OPENROUTER_MAX_RETRIES - 1:
                time.sleep(2.0 ** attempt)
                continue
            raise last_err from exc
    raise last_err or RuntimeError("Fallo desconocido al contactar OpenRouter.")


def embed_texts(
    texts: list[str],
    model: str = DEFAULT_EMBED_MODEL,
    api_key: str = "",
    batch_size: int = DEFAULT_EMBED_BATCH,
) -> list[np.ndarray]:
    if not texts:
        return []
    if not api_key:
        raise RuntimeError("Falta OPENROUTER_API_KEY (variable de entorno o --api-key).")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_REFERER,
        "X-Title": OPENROUTER_TITLE,
    }
    vectors: list[np.ndarray] = []
    batch_size = max(1, batch_size)
    total_batches = math.ceil(len(texts) / batch_size)

    for batch_num, start in enumerate(range(0, len(texts), batch_size), start=1):
        batch = texts[start:start + batch_size]
        if total_batches > 1:
            print(f"Embeddings ({batch_num}/{total_batches}): {len(batch)} textos...", file=sys.stderr)
        data = _openrouter_post({"model": model, "input": batch, "encoding_format": "float"}, headers)
        items = data.get("data") or []
        for item in sorted(items, key=lambda d: d.get("index", 0)):
            vec = np.asarray(item["embedding"], dtype=np.float32)
            norm = float(np.linalg.norm(vec))
            vectors.append(vec / norm if norm > 0.0 else vec)
    return vectors


class ProjectMapEngine:
    def __init__(
        self,
        map_path: str = "project_map.json",
        collection: str | None = None,
        host: str = "localhost",
        port: int = 6333,
        embed_model: str = DEFAULT_EMBED_MODEL,
        embed_batch: int = DEFAULT_EMBED_BATCH,
        api_key: str | None = None,
        extra_skip_prefixes: tuple[str, ...] = (),
    ):
        self.map_path = map_path
        self.host = host
        self.port = port
        self.embed_model = embed_model
        self.embed_batch = embed_batch
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.extra_skip_prefixes = extra_skip_prefixes
        self.client = QdrantClient(host=self.host, port=self.port)

        self.data = self._load_data(map_path)
        self.project_name = self.data.get("project_name", "proyecto")
        self.collection_name = collection or f"pm_{_safe_slug(self.project_name)}"
        self.custom_synonyms = self.data.get("metadata", {}).get("synonyms", {})

    def _load_data(self, path_str: str) -> dict:
        p = Path(path_str)
        if not p.exists():
            raise FileNotFoundError(f"No se encontró '{path_str}'.")
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido en '{path_str}': {exc}") from exc

    def _state_file_path(self) -> Path:
        cache_dir = Path.home() / ".cache" / "project_map_search"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"state_{self.collection_name}.json"

    def index(self, force: bool = False, skip_junk: bool = True) -> None:
        file_hash = _get_file_hash(self.map_path)
        state_file = self._state_file_path()
        state = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        collection_exists = self.client.collection_exists(self.collection_name)
        if not force and collection_exists and state.get("map_hash") == file_hash and state.get("model") == self.embed_model:
            print(f"Colección '{self.collection_name}' al día (sin cambios en {self.map_path}).", file=sys.stderr)
            return

        files = self.data.get("files", [])
        dep_graph = self.data.get("dependency_graph", {}) or {}
        dependents_map: dict[str, list[str]] = {}
        for src, targets in dep_graph.items():
            for tgt in targets:
                dependents_map.setdefault(tgt, []).append(src)

        selected = []
        for entry in files:
            path = entry.get("path", "")
            if skip_junk and is_junk_path(path, self.extra_skip_prefixes):
                continue
            selected.append(entry)

        selected.extend(build_meta_docs(self.data))
        if not selected:
            print("No hay documentos para indexar.", file=sys.stderr)
            return

        print(
            f"Indexando proyecto '{self.project_name}' en colección '{self.collection_name}' "
            f"({len(selected)} documentos)...",
            file=sys.stderr,
        )

        texts = []
        fields_list = []
        for entry in selected:
            path = entry.get("path", "")
            deps = sorted(dependents_map.get(path, []))
            texts.append(flatten_file_entry(entry, deps))
            fields_list.append({
                "path": tokenize(path),
                "symbols": tokenize(" ".join(extract_symbols(entry))),
                "summary": tokenize(entry.get("summary", "")),
                "imports": tokenize(" ".join(entry.get("imports", []))),
                "dependents": tokenize(" ".join(deps)),
            })

        all_doc_tokens = [sorted(set(sum(f.values(), []))) for f in fields_list]
        idf = compute_idf(all_doc_tokens)

        vectors = embed_texts(texts, model=self.embed_model, api_key=self.api_key, batch_size=self.embed_batch)
        dim = int(len(vectors[0]))

        if collection_exists:
            self.client.delete_collection(self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={"dense": models.VectorParams(size=dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={"sparse": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False))},
        )

        points = []
        for entry, fields, vec in zip(selected, fields_list, vectors):
            path = entry.get("path", "")
            deps = sorted(dependents_map.get(path, []))
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.project_name}:{path}"))
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": vec.tolist(),
                        "sparse": sparse_from_fields(fields, idf),
                    },
                    payload={
                        "project": self.project_name,
                        "file": path,
                        "language": entry.get("language", "unknown"),
                        "summary": entry.get("summary", ""),
                        "imports": entry.get("imports", []),
                        "exports": [x.get("name") if isinstance(x, dict) else x for x in entry.get("exports", [])],
                        "functions": [x.get("name") if isinstance(x, dict) else x for x in entry.get("functions", [])],
                        "classes": [x.get("name") if isinstance(x, dict) else x for x in entry.get("classes", [])],
                        "complexity": entry.get("complexity", ""),
                        "size_lines": entry.get("size_lines", 0),
                        "dependents": deps,
                    },
                )
            )

        for i in range(0, len(points), 64):
            self.client.upsert(collection_name=self.collection_name, points=points[i:i + 64], wait=True)

        state_file.write_text(
            json.dumps({
                "map_hash": file_hash,
                "model": self.embed_model,
                "project": self.project_name,
                "points": len(points),
            }, indent=2),
            encoding="utf-8",
        )
        print(f"Indexación completada: {len(points)} puntos guardados en '{self.collection_name}'.", file=sys.stderr)

    def _query_idf(self) -> dict[str, float]:
        docs = []
        for entry in self.data.get("files", []):
            path = entry.get("path", "")
            if is_junk_path(path, self.extra_skip_prefixes):
                continue
            text = f"{path} {entry.get('summary', '')} {' '.join(extract_symbols(entry))}"
            docs.append(tokenize(text))
        return compute_idf(docs)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.2) -> list[dict]:
        query = query.strip()
        if not query:
            return []

        if not self.client.collection_exists(self.collection_name):
            print(f"Colección '{self.collection_name}' no existe. Indexando...", file=sys.stderr)
            self.index(force=True)

        primary_tokens = tokenize(query, stems=False)
        primary_set = set(primary_tokens) | {_stem(t) for t in primary_tokens}
        query_tokens = expand_query_tokens(tokenize(query), self.custom_synonyms)

        idf = self._query_idf()
        query_tf = Counter()
        for tok in query_tokens:
            query_tf[tok] += 1.0 if tok in primary_set else 0.55
        query_sparse = sparse_from_fields({"q": query_tokens}, idf)

        query_dense = embed_texts([query], model=self.embed_model, api_key=self.api_key, batch_size=1)[0]

        limit = max(top_k * 5, 20)
        res = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(query=query_dense.tolist(), using="dense", limit=limit),
                models.Prefetch(query=query_sparse, using="sparse", limit=limit),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
            with_vectors=["dense"],
        )

        results = []
        for pt in res.points:
            payload = pt.payload or {}
            dense_vec = np.asarray(pt.vector["dense"], dtype=np.float32)
            cosine = float(np.dot(dense_vec, query_dense))
            dense_norm = max(0.0, min(1.0, (cosine - DENSE_FLOOR) / (1.0 - DENSE_FLOOR)))

            # Puntuación léxica
            doc_symbols = tokenize(" ".join(payload.get("functions", []) + payload.get("classes", []) + payload.get("exports", [])))
            doc_path = tokenize(payload.get("file", ""))
            doc_summary = tokenize(payload.get("summary", ""))

            lex_score = 0.0
            matched = []
            for tok in query_tokens:
                w = 1.0 if tok in primary_set else 0.5
                if tok in doc_symbols:
                    lex_score += 3.5 * w
                    matched.append(tok)
                elif tok in doc_path:
                    lex_score += 3.0 * w
                    matched.append(tok)
                elif tok in doc_summary:
                    lex_score += 1.5 * w
                    matched.append(tok)

            lex_norm = min(1.0, lex_score / (max(1, len(primary_tokens)) * 3.5))

            # Boost exacto para nombres de archivos y símbolos
            boost = 0.0
            boost_hits = []
            file_name = Path(payload.get("file", "")).stem.lower()
            if any(t.lower() == file_name for t in primary_tokens):
                boost = 0.8
                boost_hits.append(f"archivo {file_name}")
            else:
                for fn in payload.get("functions", []):
                    if isinstance(fn, str) and any(t.lower() == fn.lower() for t in primary_tokens):
                        boost = max(boost, 0.7)
                        boost_hits.append(f"función {fn}")
                        break

            final = W_DENSE * dense_norm + W_LEXICAL * lex_norm + W_BOOST * boost
            results.append({
                "file": payload.get("file"),
                "score": round(final, 4),
                "dense": round(cosine, 4),
                "lexical": round(lex_norm, 4),
                "boost": round(boost, 4),
                "summary": payload.get("summary", ""),
                "language": payload.get("language", ""),
                "functions": payload.get("functions", []),
                "classes": payload.get("classes", []),
                "exports": payload.get("exports", []),
                "imports": payload.get("imports", []),
                "dependents": payload.get("dependents", []),
                "matched_tokens": sorted(set(matched)),
                "matched_symbols": boost_hits,
            })

        results.sort(key=lambda r: (r["score"], r["dense"]), reverse=True)
        return [r for r in results if r["score"] >= min_score][:top_k]


def format_rag_context(results: list[dict], project_name: str) -> str:
    """Genera contexto Markdown compacto y de alta densidad para inyectar en prompts de LLM."""
    if not results:
        return f"No se encontró contexto relevante para el proyecto '{project_name}'."

    lines = [f"### Contexto Relevante del Proyecto: {project_name}\n"]
    for i, r in enumerate(results, start=1):
        lines.append(f"#### [{i}] `{r['file']}` (Score: {r['score']})")
        lines.append(f"- **Resumen**: {r['summary']}")
        if r.get("language") and r["language"] != "meta":
            lines.append(f"- **Lenguaje**: {r['language']}")
        if r.get("functions"):
            lines.append(f"- **Funciones**: {', '.join(str(f) for f in r['functions'][:8])}")
        if r.get("classes"):
            lines.append(f"- **Clases**: {', '.join(str(c) for c in r['classes'][:6])}")
        if r.get("exports"):
            lines.append(f"- **Exporta**: {', '.join(str(e) for e in r['exports'][:6])}")
        if r.get("dependents"):
            lines.append(f"- **Usado por**: {', '.join(str(d) for d in r['dependents'][:4])}")
        lines.append("")
    return "\n".join(lines).strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Búsqueda semántica híbrida (denso + sparse) y RAG sobre cualquier project_map.json con Qdrant."
    )
    parser.add_argument("query", nargs="*", help="Consulta en lenguaje natural")
    parser.add_argument("--top-k", type=int, default=5, help="Cantidad de resultados (def: 5)")
    parser.add_argument("--min-score", type=float, default=0.2, help="Umbral mínimo de score combinado (def: 0.2)")
    parser.add_argument("--map", dest="map_path", default="project_map.json", help="Ruta al archivo project_map.json")
    parser.add_argument("--collection", default=None, help="Nombre de colección (def: derivado de project_name)")
    parser.add_argument("--reindex", action="store_true", help="Fuerza la reindexación")
    parser.add_argument("--include-all", action="store_true", help="Incluye archivos filtrados por ruido")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--rag", action="store_true", help="Salida formateada en Markdown para contexto de LLM")
    parser.add_argument("--interactive", "-i", action="store_true", help="Modo interactivo")
    parser.add_argument("--host", default="localhost", help="Host de Qdrant (def: localhost)")
    parser.add_argument("--port", type=int, default=6333, help="Puerto de Qdrant (def: 6333)")
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL, help=f"Modelo de OpenRouter (def: {DEFAULT_EMBED_MODEL})")
    parser.add_argument("--embed-batch", type=int, default=DEFAULT_EMBED_BATCH, help="Batch size de embeddings (def: 64)")
    parser.add_argument("--api-key", default=None, help="API key de OpenRouter")
    parser.add_argument("--skip-prefix", action="append", default=[], help="Prefijos adicionales a ignorar (repetible)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: Falta OPENROUTER_API_KEY. Configurala en .env o pasá --api-key.", file=sys.stderr)
        return 2

    try:
        engine = ProjectMapEngine(
            map_path=args.map_path,
            collection=args.collection,
            host=args.host,
            port=args.port,
            embed_model=args.embed_model,
            embed_batch=args.embed_batch,
            api_key=api_key,
            extra_skip_prefixes=tuple(args.skip_prefix),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Asegurar indexación
    try:
        engine.index(force=args.reindex, skip_junk=not args.include_all)
    except Exception as exc:
        print(f"ERROR indexando: {exc}", file=sys.stderr)
        return 1

    def run_query(q: str):
        results = engine.search(q, top_k=args.top_k, min_score=args.min_score)
        if args.json:
            print(json.dumps({"query": q, "project": engine.project_name, "results": results}, ensure_ascii=False, indent=2))
        elif args.rag:
            print(format_rag_context(results, engine.project_name))
        else:
            print(f'\nConsulta: "{q}" (Proyecto: {engine.project_name})')
            print("=" * 72)
            if not results:
                print("No se encontraron resultados relevantes.")
                print("=" * 72)
                return
            for i, r in enumerate(results, start=1):
                print(f"[{i}] Score: {r['score']:.4f} | Archivo: {r['file']}")
                print(f"    (denso: {r['dense']:.4f}, léxico: {r['lexical']:.2f}, boost: {r['boost']:.2f})")
                print(f"  Resumen: {r['summary']}")
                if r["functions"]:
                    print(f"  Funciones: {', '.join(str(f) for f in r['functions'][:6])}")
                if r["classes"]:
                    print(f"  Clases: {', '.join(str(c) for c in r['classes'][:4])}")
                if r["dependents"]:
                    print(f"  Usado por: {', '.join(str(d) for d in r['dependents'][:4])}")
                print("-" * 72)

    query_str = " ".join(args.query).strip()
    if query_str:
        run_query(query_str)
        return 0

    if args.interactive or (not args.query and sys.stdin.isatty()):
        print(f"Búsqueda sobre '{engine.project_name}'. Escribe 'salir' para terminar.")
        while True:
            try:
                user_q = input("\nPregunta: ").strip()
                if not user_q or user_q.lower() in {"salir", "exit", "quit"}:
                    break
                run_query(user_q)
            except (KeyboardInterrupt, EOFError):
                break
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

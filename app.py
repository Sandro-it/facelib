import os
import json
import time
import threading
import sqlite3
from pathlib import Path
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="FaceLib")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

VERSION = "1.1"
GITHUB_REPO = "Sandro-it/facelib"

DB_PATH = "facelib.db"
THUMBS_DIR = Path("static/thumbs")
THUMBS_DIR.mkdir(parents=True, exist_ok=True)

indexer_state = {
    "running": False,
    "total": 0,
    "processed": 0,
    "current_file": "",
    "errors": 0,
    "clustering": False,
}
merge_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.create_function("LOWER", 1, lambda s: s.lower() if isinstance(s, str) else s)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            indexed_at REAL,
            taken_at REAL
        );
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL,
            face_index INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            bbox TEXT,
            person_id INTEGER,
            FOREIGN KEY(photo_id) REFERENCES photos(id),
            FOREIGN KEY(person_id) REFERENCES persons(id)
        );
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            cover_face_id INTEGER,
            created_at REAL DEFAULT (unixepoch())
        );
        CREATE TABLE IF NOT EXISTS scan_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            enabled INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_faces_person ON faces(person_id);
        CREATE INDEX IF NOT EXISTS idx_faces_photo ON faces(photo_id);
        CREATE INDEX IF NOT EXISTS idx_faces_person_photo ON faces(person_id, photo_id);
        CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
        """)
        count = conn.execute("SELECT COUNT(*) FROM scan_folders").fetchone()[0]
        if count == 0:
            conn.execute("INSERT OR IGNORE INTO scan_folders(path, enabled) VALUES(?, 1)", (r"G:\Photo",))

# Ensure indexes exist (for existing databases)
def ensure_indexes():
    with get_db() as conn:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_faces_person_photo ON faces(person_id, photo_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name)")

def ensure_migrations():
    """Safe migrations for existing databases."""
    with get_db() as conn:
        # Add is_favorite and sort_order if not exist
        cols = [r[1] for r in conn.execute("PRAGMA table_info(persons)").fetchall()]
        if 'is_favorite' not in cols:
            conn.execute("ALTER TABLE persons ADD COLUMN is_favorite INTEGER DEFAULT 0")
        if 'sort_order' not in cols:
            conn.execute("ALTER TABLE persons ADD COLUMN sort_order INTEGER DEFAULT 0")

try:
    ensure_indexes()
    ensure_migrations()
except Exception:
    pass

init_db()

# ---------------------------------------------------------------------------
# InsightFace loader
# ---------------------------------------------------------------------------

_face_app = None
_face_lock = threading.Lock()

def get_face_app():
    global _face_app
    if _face_app is None:
        with _face_lock:
            if _face_app is None:
                # Add CUDA dll paths
                import os
                cuda_dirs = [
                    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
                    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\libnvvp",
                ]
                # Also add pip nvidia packages
                base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    ".venv", "Lib", "site-packages", "nvidia")
                for pkg in ["cuda_runtime", "cudnn", "cublas", "cuda_nvrtc"]:
                    for sub in ["bin", os.path.join(pkg, "bin")]:
                        d = os.path.join(base, pkg, sub)
                        if os.path.isdir(d):
                            cuda_dirs.append(d)
                for d in cuda_dirs:
                    if os.path.isdir(d):
                        os.add_dll_directory(d)
                from insightface.app import FaceAnalysis
                fa = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                fa.prepare(ctx_id=0, det_size=(640, 640))
                _face_app = fa
    return _face_app

# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------

def fix_orientation(img):
    """Apply EXIF orientation so vertical photos stay vertical."""
    from PIL import ImageOps
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img

def make_thumb(src_path: str, face_id: int, bbox=None) -> str:
    from PIL import Image
    thumb_name = f"face_{face_id}.jpg"
    thumb_path = THUMBS_DIR / thumb_name
    if thumb_path.exists():
        return f"/static/thumbs/{thumb_name}"
    try:
        img = fix_orientation(Image.open(src_path).convert("RGB"))
        if bbox:
            b = json.loads(bbox)
            x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
            pad = int(max(x2 - x1, y2 - y1) * 0.3)
            x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
            x2 = min(img.width, x2 + pad); y2 = min(img.height, y2 + pad)
            img = img.crop((x1, y1, x2, y2))
        img.thumbnail((200, 200))
        img.save(thumb_path, "JPEG", quality=85)
    except Exception:
        return "/static/placeholder.jpg"
    return f"/static/thumbs/{thumb_name}"

def make_photo_thumb(src_path: str, photo_id: int) -> str:
    from PIL import Image
    thumb_name = f"photo_{photo_id}.jpg"
    thumb_path = THUMBS_DIR / thumb_name
    if thumb_path.exists():
        return f"/static/thumbs/{thumb_name}"
    try:
        img = fix_orientation(Image.open(src_path).convert("RGB"))
        img.thumbnail((400, 400))
        img.save(thumb_path, "JPEG", quality=82)
    except Exception:
        return "/static/placeholder.jpg"
    return f"/static/thumbs/{thumb_name}"

# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

CLUSTER_EVERY = 200   # auto-cluster after every N new faces
CLUSTER_THRESHOLD = 0.5

def cluster_faces(threshold: float = CLUSTER_THRESHOLD):
    db = get_db()
    unassigned = db.execute(
        "SELECT id, embedding FROM faces WHERE person_id IS NULL"
    ).fetchall()
    if not unassigned:
        return 0

    embeddings = [(row["id"], np.frombuffer(row["embedding"], dtype=np.float32)) for row in unassigned]
    persons_rows = db.execute(
        "SELECT p.id, f.embedding FROM persons p JOIN faces f ON f.id=p.cover_face_id WHERE p.cover_face_id IS NOT NULL"
    ).fetchall()
    person_centroids = {r["id"]: np.frombuffer(r["embedding"], dtype=np.float32) for r in persons_rows}

    def cosine_sim(a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    new_persons = []
    with db:
        for face_id, emb in embeddings:
            best_pid = None
            best_sim = threshold
            for pid, centroid in person_centroids.items():
                sim = cosine_sim(emb, centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_pid = pid
            for np_pid, centroid, _ in new_persons:
                sim = cosine_sim(emb, centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_pid = np_pid
            if best_pid is None:
                cur = db.execute("INSERT INTO persons(created_at) VALUES(?)", (time.time(),))
                new_pid = cur.lastrowid
                db.execute("UPDATE persons SET cover_face_id=? WHERE id=?", (face_id, new_pid))
                new_persons.append((new_pid, emb, [face_id]))
                best_pid = new_pid
            else:
                for entry in new_persons:
                    if entry[0] == best_pid:
                        entry[2].append(face_id)
                        break
            db.execute("UPDATE faces SET person_id=? WHERE id=?", (best_pid, face_id))
    return len(new_persons)

# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

def run_indexer():
    global indexer_state
    indexer_state["running"] = True
    indexer_state["errors"] = 0

    try:
        from PIL import Image
        fa = get_face_app()
        db = get_db()

        # Get enabled folders
        folders = [r["path"] for r in db.execute("SELECT path FROM scan_folders WHERE enabled=1").fetchall()]

        all_files = []
        for folder in folders:
            if not os.path.exists(folder):
                continue
            for root, _, files in os.walk(folder):
                for f in files:
                    if Path(f).suffix.lower() in SUPPORTED:
                        all_files.append(os.path.join(root, f))

        indexed = set(row[0] for row in db.execute("SELECT path FROM photos").fetchall())
        todo = [f for f in all_files if f not in indexed]

        indexer_state["total"] = len(todo)
        indexer_state["processed"] = 0

        faces_since_cluster = 0

        for i, fpath in enumerate(todo):
            if not indexer_state["running"]:
                break

            indexer_state["current_file"] = os.path.basename(fpath)

            try:
                pil_img = Image.open(fpath).convert("RGB")
                img = np.array(pil_img)[:, :, ::-1].copy()
                faces = fa.get(img)

                # Читаємо дату з EXIF окремо
                taken_at = None
                try:
                    from PIL import Image as _Img
                    _tmp = _Img.open(fpath)
                    exif = _tmp._getexif() if hasattr(_tmp, '_getexif') else None
                    if exif:
                        import datetime
                        dt_str = exif.get(36867) or exif.get(306)
                        if dt_str:
                            dt = datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                            taken_at = dt.timestamp()
                    _tmp.close()
                except:
                    pass
                if not taken_at:
                    try:
                        taken_at = os.path.getmtime(fpath)
                    except:
                        pass

                with db:
                    cur = db.execute("INSERT OR IGNORE INTO photos(path, indexed_at, taken_at) VALUES(?,?,?)",
                                     (fpath, time.time(), taken_at))
                    photo_id = cur.lastrowid or db.execute(
                        "SELECT id FROM photos WHERE path=?", (fpath,)).fetchone()[0]
                    if taken_at:
                        db.execute("UPDATE photos SET taken_at=? WHERE id=? AND taken_at IS NULL",
                                   (taken_at, photo_id))

                    for fi, face in enumerate(faces):
                        emb = face.embedding.astype(np.float32).tobytes()
                        bbox = json.dumps(face.bbox.tolist())
                        cur2 = db.execute(
                            "INSERT INTO faces(photo_id, face_index, embedding, bbox) VALUES(?,?,?,?)",
                            (photo_id, fi, emb, bbox)
                        )
                        make_thumb(fpath, cur2.lastrowid, bbox)
                        faces_since_cluster += 1

                # Auto-cluster every CLUSTER_EVERY new faces
                if faces_since_cluster >= CLUSTER_EVERY:
                    indexer_state["clustering"] = True
                    cluster_faces()
                    indexer_state["clustering"] = False
                    faces_since_cluster = 0

            except Exception:
                indexer_state["errors"] += 1

            indexer_state["processed"] = i + 1

        # Final cluster pass
        if faces_since_cluster > 0:
            indexer_state["clustering"] = True
            cluster_faces()
            indexer_state["clustering"] = False

    finally:
        indexer_state["running"] = False
        indexer_state["clustering"] = False
        indexer_state["current_file"] = ""

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/status")
def status():
    db = get_db()
    photos = db.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
    faces = db.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    persons = db.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    return {**indexer_state, "db_photos": photos, "db_faces": faces, "db_persons": persons}

@app.post("/api/indexer/start")
def start_indexer():
    if indexer_state["running"]:
        return {"ok": False, "msg": "Already running"}
    t = threading.Thread(target=run_indexer, daemon=True)
    t.start()
    return {"ok": True}

@app.post("/api/indexer/stop")
def stop_indexer():
    indexer_state["running"] = False
    return {"ok": True}

@app.post("/api/cluster")
def do_cluster():
    if indexer_state["running"]:
        return {"ok": False, "msg": "Зачекай поки індексація завершиться"}
    n = cluster_faces()
    return {"ok": True, "new_persons": n}

# Folders API
@app.get("/api/folders")
def get_folders():
    db = get_db()
    rows = db.execute("SELECT id, path, enabled FROM scan_folders ORDER BY id").fetchall()
    return [{"id": r["id"], "path": r["path"], "enabled": bool(r["enabled"])} for r in rows]

@app.post("/api/folders")
async def add_folder(data: dict):
    path = data.get("path", "").strip()
    if not path:
        return JSONResponse({"ok": False, "msg": "Шлях не вказано"}, status_code=400)
    db = get_db()
    try:
        with db:
            db.execute("INSERT INTO scan_folders(path, enabled) VALUES(?, 1)", (path,))
        return {"ok": True}
    except Exception:
        return JSONResponse({"ok": False, "msg": "Така папка вже є"}, status_code=400)

@app.delete("/api/folders/{folder_id}")
def delete_folder(folder_id: int):
    db = get_db()
    with db:
        db.execute("DELETE FROM scan_folders WHERE id=?", (folder_id,))
    return {"ok": True}

@app.patch("/api/folders/{folder_id}")
async def toggle_folder(folder_id: int, data: dict):
    db = get_db()
    with db:
        db.execute("UPDATE scan_folders SET enabled=? WHERE id=?", (1 if data.get("enabled") else 0, folder_id))
    return {"ok": True}

# Persons API
@app.get("/api/persons")
def list_persons(limit: int = 100, offset: int = 0, search: str = "", sort: str = "count"):
    db = get_db()
    order_named = "LOWER(p.name) ASC" if sort == "name" else "photo_count DESC"
    search_pat = f"%{search.lower()}%" if search else None
    if search_pat:
        rows = db.execute(f"""
            SELECT p.id, p.name, p.cover_face_id, p.is_favorite, p.sort_order,
                   (SELECT COUNT(DISTINCT photo_id) FROM faces WHERE person_id=p.id) as photo_count
            FROM persons p
            WHERE LOWER(p.name) LIKE ?
            ORDER BY p.is_favorite DESC, p.sort_order ASC,
                     CASE WHEN p.name IS NULL OR p.name='' THEN 1 ELSE 0 END ASC,
                     {order_named}
            LIMIT ? OFFSET ?
        """, (search_pat, limit, offset)).fetchall()
    else:
        rows = db.execute(f"""
            SELECT p.id, p.name, p.cover_face_id, p.is_favorite, p.sort_order,
                   (SELECT COUNT(DISTINCT photo_id) FROM faces WHERE person_id=p.id) as photo_count
            FROM persons p
            ORDER BY p.is_favorite DESC, p.sort_order ASC,
                     CASE WHEN p.name IS NULL OR p.name='' THEN 1 ELSE 0 END ASC,
                     {order_named}
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
    result = []
    for r in rows:
        cover_url = None
        if r["cover_face_id"]:
            thumb_path = THUMBS_DIR / f"face_{r['cover_face_id']}.jpg"
            if thumb_path.exists():
                cover_url = f"/static/thumbs/face_{r['cover_face_id']}.jpg"
            else:
                face = db.execute("SELECT id, photo_id, bbox FROM faces WHERE id=?", (r["cover_face_id"],)).fetchone()
                if face:
                    photo = db.execute("SELECT path FROM photos WHERE id=?", (face["photo_id"],)).fetchone()
                    if photo:
                        cover_url = make_thumb(photo["path"], face["id"], face["bbox"])
        result.append({
            "id": r["id"], "name": r["name"],
            "photo_count": r["photo_count"], "cover_url": cover_url,
            "is_favorite": bool(r["is_favorite"]), "sort_order": r["sort_order"],
        })
    return result

@app.get("/api/persons/count")
def persons_count(search: str = ""):
    db = get_db()
    if search:
        row = db.execute("SELECT COUNT(*) FROM persons WHERE LOWER(name) LIKE ?", (f"%{search.lower()}%",)).fetchone()
    else:
        row = db.execute("SELECT COUNT(*) FROM persons").fetchone()
    return {"count": row[0]}

@app.post("/api/persons/reorder")
async def reorder_favorites(data: dict):
    """data: {ids: [id1, id2, ...]} — ordered list of favorite person ids"""
    ids = data.get("ids", [])
    db = get_db()
    with db:
        for i, pid in enumerate(ids):
            db.execute("UPDATE persons SET sort_order=? WHERE id=?", (i, pid))
    return {"ok": True}

@app.get("/api/persons/{person_id}")
def get_person(person_id: int):
    db = get_db()
    r = db.execute("""
        SELECT p.id, p.name, p.cover_face_id, p.is_favorite, p.sort_order,
               (SELECT COUNT(DISTINCT photo_id) FROM faces WHERE person_id=p.id) as photo_count
        FROM persons p WHERE p.id=?
    """, (person_id,)).fetchone()
    if not r: return JSONResponse({"error": "not found"}, status_code=404)
    cover_url = None
    if r["cover_face_id"]:
        thumb_path = THUMBS_DIR / f"face_{r['cover_face_id']}.jpg"
        if thumb_path.exists():
            cover_url = f"/static/thumbs/face_{r['cover_face_id']}.jpg"
    return {"id": r["id"], "name": r["name"], "photo_count": r["photo_count"],
            "cover_url": cover_url, "is_favorite": bool(r["is_favorite"]), "sort_order": r["sort_order"]}

@app.get("/api/persons/{person_id}/years")
def person_years(person_id: int):
    """Return all years for a person for timeline."""
    import datetime
    db = get_db()
    rows = db.execute("""
        SELECT DISTINCT CAST(strftime('%Y', datetime(ph.taken_at, 'unixepoch')) AS INTEGER) as year
        FROM photos ph
        JOIN faces f ON f.photo_id = ph.id
        WHERE f.person_id = ? AND ph.taken_at IS NOT NULL
        ORDER BY year DESC
    """, (person_id,)).fetchall()
    return [r["year"] for r in rows if r["year"]]

@app.get("/api/persons/{person_id}/photos")
def person_photos(person_id: int, limit: int = 200, offset: int = 0, year: int = None):
    import datetime
    db = get_db()
    if year:
        year_start = datetime.datetime(year, 1, 1).timestamp()
        year_end = datetime.datetime(year, 12, 31, 23, 59, 59).timestamp()
        rows = db.execute("""
            SELECT DISTINCT ph.id, ph.path, ph.taken_at FROM photos ph
            JOIN faces f ON f.photo_id = ph.id
            WHERE f.person_id = ? AND ph.taken_at BETWEEN ? AND ?
            ORDER BY ph.taken_at DESC
            LIMIT ? OFFSET ?
        """, (person_id, year_start, year_end, limit, offset)).fetchall()
    else:
        rows = db.execute("""
            SELECT DISTINCT ph.id, ph.path, ph.taken_at FROM photos ph
            JOIN faces f ON f.photo_id = ph.id
            WHERE f.person_id = ?
            ORDER BY ph.taken_at DESC NULLS LAST
            LIMIT ? OFFSET ?
        """, (person_id, limit, offset)).fetchall()
    result = []
    for r in rows:
        yr = None
        if r["taken_at"]:
            try:
                yr = datetime.datetime.fromtimestamp(r["taken_at"]).year
            except Exception:
                pass
        result.append({
            "id": r["id"],
            "path": r["path"],
            "thumb": make_photo_thumb(r["path"], r["id"]),
            "taken_at": r["taken_at"],
            "year": yr
        })
    return result

@app.post("/api/persons/{person_id}/favorite")
def toggle_favorite(person_id: int):
    db = get_db()
    row = db.execute("SELECT is_favorite FROM persons WHERE id=?", (person_id,)).fetchone()
    if not row:
        return JSONResponse({"ok": False}, status_code=404)
    new_val = 0 if row["is_favorite"] else 1
    with db:
        db.execute("UPDATE persons SET is_favorite=? WHERE id=?", (new_val, person_id))
    return {"ok": True, "is_favorite": bool(new_val)}

@app.post("/api/persons/split")
async def split_person(data: dict):
    """Переміщує вибрані фото (по photo_id) до іншої або нової людини."""
    photo_ids = data.get("photo_ids", [])
    target_person_id = data.get("target_person_id")  # None = створити нову
    if not photo_ids:
        return JSONResponse({"ok": False, "error": "no photos"}, status_code=400)
    db = get_db()
    with db:
        if target_person_id is None:
            # Створюємо нову людину
            cur = db.execute("INSERT INTO persons (name) VALUES ('')")
            target_person_id = cur.lastrowid
        # Переміщуємо faces цих фото від поточної людини до нової
        for photo_id in photo_ids:
            db.execute("""
                UPDATE faces SET person_id = ?
                WHERE photo_id = ? AND person_id IN (
                    SELECT DISTINCT person_id FROM faces WHERE photo_id = ?
                )
            """, (target_person_id, photo_id, photo_id))
    return {"ok": True, "target_person_id": target_person_id}


@app.patch("/api/persons/{person_id}")
async def update_person(person_id: int, data: dict):
    db = get_db()
    if "name" in data:
        with db:
            db.execute("UPDATE persons SET name=? WHERE id=?", (data["name"], person_id))
    if "cover_face_id" in data:
        with db:
            db.execute("UPDATE persons SET cover_face_id=? WHERE id=?", (data["cover_face_id"], person_id))
    return {"ok": True}

@app.delete("/api/persons/{person_id}")
def delete_person(person_id: int):
    db = get_db()
    with db:
        db.execute("DELETE FROM faces WHERE person_id=?", (person_id,))
        db.execute("DELETE FROM persons WHERE id=?", (person_id,))
    return {"ok": True}

@app.post("/api/photos/{photo_id}/unlink")
def unlink_photo(photo_id: int):
    """Remove photo faces from their person group (but keep in DB)."""
    db = get_db()
    with db:
        db.execute("UPDATE faces SET person_id=NULL WHERE photo_id=?", (photo_id,))
    return {"ok": True}

@app.get("/api/photos/{photo_id}/face-for-person/{person_id}")
def face_for_person(photo_id: int, person_id: int):
    db = get_db()
    row = db.execute(
        "SELECT id FROM faces WHERE photo_id=? AND person_id=? LIMIT 1",
        (photo_id, person_id)
    ).fetchone()
    return {"face_id": row["id"] if row else None}

@app.post("/api/persons/merge")
async def merge_persons(data: dict):
    src = data.get("src_id")
    dst = data.get("dst_id")
    print(f"MERGE: src={src} dst={dst} data={data}")
    if src is None or dst is None:
        return JSONResponse({"ok": False, "msg": "src_id and dst_id required"}, status_code=400)
    src = int(src)
    dst = int(dst)

    import asyncio, time as _time
    was_running = indexer_state["running"]
    indexer_state["running"] = False
    await asyncio.sleep(0.5)  # let indexer finish current step

    def do_merge():
        with merge_lock:
            db = get_db()
            with db:
                db.execute("UPDATE faces SET person_id=? WHERE person_id=?", (dst, src))
                db.execute("DELETE FROM persons WHERE id=?", (src,))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, do_merge)

    if was_running:
        indexer_state["running"] = True
        t = threading.Thread(target=run_indexer, daemon=True)
        t.start()
    return {"ok": True}

@app.post("/api/search")
async def search_by_face(file: UploadFile = File(...)):
    import tempfile
    from PIL import Image as PILImage
    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    fa = get_face_app()
    try:
        pil_img = PILImage.open(tmp_path).convert("RGB")
        img = np.array(pil_img)[:, :, ::-1].copy()
    except Exception:
        img = None
    os.unlink(tmp_path)
    if img is None:
        return JSONResponse({"error": "Cannot read image"}, status_code=400)
    faces = fa.get(img)
    if not faces:
        return {"persons": [], "msg": "No faces detected"}
    query_emb = faces[0].embedding.astype(np.float32)
    db = get_db()
    all_faces = db.execute("SELECT id, embedding, person_id FROM faces WHERE person_id IS NOT NULL").fetchall()
    scores = {}
    for row in all_faces:
        emb = np.frombuffer(row["embedding"], dtype=np.float32)
        sim = float(np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb) + 1e-8))
        pid = row["person_id"]
        if pid not in scores or scores[pid] < sim:
            scores[pid] = sim
    matched = sorted([(pid, sim) for pid, sim in scores.items() if sim >= 0.45], key=lambda x: -x[1])[:5]
    persons = list_persons()
    pid_map = {p["id"]: p for p in persons}
    result = []
    for pid, sim in matched:
        if pid in pid_map:
            p = dict(pid_map[pid])
            p["similarity"] = round(sim * 100, 1)
            result.append(p)
    return {"persons": result}

@app.get("/api/photo/image")
def photo_image(path: str):
    from fastapi.responses import FileResponse
    import mimetypes
    mt = mimetypes.guess_type(path)[0] or "image/jpeg"
    return FileResponse(path, media_type=mt)

@app.get("/api/photo/open")
def open_photo(path: str):
    import subprocess
    subprocess.Popen(["explorer", "/select,", path])
    return {"ok": True}

@app.get("/api/browse-folder")
def browse_folder():
    """Open native Windows folder picker, return selected path."""
    import subprocess, tempfile, sys
    script = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "root = tk.Tk()\n"
        "root.withdraw()\n"
        "root.wm_attributes('-topmost', 1)\n"
        "path = filedialog.askdirectory(title='Обери папку з фото')\n"
        "print(path)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True
    )
    path = result.stdout.strip().replace("/", "\\")
    if path:
        return {"ok": True, "path": path}
    return {"ok": False, "path": ""}

@app.get("/api/version")
def get_version():
    return {"version": VERSION}

@app.get("/api/check-update")
async def check_update():
    import urllib.request
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers={"User-Agent": "FaceLib"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            latest = data["tag_name"].lstrip("v")
            return {"current": VERSION, "latest": latest, "has_update": latest != VERSION, "tag": data["tag_name"], "name": data["name"]}
    except Exception as e:
        return {"error": str(e), "current": VERSION}

@app.post("/api/update")
async def do_update():
    import urllib.request, zipfile, shutil, tempfile
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers={"User-Agent": "FaceLib"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{data['tag_name']}.zip"
        app_dir = Path(__file__).parent
        backup_dir = app_dir / "backup"
        backup_dir.mkdir(exist_ok=True)
        for f in ["app.py", "index.html"]:
            src = app_dir / f
            if src.exists():
                shutil.copy2(src, backup_dir / f)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name
        urllib.request.urlretrieve(zip_url, tmp_path)
        with zipfile.ZipFile(tmp_path) as z:
            for member in z.namelist():
                filename = Path(member).name
                if filename in ["app.py", "index.html"]:
                    with z.open(member) as src, open(app_dir / filename, "wb") as dst:
                        dst.write(src.read())
        Path(tmp_path).unlink()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/rollback")
async def do_rollback():
    import shutil
    app_dir = Path(__file__).parent
    backup_dir = app_dir / "backup"
    if not backup_dir.exists():
        return {"ok": False, "error": "No backup found"}
    for f in ["app.py", "index.html"]:
        src = backup_dir / f
        if src.exists():
            shutil.copy2(src, app_dir / f)
    return {"ok": True}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    return FileResponse("index.html")

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=7788, reload=False)

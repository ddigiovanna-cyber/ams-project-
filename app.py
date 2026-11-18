from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Optional
import sqlite3
import json
import io
import os
import secrets
import shutil
import networkx as nx
import qrcode

app = FastAPI(title="AMS-03 - Archaeological Matrix & AR Museum")
security = HTTPBasic()

ADMIN_USER = os.getenv("AMS_ADMIN_USER", "archeologo")
ADMIN_PASS = os.getenv("AMS_ADMIN_PASS", "harris2026")

os.makedirs("static/models", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = "ams_museum.db"

def verifica_admin(credentials: HTTPBasicCredentials = Depends(security)):
    user_ok = secrets.compare_digest(credentials.username.encode("utf8"), ADMIN_USER.encode("utf8"))
    pass_ok = secrets.compare_digest(credentials.password.encode("utf8"), ADMIN_PASS.encode("utf8"))
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

class SalaMuseale(BaseModel):
    id: str
    nome: str
    descrizione: str

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sale (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            descrizione TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS unita_stratigrafiche (
            id TEXT NOT NULL,
            sala_id TEXT NOT NULL,
            nome TEXT NOT NULL,
            periodo TEXT,
            descrizione TEXT,
            copre TEXT,
            modello_glb TEXT,
            modello_usdz TEXT,
            PRIMARY KEY (id, sala_id),
            FOREIGN KEY (sala_id) REFERENCES sale(id)
        )
    """)
    cur.execute("SELECT COUNT(*) FROM sale")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO sale VALUES (?, ?, ?)", [
            ("sala1", "Sala 1 - Domus Imperiale", "Scavo urbano di età romana imperial-tardoantica."),
            ("sala2", "Sala 2 - Necropoli Arcaica", "Area funeraria con sepolture a cassa litica.")
        ])
        dati_iniziali = [
            ("US1", "sala1", "Humus superficiale", "Età Contemporanea", "Strato agricolo superficiale.", json.dumps(["US2", "US3"]), "/static/models/strato_moderno.glb", "/static/models/strato_moderno.usdz"),
            ("US2", "sala1", "Crollo tetto in tegole", "V sec. d.C.", "Crollo delle coperture fittili.", json.dumps(["US3", "US4"]), "/static/models/crollo_tetto.glb", "/static/models/crollo_tetto.usdz"),
            ("US3", "sala1", "Muro perimetrale Nord", "II sec. d.C.", "Struttura muraria in opera listata.", json.dumps(["US5"]), "/static/models/muro_romano.glb", "/static/models/muro_romano.usdz"),
            ("US4", "sala1", "Pavimento a mosaico", "II sec. d.C.", "Tessellato bicromo geometrico.", json.dumps(["US5"]), "/static/models/mosaico_ar.glb", "/static/models/mosaico_ar.usdz"),
            ("US5", "sala1", "Fossa di fondazione", "I sec. d.C.", "Taglio nel banco vergine.", json.dumps([]), "/static/models/fondazioni.glb", "/static/models/fondazioni.usdz"),
            ("US10", "sala2", "Terreno colluviale", "Età Ellenistica", "Deposito naturale di copertura.", json.dumps(["US11"]), "/static/models/colluvio.glb", "/static/models/colluvio.usdz"),
            ("US11", "sala2", "Tomba a cassa litica", "VI sec. a.C.", "Sepoltura con corredo ceramico.", json.dumps([]), "/static/models/tomba_arcaica.glb", "/static/models/tomba_arcaica.usdz")
        ]
        cur.executemany("INSERT INTO unita_stratigrafiche VALUES (?, ?, ?, ?, ?, ?, ?, ?)", dati_iniziali)
    conn.commit()
    conn.close()

init_db()

def calcola_matrix_sala(sala_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM unita_stratigrafiche WHERE sala_id = ?", (sala_id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {"nodi": [], "archi": []}

    dati_us = {}
    G = nx.DiGraph()

    for r in rows:
        us_id = r["id"]
        copre_list = json.loads(r["copre"] or "[]")
        dati_us[us_id] = dict(r)
        G.add_node(us_id)
        for target_id in copre_list:
            G.add_edge(us_id, target_id)

    G.remove_nodes_from([n for n in list(G.nodes()) if n not in dati_us])

    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Errore stratigrafico: ciclo cronologico rilevato nella sala!")

    matrix_ridotto = nx.transitive_reduction(G)

    nodi = [
        {
            "id": n,
            "sala_id": dati_us[n]["sala_id"],
            "nome": dati_us[n]["nome"],
            "periodo": dati_us[n]["periodo"],
            "descrizione": dati_us[n]["descrizione"],
            "copre": json.loads(dati_us[n]["copre"] or "[]"),
            "modello_glb": dati_us[n]["modello_glb"],
            "modello_usdz": dati_us[n]["modello_usdz"]
        }
        for n in matrix_ridotto.nodes()
    ]
    archi = [{"source": u, "target": v} for u, v in matrix_ridotto.edges()]
    return {"nodi": nodi, "archi": archi}

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin")
async def admin_panel(request: Request, username: str = Depends(verifica_admin)):
    return templates.TemplateResponse("admin.html", {"request": request, "username": username})

@app.get("/api/sale")
async def lista_sale():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sale")
    sale = [dict(r) for r in cur.fetchall()]
    conn.close()
    return sale

@app.post("/api/admin/sale")
async def crea_sala(sala: SalaMuseale, username: str = Depends(verifica_admin)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO sale VALUES (?, ?, ?)", (sala.id.strip(), sala.nome.strip(), sala.descrizione.strip()))
    conn.commit()
    conn.close()
    return {"messaggio": f"Sala '{sala.nome}' salvata con successo"}

@app.get("/api/matrix/{sala_id}")
async def get_matrix(sala_id: str):
    try:
        return calcola_matrix_sala(sala_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/admin/us")
async def salva_us_con_upload(
    id: str = Form(...),
    sala_id: str = Form(...),
    nome: str = Form(...),
    periodo: str = Form(""),
    descrizione: str = Form(""),
    copre: str = Form(""),
    file_glb: Optional[UploadFile] = File(None),
    file_usdz: Optional[UploadFile] = File(None),
    username: str = Depends(verifica_admin)
):
    us_id = id.strip().upper()
    s_id = sala_id.strip()
    copre_list = [x.strip().upper() for x in copre.split(",") if x.strip()]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT modello_glb, modello_usdz FROM unita_stratigrafiche WHERE id = ? AND sala_id = ?", (us_id, s_id))
    esistente = cur.fetchone()

    path_glb = esistente["modello_glb"] if esistente else None
    path_usdz = esistente["modello_usdz"] if esistente else None

    if file_glb and file_glb.filename:
        if not file_glb.filename.lower().endswith(".glb"):
            conn.close()
            raise HTTPException(status_code=400, detail="Il modello Android/Web deve essere in formato .glb")
        nome_file = f"{s_id}_{us_id}.glb"
        dest = os.path.join("static/models", nome_file)
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file_glb.file, buffer)
        path_glb = f"/static/models/{nome_file}"

    if file_usdz and file_usdz.filename:
        if not file_usdz.filename.lower().endswith(".usdz"):
            conn.close()
            raise HTTPException(status_code=400, detail="Il modello iOS deve essere in formato .usdz")
        nome_file = f"{s_id}_{us_id}.usdz"
        dest = os.path.join("static/models", nome_file)
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file_usdz.file, buffer)
        path_usdz = f"/static/models/{nome_file}"

    cur.execute(
        "INSERT OR REPLACE INTO unita_stratigrafiche VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (us_id, s_id, nome.strip(), periodo.strip(), descrizione.strip(), json.dumps(copre_list), path_glb, path_usdz)
    )
    conn.commit()
    conn.close()
    return {"messaggio": f"Unità Stratigrafica {us_id} salvata in {s_id}"}

@app.delete("/api/admin/us/{sala_id}/{us_id}")
async def elimina_us(sala_id: str, us_id: str, username: str = Depends(verifica_admin)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM unita_stratigrafiche WHERE sala_id = ? AND id = ?", (sala_id, us_id))
    conn.commit()
    conn.close()
    return {"messaggio": f"US {us_id} eliminata"}

@app.get("/api/qr/{sala_id}/{us_id}")
async def genera_qr_teca(request: Request, sala_id: str, us_id: str):
    base_url = str(request.base_url).rstrip("/")
    target_url = f"{base_url}/?sala={sala_id}&us={us_id}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=3)
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#18181b", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    headers = {"Content-Disposition": f'inline; filename="QR_{sala_id}_{us_id}.png"'}
    return StreamingResponse(buf, media_type="image/png", headers=headers)

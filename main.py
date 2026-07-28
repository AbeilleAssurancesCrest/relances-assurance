from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import (init_db, add_client_avec_contrats, get_all_clients, 
                      log_relance, get_historique, update_statut, delete_client, 
                      update_contrat_details, update_commentaire)

app = FastAPI()
init_db()

# Autoriser toutes les origines pour le partage en réseau local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="."), name="static")
templates = Jinja2Templates(directory="templates")

class ContratSchema(BaseModel):
    num_contrat: str
    type_vehicule: str = "Voiture"
    date_effet: str
    marque: str = ""
    immat: str = ""
    pieces: list[str] = []

class ClientSchema(BaseModel):
    nom: str
    prenom: str
    email: str = ""
    telephone: str = ""
    commentaire: str = ""
    contrats: list[ContratSchema]

class RelanceSchema(BaseModel):
    client_id: int
    email: str
    pieces: list[str]

class StatutSchema(BaseModel):
    client_id: int
    statut: str

class ContratUpdateSchema(BaseModel):
    contrat_id: int
    immat: str = ""
    pieces: list[str] = []

class CommentaireUpdateSchema(BaseModel):
    client_id: int
    commentaire: str

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/dossiers")
def fetch_dossiers():
    return get_all_clients()

@app.post("/api/dossiers")
def create_dossier(data: ClientSchema):
    contrats_list = [c.dict() for c in data.contrats]
    add_client_avec_contrats(data.nom, data.prenom, data.email, data.telephone, data.commentaire, contrats_list)
    return {"status": "ok"}

@app.post("/api/contrats/update")
def modify_contrat(data: ContratUpdateSchema):
    update_contrat_details(data.contrat_id, data.immat, data.pieces)
    return {"status": "ok"}

@app.post("/api/dossiers/update_commentaire")
def modify_commentaire(data: CommentaireUpdateSchema):
    update_commentaire(data.client_id, data.commentaire)
    return {"status": "ok"}

@app.post("/api/statut")
def change_statut(data: StatutSchema):
    update_statut(data.client_id, data.statut)
    return {"status": "ok"}

@app.delete("/api/dossiers/{client_id}")
def remove_dossier(client_id: int):
    delete_client(client_id)
    return {"status": "ok"}

@app.post("/api/relancer")
def relancer(data: RelanceSchema):
    log_relance(data.client_id, data.email, data.pieces)
    return {"status": "ok"}

@app.get("/api/historique/{client_id}")
def fetch_historique(client_id: int):
    return get_historique(client_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

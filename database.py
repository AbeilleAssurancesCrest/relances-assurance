import os
import json
import requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pswcxcjvybvsvimfrrnq.supabase.co").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

# Nettoyage automatique au cas où une URL markdown est injectée
if "[" in SUPABASE_URL:
    SUPABASE_URL = "https://pswcxcjvybvsvimfrrnq.supabase.co"

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None

def init_db():
    pass

def add_client_avec_contrats(nom, prenom, email, telephone, commentaire, liste_contrats):
    if not SUPABASE_KEY:
        return
    
    url_client = f"{SUPABASE_URL}/rest/v1/clients"
    payload_client = {
        "nom": nom,
        "prenom": prenom,
        "email": email,
        "telephone": telephone,
        "commentaire": commentaire,
        "statut": "En attente"
    }
    r = requests.post(url_client, headers=get_headers(), json=payload_client)
    
    if r.status_code in [200, 201]:
        res = r.json()
        if res and len(res) > 0:
            client_id = res[0]['id']
            
            url_contrat = f"{SUPABASE_URL}/rest/v1/contrats"
            for c in liste_contrats:
                pieces_json = json.dumps(c.get('pieces', []))
                payload_contrat = {
                    "client_id": client_id,
                    "num_contrat": c['num_contrat'],
                    "type_vehicule": c.get('type_vehicule', 'Voiture'),
                    "date_effet": c['date_effet'],
                    "marque": c.get('marque', ''),
                    "immat": c.get('immat', ''),
                    "pieces_manquantes": pieces_json,
                    "pieces_initiales": pieces_json
                }
                requests.post(url_contrat, headers=get_headers(), json=payload_contrat)

def add_contrats_a_client(client_id, liste_contrats):
    if not SUPABASE_KEY:
        return False

    url_client = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}&select=id"
    response_client = requests.get(url_client, headers=get_headers())
    if response_client.status_code != 200 or not response_client.json():
        return False

    url_contrats = f"{SUPABASE_URL}/rest/v1/contrats"
    payloads = []
    for contrat in liste_contrats:
        pieces_json = json.dumps(contrat.get('pieces', []))
        payloads.append({
            "client_id": client_id,
            "num_contrat": contrat['num_contrat'],
            "type_vehicule": contrat.get('type_vehicule', 'Voiture'),
            "date_effet": contrat['date_effet'],
            "marque": contrat.get('marque', ''),
            "immat": contrat.get('immat', ''),
            "pieces_manquantes": pieces_json,
            "pieces_initiales": pieces_json
        })

    response = requests.post(url_contrats, headers=get_headers(), json=payloads)
    return response.status_code in (200, 201)

def get_all_clients():
    if not SUPABASE_KEY:
        return []
    
    url_clients = f"{SUPABASE_URL}/rest/v1/clients?select=*&order=id.desc"
    r = requests.get(url_clients, headers=get_headers())
    if r.status_code != 200:
        return []
    
    clients = r.json()
    
    for cl in clients:
        url_c = f"{SUPABASE_URL}/rest/v1/contrats?client_id=eq.{cl['id']}"
        rc = requests.get(url_c, headers=get_headers())
        contrats_db = rc.json() if rc.status_code == 200 else []
        
        contrats_list = []
        dossier_complet = True
        for c in contrats_db:
            c_dict = dict(c)
            try:
                c_dict['pieces_manquantes'] = json.loads(c_dict['pieces_manquantes']) if c_dict.get('pieces_manquantes') else []
            except:
                c_dict['pieces_manquantes'] = []
            
            try:
                c_dict['pieces_initiales'] = json.loads(c_dict['pieces_initiales']) if c_dict.get('pieces_initiales') else []
            except:
                c_dict['pieces_initiales'] = []

            contrats_list.append(c_dict)

            if len(c_dict['pieces_manquantes']) > 0:
                dossier_complet = False

        cl['contrats'] = contrats_list

        if dossier_complet:
            cl['niveau_urgence'] = 'vert'
            cl['texte_statut'] = 'Complet — à supprimer'
        else:
            reference_date = cl.get('derniere_relance') or cl.get('date_creation')
            if not reference_date:
                dates_effet = [c.get('date_effet') for c in contrats_list if c.get('date_effet')]
                reference_date = min(dates_effet) if dates_effet else None

            date_reference = _parse_timestamp(reference_date)
            jours = max(0, (datetime.now(timezone.utc) - date_reference).days) if date_reference else 0
            relance_deja_envoyee = bool(cl.get('derniere_relance'))

            if jours >= 15:
                cl['niveau_urgence'] = 'rouge'
                cl['texte_statut'] = f'Urgent ({jours} j)'
            elif jours >= 7:
                cl['niveau_urgence'] = 'orange'
                etiquette = 'Relance à faire' if relance_deja_envoyee else 'Première relance à faire'
                cl['texte_statut'] = f'{etiquette} ({jours} j)'
            else:
                cl['niveau_urgence'] = 'vert'
                etiquette = 'Relancé récemment' if relance_deja_envoyee else 'En cours'
                cl['texte_statut'] = f'{etiquette} ({jours} j)'

    return clients

def update_contrat_details(contrat_id, immat, pieces):
    if not SUPABASE_KEY: return
    url = f"{SUPABASE_URL}/rest/v1/contrats?id=eq.{contrat_id}"
    payload = {"immat": immat, "pieces_manquantes": json.dumps(pieces)}
    requests.patch(url, headers=get_headers(), json=payload)

def update_commentaire(client_id, commentaire):
    if not SUPABASE_KEY: return
    url = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    requests.patch(url, headers=get_headers(), json={"commentaire": commentaire})

def delete_client(client_id):
    if not SUPABASE_KEY: return
    url = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    requests.delete(url, headers=get_headers())

def log_relance(client_id, email, pieces):
    if not SUPABASE_KEY:
        return False
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    
    url_cl = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    response_client = requests.patch(url_cl, headers=get_headers(), json={"derniere_relance": now})
    if not response_client.ok:
        return False
    
    url_h = f"{SUPABASE_URL}/rest/v1/historique"
    payload_h = {
        "client_id": client_id,
        "date_heure": now,
        "email": email,
        "pieces": json.dumps(pieces)
    }
    response_historique = requests.post(url_h, headers=get_headers(), json=payload_h)
    return response_historique.status_code in (200, 201, 204)

def get_historique(client_id):
    if not SUPABASE_KEY: return []
    url = f"{SUPABASE_URL}/rest/v1/historique?client_id=eq.{client_id}&order=id.desc"
    r = requests.get(url, headers=get_headers())
    if r.status_code != 200: return []
    rows = r.json()
    for r_item in rows:
        try:
            r_item['pieces'] = json.loads(r_item['pieces']) if r_item.get('pieces') else []
        except:
            r_item['pieces'] = []
    return rows

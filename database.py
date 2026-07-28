import os
import json
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pswcxcjvybvsvimfrrnq.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def init_db():
    pass

def add_client_avec_contrats(nom, prenom, email, telephone, commentaire, liste_contrats):
    if not SUPABASE_KEY: return
    
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

def get_all_clients():
    if not SUPABASE_KEY: return []
    
    url_clients = f"{SUPABASE_URL}/rest/v1/clients?select=*&order=id.desc"
    r = requests.get(url_clients, headers=get_headers())
    if r.status_code != 200: return []
    
    clients = r.json()
    
    for cl in clients:
        url_c = f"{SUPABASE_URL}/rest/v1/contrats?client_id=eq.{cl['id']}"
        rc = requests.get(url_c, headers=get_headers())
        contrats_db = rc.json() if rc.status_code == 200 else []
        
        contrats_list = []
        dossier_complet = True
        nb_jours_max = 0

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

            if c_dict.get('date_effet'):
                from datetime import datetime
                try:
                    d_effet = datetime.strptime(c_dict['date_effet'], '%Y-%m-%d')
                    delta = (datetime.now() - d_effet).days
                    if delta > nb_jours_max:
                        nb_jours_max = delta
                except:
                    pass

        cl['contrats'] = contrats_list

        if cl.get('statut') == 'Archivé':
            cl['niveau_urgence'] = 'archive'
            cl['texte_statut'] = 'Archivé'
        elif dossier_complet:
            cl['niveau_urgence'] = 'vert'
            cl['texte_statut'] = 'Complet (Prêt à archiver)'
        elif nb_jours_max >= 15:
            cl['niveau_urgence'] = 'rouge'
            cl['texte_statut'] = f'Urgent ({nb_jours_max} jrs)'
        elif nb_jours_max >= 7:
            cl['niveau_urgence'] = 'orange'
            cl['texte_statut'] = f'Relance requise ({nb_jours_max} jrs)'
        else:
            cl['niveau_urgence'] = 'vert'
            cl['texte_statut'] = f'En cours ({nb_jours_max} jrs)'

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

def update_statut(client_id, statut):
    if not SUPABASE_KEY: return
    url = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    requests.patch(url, headers=get_headers(), json={"statut": statut})

def delete_client(client_id):
    if not SUPABASE_KEY: return
    url = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    requests.delete(url, headers=get_headers())

def log_relance(client_id, email, pieces):
    if not SUPABASE_KEY: return
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    url_cl = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    requests.patch(url_cl, headers=get_headers(), json={"derniere_relance": now})
    
    url_h = f"{SUPABASE_URL}/rest/v1/historique"
    payload_h = {
        "client_id": client_id,
        "date_heure": now,
        "email": email,
        "pieces": json.dumps(pieces)
    }
    requests.post(url_h, headers=get_headers(), json=payload_h)

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

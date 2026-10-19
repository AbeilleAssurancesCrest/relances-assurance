import os
import json
import requests
from datetime import datetime, timezone, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pswcxcjvybvsvimfrrnq.supabase.co").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

# Nettoyage automatique au cas où une URL markdown est injectée
if "[" in SUPABASE_URL:
    SUPABASE_URL = "https://pswcxcjvybvsvimfrrnq.supabase.co"

def get_headers():
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    # Les nouvelles clés Supabase sb_publishable_/sb_secret_ ne sont pas des JWT.
    # Elles doivent être envoyées dans apikey, jamais comme jeton Bearer.
    if not SUPABASE_KEY.startswith(("sb_publishable_", "sb_secret_")):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    return headers

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
    url_contrats = f"{SUPABASE_URL}/rest/v1/contrats?select=*&order=id.asc"
    response_contrats = requests.get(url_contrats, headers=get_headers())
    contrats_par_client = {}
    if response_contrats.status_code == 200:
        for contrat in response_contrats.json():
            contrats_par_client.setdefault(contrat.get('client_id'), []).append(contrat)

    for cl in clients:
        contrats_db = contrats_par_client.get(cl['id'], [])
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

def _mutation_result(response, action):
    if response.ok:
        try:
            lignes = response.json()
            if isinstance(lignes, list) and not lignes:
                return False, f"{action} : aucune fiche modifiée. Vérifie les droits Supabase ou l’existence de la fiche."
        except (ValueError, AttributeError):
            pass
        return True, ""
    try:
        contenu = response.json()
        details = [contenu.get(cle) for cle in ("message", "details", "hint", "code") if contenu.get(cle)]
        explication = " — ".join(str(detail) for detail in details)
    except (ValueError, AttributeError):
        explication = response.text.strip()
    detail = f"{action} impossible (Supabase HTTP {response.status_code})"
    if explication:
        detail += f" : {explication}"
    return False, detail

def update_contrat_details(contrat_id, immat, pieces, num_contrat=""):
    if not SUPABASE_KEY: return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/contrats?id=eq.{contrat_id}"
    payload = {"immat": immat, "pieces_manquantes": json.dumps(pieces)}
    if num_contrat:
        payload["num_contrat"] = num_contrat
    response = requests.patch(url, headers=get_headers(), json=payload)
    return _mutation_result(response, "Modification du contrat")

def update_commentaire(client_id, commentaire):
    if not SUPABASE_KEY: return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    response = requests.patch(url, headers=get_headers(), json={"commentaire": commentaire})
    return _mutation_result(response, "Modification du commentaire")

def update_coordonnees(client_id, email, telephone):
    if not SUPABASE_KEY: return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    response = requests.patch(url, headers=get_headers(), json={"email": email, "telephone": telephone})
    return _mutation_result(response, "Modification des coordonnées")

def delete_client(client_id):
    if not SUPABASE_KEY: return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}"
    response = requests.delete(url, headers=get_headers())
    return _mutation_result(response, "Suppression du dossier")

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

def get_rendez_vous_commerciaux():
    if not SUPABASE_KEY: return None
    url = f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?select=*&order=date_rdv.asc"
    response = requests.get(url, headers=get_headers())
    return response.json() if response.status_code == 200 else None

def _rendez_vous_payload(data):
    return {
        "client_id": data.get("client_id"),
        "nom": data.get("nom", "").strip().upper(),
        "prenom": data.get("prenom", "").strip(),
        "email": data.get("email", "").strip(),
        "telephone": data.get("telephone", "").strip(),
        "profil": data.get("profil", ""),
        "date_rdv": data.get("date_rdv"),
        "besoin": data.get("besoin", "").strip(),
        "statut": data.get("statut", "Demande reçue"),
        "prochaine_action": data.get("prochaine_action") or None,
        "type_prochaine_action": data.get("type_prochaine_action", ""),
        "commentaire": data.get("commentaire", "").strip(),
    }

def add_rendez_vous_commercial(data):
    if not SUPABASE_KEY:
        return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux"
    headers = get_headers()
    # L'ajout n'a pas besoin de relire la ligne créée (ce qui exigerait une
    # policy SELECT en plus de la policy INSERT).
    headers["Prefer"] = "return=minimal"
    response = requests.post(url, headers=headers, json=_rendez_vous_payload(data))
    if response.status_code in (200, 201, 204):
        return True, ""
    try:
        contenu = response.json()
        details = [contenu.get(cle) for cle in ("message", "details", "hint", "code") if contenu.get(cle)]
        explication = " — ".join(str(detail) for detail in details)
    except (ValueError, AttributeError):
        explication = ""
    return False, f"Supabase a refusé l’enregistrement (HTTP {response.status_code})" + (f" : {explication}" if explication else ".")

def update_rendez_vous_commercial(rendez_vous_id, data):
    if not SUPABASE_KEY: return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}"
    response = requests.patch(url, headers=get_headers(), json=_rendez_vous_payload(data))
    return _mutation_result(response, "Modification du rendez-vous commercial")

def delete_rendez_vous_commercial(rendez_vous_id):
    if not SUPABASE_KEY: return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}"
    response = requests.delete(url, headers=get_headers())
    return _mutation_result(response, "Suppression du rendez-vous commercial")

def add_compte_rendu_rendez_vous(rendez_vous_id, date_rdv, compte_rendu, type_echange="Autre"):
    if not SUPABASE_KEY:
        return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}&select=comptes_rendus"
    response = requests.get(url, headers=get_headers())
    if not response.ok:
        return _mutation_result(response, "Lecture des comptes rendus")
    lignes = response.json()
    if not lignes:
        return False, "Ce rendez-vous est introuvable."
    comptes_rendus = lignes[0].get("comptes_rendus") or []
    if not isinstance(comptes_rendus, list):
        comptes_rendus = []
    comptes_rendus.append({"date": date_rdv, "type": type_echange, "compte_rendu": compte_rendu.strip()})
    mise_a_jour = {"comptes_rendus": comptes_rendus}
    date_echange = datetime.strptime(date_rdv, "%Y-%m-%d").date()
    if type_echange == "Devis envoyé":
        mise_a_jour.update({
            "statut": "Offre envoyée",
            "prochaine_action": (date_echange + timedelta(days=7)).isoformat(),
            "type_prochaine_action": "Relancer",
        })
    elif type_echange == "Devis accepté":
        mise_a_jour.update({"statut": "Devis validé", "prochaine_action": None, "type_prochaine_action": ""})
    elif type_echange == "Client conservé":
        mise_a_jour.update({"statut": "Client conservé", "prochaine_action": None, "type_prochaine_action": ""})
    elif type_echange == "Contrats ajoutés":
        mise_a_jour.update({"statut": "Contrats ajoutés", "prochaine_action": None, "type_prochaine_action": ""})
    elif type_echange == "Client parti":
        mise_a_jour.update({
            "statut": "À reconquérir",
            "prochaine_action": (date_echange + timedelta(days=365)).isoformat(),
            "type_prochaine_action": "Recontacter",
        })
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}",
        headers=get_headers(),
        json=mise_a_jour,
    )
    return _mutation_result(response, "Enregistrement du compte rendu")

def update_compte_rendu_rendez_vous(rendez_vous_id, index, date_rdv, compte_rendu, type_echange):
    if not SUPABASE_KEY:
        return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}&select=comptes_rendus"
    response = requests.get(url, headers=get_headers())
    if not response.ok:
        return _mutation_result(response, "Lecture de l’historique")
    lignes = response.json()
    if not lignes:
        return False, "Ce suivi commercial est introuvable."
    comptes_rendus = lignes[0].get("comptes_rendus") or []
    if not isinstance(comptes_rendus, list) or index < 0 or index >= len(comptes_rendus):
        return False, "Cet échange est introuvable dans l’historique. Actualise la page puis réessaie."
    compte = dict(comptes_rendus[index])
    compte.update({"date": date_rdv, "type": type_echange, "compte_rendu": compte_rendu.strip()})
    comptes_rendus[index] = compte
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}",
        headers=get_headers(),
        json={"comptes_rendus": comptes_rendus},
    )
    return _mutation_result(response, "Modification de l’échange")

def delete_compte_rendu_rendez_vous(rendez_vous_id, index):
    if not SUPABASE_KEY:
        return False, "La connexion à Supabase n’est pas configurée sur le serveur."
    url = f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}&select=comptes_rendus"
    response = requests.get(url, headers=get_headers())
    if not response.ok:
        return _mutation_result(response, "Lecture de l’historique")
    lignes = response.json()
    if not lignes:
        return False, "Ce suivi commercial est introuvable."
    comptes_rendus = lignes[0].get("comptes_rendus") or []
    if not isinstance(comptes_rendus, list) or index < 0 or index >= len(comptes_rendus):
        return False, "Cet échange est introuvable dans l’historique. Actualise la page puis réessaie."
    comptes_rendus.pop(index)
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/rendez_vous_commerciaux?id=eq.{rendez_vous_id}",
        headers=get_headers(),
        json={"comptes_rendus": comptes_rendus},
    )
    return _mutation_result(response, "Suppression de l’échange")

import sqlite3
from datetime import datetime

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            prenom TEXT,
            email TEXT,
            telephone TEXT,
            commentaire TEXT,
            statut TEXT DEFAULT 'En attente'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contrats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            num_contrat TEXT,
            type_vehicule TEXT,
            date_effet TEXT,
            marque_vehicule TEXT,
            immatriculation TEXT,
            pieces_manquantes TEXT,
            pieces_initiales TEXT,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')

    cursor.execute("PRAGMA table_info(contrats)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'type_vehicule' not in columns:
        cursor.execute("ALTER TABLE contrats ADD COLUMN type_vehicule TEXT")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            date_heure TEXT,
            email TEXT,
            pieces TEXT,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')

    conn.commit()
    conn.close()

def add_client_avec_contrats(nom, prenom, email, telephone, commentaire, liste_contrats):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    nom_formatted = nom.strip().upper()
    prenom_formatted = prenom.strip().capitalize()

    cursor.execute('''
        INSERT INTO clients (nom, prenom, email, telephone, commentaire)
        VALUES (?, ?, ?, ?, ?)
    ''', (nom_formatted, prenom_formatted, email, telephone, commentaire))
    
    client_id = cursor.lastrowid

    for c in liste_contrats:
        pieces_str = ",".join(c.get('pieces', []))
        cursor.execute('''
            INSERT INTO contrats (client_id, num_contrat, type_vehicule, date_effet, marque_vehicule, immatriculation, pieces_manquantes, pieces_initiales)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, c.get('num_contrat'), c.get('type_vehicule'), c.get('date_effet'), c.get('marque'), c.get('immat'), pieces_str, pieces_str))

    conn.commit()
    conn.close()

def get_all_clients():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients')
    rows = cursor.fetchall()

    resultat = []
    maintenant = datetime.now()

    for r in rows:
        client_id, nom, prenom, email, tel, commentaire, statut = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        
        cursor.execute('SELECT id, num_contrat, type_vehicule, date_effet, marque_vehicule, immatriculation, pieces_manquantes, pieces_initiales FROM contrats WHERE client_id = ?', (client_id,))
        contrats_rows = cursor.fetchall()
        
        contrats = []
        for c in contrats_rows:
            contrats.append({
                "id": c[0],
                "num_contrat": c[1],
                "type_vehicule": c[2] or 'Voiture',
                "date_effet": c[3],
                "marque": c[4] or '',
                "immat": c[5] or '',
                "pieces_manquantes": c[6].split(',') if c[6] else [],
                "pieces_initiales": c[7].split(',') if c[7] else []
            })

        cursor.execute('SELECT date_heure FROM historique WHERE client_id = ? ORDER BY id DESC LIMIT 1', (client_id,))
        last_relance = cursor.fetchone()
        derniere_relance = last_relance[0] if last_relance else None

        niveau_urgence = 'neutre'
        texte_statut = 'En attente'

        if statut == 'Archivé':
            texte_statut = '📦 Archivé'
            niveau_urgence = 'archive'
        elif derniere_relance:
            try:
                date_r = datetime.strptime(derniere_relance, '%Y-%m-%d %H:%M:%S')
                jours_ecoules = (maintenant - date_r).days
                if jours_ecoules < 7:
                    texte_statut = 'Relance < 7j'
                    niveau_urgence = 'vert'
                elif 7 <= jours_ecoules < 14:
                    texte_statut = 'Relance > 7j'
                    niveau_urgence = 'orange'
                else:
                    texte_statut = 'Urgent à relancer'
                    niveau_urgence = 'rouge'
            except Exception:
                pass
        else:
            dates_eff = [c['date_effet'] for c in contrats if c['date_effet']]
            if dates_eff:
                min_date = min(dates_eff)
                try:
                    date_e = datetime.strptime(min_date, '%Y-%m-%d')
                    if (maintenant - date_e).days >= 7:
                        texte_statut = 'Urgent à relancer'
                        niveau_urgence = 'rouge'
                    else:
                        texte_statut = 'À relancer'
                        niveau_urgence = 'orange'
                except Exception:
                    pass

        resultat.append({
            "id": client_id,
            "nom": nom,
            "prenom": prenom,
            "email": email or '',
            "telephone": tel or '',
            "commentaire": commentaire or '',
            "statut": statut,
            "texte_statut": texte_statut,
            "niveau_urgence": niveau_urgence,
            "derniere_relance": derniere_relance,
            "contrats": contrats
        })

    conn.close()
    return resultat

def update_contrat_details(contrat_id, immat, pieces):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    pieces_str = ",".join(pieces)
    cursor.execute('''
        UPDATE contrats 
        SET immatriculation = ?, pieces_manquantes = ?
        WHERE id = ?
    ''', (immat, pieces_str, contrat_id))
    conn.commit()
    conn.close()

def update_commentaire(client_id, commentaire):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE clients SET commentaire = ? WHERE id = ?', (commentaire, client_id))
    conn.commit()
    conn.close()

def log_relance(client_id, email, pieces):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pieces_str = ",".join(pieces)
    cursor.execute('''
        INSERT INTO historique (client_id, date_heure, email, pieces)
        VALUES (?, ?, ?, ?)
    ''', (client_id, now_str, email, pieces_str))
    conn.commit()
    conn.close()

def get_historique(client_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT date_heure, email, pieces FROM historique WHERE client_id = ? ORDER BY id DESC', (client_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"date_heure": r[0], "email": r[1], "pieces": r[2].split(',')} for r in rows]

def update_statut(client_id, statut):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE clients SET statut = ? WHERE id = ?', (statut, client_id))
    conn.commit()
    conn.close()

def delete_client(client_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clients WHERE id = ?', (client_id,))
    cursor.execute('DELETE FROM contrats WHERE client_id = ?', (client_id,))
    cursor.execute('DELETE FROM historique WHERE client_id = ?', (client_id,))
    conn.commit()
    conn.close()

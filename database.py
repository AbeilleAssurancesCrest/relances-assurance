import sqlite3
import json
import os

DB_PATH = "database.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_PATH):
        open(DB_PATH, 'a').close()
        
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            email TEXT,
            telephone TEXT,
            statut TEXT DEFAULT 'En attente',
            derniere_relance TEXT,
            commentaire TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contrats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            num_contrat TEXT NOT NULL,
            type_vehicule TEXT,
            date_effet TEXT,
            marque TEXT,
            immat TEXT,
            pieces_manquantes TEXT,
            pieces_initiales TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            date_heure TEXT,
            email TEXT,
            pieces TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

def add_client_avec_contrats(nom, prenom, email, telephone, commentaire, liste_contrats):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO clients (nom, prenom, email, telephone, commentaire, statut)
        VALUES (?, ?, ?, ?, ?, 'En attente')
    ''', (nom, prenom, email, telephone, commentaire))
    client_id = cursor.lastrowid

    for c in liste_contrats:
        pieces_json = json.dumps(c.get('pieces', []))
        cursor.execute('''
            INSERT INTO contrats (client_id, num_contrat, type_vehicule, date_effet, marque, immat, pieces_manquantes, pieces_initiales)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, c['num_contrat'], c.get('type_vehicule', 'Voiture'), c['date_effet'], c.get('marque', ''), c.get('immat', ''), pieces_json, pieces_json))

    conn.commit()
    conn.close()

def update_contrat_details(contrat_id, immat, pieces):
    conn = get_connection()
    cursor = conn.cursor()
    pieces_json = json.dumps(pieces)
    cursor.execute('''
        UPDATE contrats 
        SET immat = ?, pieces_manquantes = ?
        WHERE id = ?
    ''', (immat, pieces_json, contrat_id))
    conn.commit()
    conn.close()

def update_commentaire(client_id, commentaire):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE clients SET commentaire = ? WHERE id = ?', (commentaire, client_id))
    conn.commit()
    conn.close()

def get_all_clients():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients ORDER BY id DESC')
    clients = [dict(row) for row in cursor.fetchall()]

    for cl in clients:
        cursor.execute('SELECT * FROM contrats WHERE client_id = ?', (cl['id'],))
        contrats_db = cursor.fetchall()
        
        contrats_list = []
        dossier_complet = True
        nb_jours_max = 0

        for c in contrats_db:
            c_dict = dict(c)
            c_dict['pieces_manquantes'] = json.loads(c_dict['pieces_manquantes']) if c_dict['pieces_manquantes'] else []
            c_dict['pieces_initiales'] = json.loads(c_dict['pieces_initiales']) if c_dict['pieces_initiales'] else []
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

        if cl['statut'] == 'Archivé':
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

    conn.close()
    return clients

def update_statut(client_id, statut):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE clients SET statut = ? WHERE id = ?', (statut, client_id))
    conn.commit()
    conn.close()

def delete_client(client_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clients WHERE id = ?', (client_id,))
    conn.commit()
    conn.close()

def log_relance(client_id, email, pieces):
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('UPDATE clients SET derniere_relance = ? WHERE id = ?', (now, client_id))
    cursor.execute('''
        INSERT INTO historique (client_id, date_heure, email, pieces)
        VALUES (?, ?, ?, ?)
    ''', (client_id, now, email, json.dumps(pieces)))
    conn.commit()
    conn.close()

def get_historique(client_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM historique WHERE client_id = ? ORDER BY id DESC', (client_id,))
    rows = cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['pieces'] = json.loads(d['pieces']) if d['pieces'] else []
        result.append(d)
    conn.close()
    return result

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    if DATABASE_URL:
        # Connexion Supabase / PostgreSQL sur Render
        return psycopg2.connect(DATABASE_URL)
    else:
        # Fallback local SQLite sur ton Mac
        import sqlite3
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Adaptation auto selon la BDD
    is_postgres = bool(DATABASE_URL)
    pk_type = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS clients (
            id {pk_type},
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            email TEXT,
            telephone TEXT,
            statut TEXT DEFAULT 'En attente',
            derniere_relance TEXT,
            commentaire TEXT
        )
    ''')
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS contrats (
            id {pk_type},
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

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS historique (
            id {pk_type},
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
    
    if DATABASE_URL:
        cursor.execute('''
            INSERT INTO clients (nom, prenom, email, telephone, commentaire, statut)
            VALUES (%s, %s, %s, %s, %s, 'En attente') RETURNING id
        ''', (nom, prenom, email, telephone, commentaire))
        client_id = cursor.fetchone()[0]

        for c in liste_contrats:
            pieces_json = json.dumps(c.get('pieces', []))
            cursor.execute('''
                INSERT INTO contrats (client_id, num_contrat, type_vehicule, date_effet, marque, immat, pieces_manquantes, pieces_initiales)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (client_id, c['num_contrat'], c.get('type_vehicule', 'Voiture'), c['date_effet'], c.get('marque', ''), c.get('immat', ''), pieces_json, pieces_json))
    else:
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
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f'''
        UPDATE contrats 
        SET immat = {placeholder}, pieces_manquantes = {placeholder}
        WHERE id = {placeholder}
    ''', (immat, pieces_json, contrat_id))
    conn.commit()
    conn.close()

def update_commentaire(client_id, commentaire):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f'UPDATE clients SET commentaire = {placeholder} WHERE id = {placeholder}', (commentaire, client_id))
    conn.commit()
    conn.close()

def get_all_clients():
    conn = get_connection()
    if DATABASE_URL:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()

    cursor.execute('SELECT * FROM clients ORDER BY id DESC')
    
    if DATABASE_URL:
        clients = [dict(row) for row in cursor.fetchall()]
    else:
        clients = [dict(row) for row in cursor.fetchall()]

    for cl in clients:
        placeholder = "%s" if DATABASE_URL else "?"
        cursor.execute(f'SELECT * FROM contrats WHERE client_id = {placeholder}', (cl['id'],))
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
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f'UPDATE clients SET statut = {placeholder} WHERE id = {placeholder}', (statut, client_id))
    conn.commit()
    conn.close()

def delete_client(client_id):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f'DELETE FROM clients WHERE id = {placeholder}', (client_id,))
    conn.commit()
    conn.close()

def log_relance(client_id, email, pieces):
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f'UPDATE clients SET derniere_relance = {placeholder} WHERE id = {placeholder}', (now, client_id))
    cursor.execute(f'''
        INSERT INTO historique (client_id, date_heure, email, pieces)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
    ''', (client_id, now, email, json.dumps(pieces)))
    conn.commit()
    conn.close()

def get_historique(client_id):
    conn = get_connection()
    if DATABASE_URL:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()

    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f'SELECT * FROM historique WHERE client_id = {placeholder} ORDER BY id DESC', (client_id,))
    rows = cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['pieces'] = json.loads(d['pieces']) if d['pieces'] else []
        result.append(d)
    conn.close()
    return result

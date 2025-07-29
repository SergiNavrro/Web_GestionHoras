import mysql.connector
from datetime import datetime
import os  # <-- AÑADIDO: Importamos la librería 'os'

# Función auxiliar para crear la conexión, evitando repetir el código.
import mysql.connector

def get_db_connection():
    conexion = mysql.connector.connect(
        host="sql7.freesqldatabase.com",
        user="sql7792522",
        password="IXStwXlpHx",
        database="sql7792522"
    )
    return conexion
	
def init():
    con = None
    try:
        # Para la inicialización, nos conectamos sin especificar la base de datos primero
        con = mysql.connector.connect(
            host="sql7.freesqldatabase.com",
            user="sql7792522",
            password="IXStwXlpHx"
        )
        cur = con.cursor()
        
        db_name = os.getenv('DB_NAME', 'sql7792522')
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cur.execute(f"USE {db_name}")

        cur.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                username VARCHAR(50) PRIMARY KEY,
                password VARCHAR(255) NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS administradores (
                username VARCHAR(50) PRIMARY KEY,
                password VARCHAR(255) NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS fichajes (
                username VARCHAR(50),
                tipo VARCHAR(50) NOT NULL,
                hora DATETIME NOT NULL,
                comentario VARCHAR(300),
                FOREIGN KEY (username) REFERENCES usuarios(username) ON DELETE CASCADE
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS resumen_horas_diarias (
                username VARCHAR(50),
                horas_diarias VARCHAR(100),
                FOREIGN KEY (username) REFERENCES usuarios(username) ON DELETE CASCADE
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS resumen_horas_totales (
                username VARCHAR(50),
                horas_totales VARCHAR(100),
                UNIQUE (username),
                FOREIGN KEY (username) REFERENCES usuarios(username) ON DELETE CASCADE
            )
        ''')
        con.commit()
        print("Base de datos inicializada")
    except Exception as e:
        print("Error inicializando la base de datos:", e)
    finally:
        if con:
            con.close()

def addUser(user):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = %s", (user['username'],))
        if cur.fetchone():
            return {"error": "El usuario ya existe"}
        cur.execute(
            "INSERT INTO usuarios (username, password) VALUES (%s, %s)",
            (user['username'], user['password'])
        )
        con.commit()
        return {"success": "Usuario creado"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()

def addAdmin(admin):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM administradores WHERE username = %s", (admin['username'],))
        if cur.fetchone():
            return {"error": "El administrador ya existe"}
        cur.execute(
            "INSERT INTO administradores (username, password) VALUES (%s, %s)",
            (admin['username'], admin['password'])
        )
        con.commit()
        return {"success": "Administrador creado"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()

def checkLogin(username, password, tipo):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor(dictionary=True)
        if not tipo:
            cur.execute("SELECT * FROM usuarios WHERE username = %s AND password = %s", (username, password))
        else:
            cur.execute("SELECT * FROM administradores WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        return user is not None
    finally:
        con.close()

def fichar(username, tipo):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor(dictionary=True)
        query = """
            INSERT INTO fichajes (username, tipo,hora)
            VALUES (%s, %s, NOW())
        """
        cur.execute(query, (username, tipo))
        con.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error en la base de datos: {err}")
        return False
    finally:
        con.close()

def listar_fichajes(username, fecha_busqueda=None):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor(dictionary=True)
        if fecha_busqueda:
            print(f"[MODEL - listar_fichajes] Buscando fichajes para '{username}' en la fecha {fecha_busqueda}")
            query = """
                SELECT tipo, hora, comentario
                FROM fichajes
                WHERE username = %s AND DATE(hora) = %s
                ORDER BY hora ASC
            """
            params = (username, fecha_busqueda)
        else:
            query = """
                SELECT tipo, hora, comentario
                FROM fichajes
                WHERE username = %s
                ORDER BY hora DESC
                LIMIT 4
            """
            params = (username,)
        cur.execute(query, params)
        resultados = cur.fetchall()
        return resultados
    except Exception as e:
        print("Error en listar_fichajes:", e)
        return []
    finally:
        con.close()

def obtener_horas(username):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor(dictionary=True)
        cur.execute("""
            SELECT horas_totales
            FROM resumen_horas_totales
            WHERE username = %s
        """, (username,))
        row = cur.fetchone()
        return row['horas_totales'] if row else None
    except Exception as e:
        print("Error listando horas_totales:", e)
        return None
    finally:
        con.close()

def insertar_horas_diarias(username, horas_calculadas_str):
    try:
        fecha_str, tiempo_str = horas_calculadas_str.split(' - ')
    except (ValueError, AttributeError):
        print(f"Error: El formato de horas_calculadas_str ('{horas_calculadas_str}') no es válido.")
        return False
    
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor(buffered=True)
        query_buscar = "SELECT horas_diarias FROM resumen_horas_diarias WHERE username = %s AND horas_diarias LIKE %s"
        patron_like = f"{fecha_str} - %"
        cur.execute(query_buscar, (username, patron_like))
        fila_existente = cur.fetchone()
        if fila_existente:
            print(f"[MODEL] Fila encontrada para {fecha_str}. Actualizando a: {horas_calculadas_str}")
            query_update = "UPDATE resumen_horas_diarias SET horas_diarias = %s WHERE username = %s AND horas_diarias = %s"
            cur.execute(query_update, (horas_calculadas_str, username, fila_existente[0]))
        else:
            print(f"[MODEL] No se encontró fila para {fecha_str}. Insertando nueva fila: {horas_calculadas_str}")
            query_insert = "INSERT INTO resumen_horas_diarias (username, horas_diarias) VALUES (%s, %s)"
            cur.execute(query_insert, (username, horas_calculadas_str))
        con.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error en la base de datos al insertar horas diarias: {err}")
        con.rollback()
        return False
    finally:
        con.close()

def insertar_horas_totales(username, horas_totales):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO resumen_horas_totales (username, horas_totales)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE horas_totales = VALUES(horas_totales)
        """, (username, horas_totales))
        con.commit()
        return True
    except Exception as e:
        print("Error insertando/actualizando horas:", e)
        return False
    finally:
        con.close()

def estado_fichaje(username):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor(dictionary=True)
        query = "SELECT tipo FROM fichajes WHERE username = %s ORDER BY hora DESC LIMIT 1"
        cur.execute(query, (username,))
        result = cur.fetchone()
        if result:
            return result['tipo']
        else:
            return None
    finally:
        con.close()

def ver_horas_diarias(username):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor(dictionary=True)
        query = "SELECT horas_diarias FROM resumen_horas_diarias WHERE username = %s ORDER BY horas_diarias DESC"
        cur.execute(query, (username,))
        resultados = cur.fetchall()
        return resultados
    except Exception as e:
        print(f"Error en ver_horas_diarias: {e}")
        return []
    finally:
        if con:
            con.close()

def insertar_comentario(username, hora, comentario):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor()
        query = "UPDATE fichajes SET comentario = %s WHERE username = %s AND hora = %s"
        print(f"[DEBUG MODELO] Intentando actualizar con: comentario='{comentario}', username='{username}', hora='{hora}'")
        cur.execute(query, (comentario, username, hora))
        if cur.rowcount == 0:
            print("[DEBUG MODELO] ¡Advertencia! La consulta UPDATE no modificó ninguna fila. ¿La hora y el usuario coinciden exactamente?")
            return {"status": "error", "message": "No se encontró el fichaje para actualizar. Revisa la hora."}
        con.commit()
        return {"status": "ok", "message": f"Comentario guardado: {comentario}"}
    except Exception as e:
        print(f"Error en guardar_comentario: {e}")
        if con:
            con.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if con:
            con.close()

def editar_jornada_admin(username, fecha_jornada, nuevos_fichajes):
    con = get_db_connection() # Usamos la función auxiliar
    try:
        cur = con.cursor()
        con.start_transaction()
        print(f"[MODEL] Iniciando actualización para {username} en la fecha {fecha_jornada}.")
        for tipo, nueva_hora in nuevos_fichajes.items():
            if not nueva_hora:
                print(f"[MODEL] Omitiendo el tipo '{tipo}' porque no tiene hora asignada.")
                continue
            nuevo_datetime_str = f"{fecha_jornada} {nueva_hora}"
            query_buscar = """
                SELECT COUNT(*) FROM fichajes
                WHERE username = %s AND tipo = %s AND DATE(hora) = %s
            """
            cur.execute(query_buscar, (username, tipo, fecha_jornada))
            if cur.fetchone()[0] > 0:
                print(f"[MODEL] Existe un fichaje para '{tipo}'. Actualizando a {nuevo_datetime_str}...")
                query_actualizar = """
                    UPDATE fichajes
                    SET hora = %s
                    WHERE username = %s AND tipo = %s AND DATE(hora) = %s
                """
                cur.execute(query_actualizar, (nuevo_datetime_str, username, tipo, fecha_jornada))
            else:
                print(f"[MODEL] No existe un fichaje para '{tipo}'. Insertando {nuevo_datetime_str}...")
                query_insertar = """
                    INSERT INTO fichajes (username, tipo, hora)
                    VALUES (%s, %s, %s)
                """
                cur.execute(query_insertar, (username, tipo, nuevo_datetime_str))
        con.commit()
        print("[MODEL] Transacción completada con éxito.")
        return True
    except mysql.connector.Error as err:
        print(f"[ERROR MODEL] Ocurrió un error en la transacción: {err}")
        con.rollback()
        return False
    finally:
        cur.close()
        con.close()

if __name__ == "__main__":
    # Es necesario definir las variables de entorno para que el __main__ funcione
    # o bien, confiar en los valores por defecto que hemos puesto.
    init()
    sergi = {"username": "Sergi", "password": "Sergi"}
    emily = {"username": "Emily", "password": "Emily"}
    juan = {"username": "Juan", "password": "Juan"}
    addUser(sergi)
    addUser(emily)
    addAdmin(juan)

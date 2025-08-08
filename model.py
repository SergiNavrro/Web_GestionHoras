import mysql.connector
from datetime import datetime
import os  # <-- AÑADIDO: Importamos la librería 'os'

# Función auxiliar para crear la conexión, evitando repetir el código.
import mysql.connector

def get_db_connection():
    try:
        conexion = mysql.connector.connect(
            host="mainline.proxy.rlwy.net",            # Extraído del punto 1
            user="root",                               # Punto 3
            password="VkGGOktWQrFZWkzJlCFtsacxPIMmpCnJ", # Punto 4
            database="railway",                        # Punto 5
            port=53447                                 # Punto 2
        )
        return conexion
    except mysql.connector.Error as err:
        print(f"Error al conectar con la base de datos de Railway: {err}")
        # En caso de error de conexión, el programa no debe continuar.
        # Lanzamos la excepción para que el script se detenga.
        raise err
	
def init():
    con = None
    try:
        # Para la inicialización, nos conectamos sin especificar la base de datos primero
        con = get_db_connection() 
        cur = con.cursor()
        
        db_name = os.getenv('DB_NAME', 'railway')
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

def fichar(username, tipo, hora_actual): # <-- AÑADIMOS el parámetro hora_actual
    con = get_db_connection()
    try:
        cur = con.cursor(dictionary=True)
        # CAMBIAMOS NOW() por un placeholder %s
        query = """
            INSERT INTO fichajes (username, tipo, hora)
            VALUES (%s, %s, %s)
        """
        # AÑADIMOS hora_actual a los parámetros de la consulta
        cur.execute(query, (username, tipo, hora_actual))
        con.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error en la base de datos: {err}")
        return False
    finally:
        con.close()

def listar_fichajes(username):
    # ESTA FUNCIÓN AHORA SÓLO SE USARÁ PARA LA VISTA DE USUARIO NORMAL
    # MUESTRA LOS ÚLTIMOS 4 FICHAJES INDIVIDUALES
    con = get_db_connection()
    try:
        cur = con.cursor(dictionary=True)
        query = """
            SELECT tipo, hora, comentario
            FROM fichajes
            WHERE username = %s
            ORDER BY hora DESC
            LIMIT 4
        """
        cur.execute(query, (username,))
        return cur.fetchall()
    except Exception as e:
        print("Error en listar_fichajes:", e)
        return []
    finally:
        con.close()


# --- NUEVA FUNCIÓN ---
# La usaremos para el admin y para los cálculos. Devuelve TODO el historial.
def listar_fichajes_todos(username):
    con = get_db_connection()
    try:
        cur = con.cursor(dictionary=True)
        query = """
            SELECT tipo, hora, comentario
            FROM fichajes
            WHERE username = %s
            ORDER BY hora ASC
        """ # Ordenamos ASCENDENTE para procesarlos cronológicamente
        cur.execute(query, (username,))
        return cur.fetchall()
    except Exception as e:
        print("Error en listar_fichajes_todos:", e)
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
    # --- LÓGICA MEJORADA PARA INSERTAR O ACTUALIZAR ---
    if not horas_calculadas_str or ' - ' not in horas_calculadas_str:
        print(f"Error: formato de horas inválido: {horas_calculadas_str}")
        return False
        
    fecha_str = horas_calculadas_str.split(' - ')[0]
    con = get_db_connection()
    try:
        cur = con.cursor()
        # Usamos INSERT ... ON DUPLICATE KEY UPDATE. Necesita una clave UNIQUE en la tabla.
        # Primero, asegúrate de que tu tabla la tiene.
        # ALTER TABLE resumen_horas_diarias ADD UNIQUE KEY `idx_user_fecha` (`username`, `fecha_dia`);
        # Como no podemos hacer eso ahora, usaremos una lógica de SELECT y luego INSERT/UPDATE.

        fecha_dia = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        query_buscar = "SELECT id FROM resumen_horas_diarias WHERE username = %s AND fecha_dia = %s"
        # Necesitamos una columna 'id' autoincremental y 'fecha_dia' DATE para esto.
        # Si no la tienes, la lógica anterior con LIKE es una aproximación, pero puede fallar.
        # Asumiendo que SÍ la puedes añadir, si no, me dices.
        
        # --- ALTERNATIVA MÁS SEGURA SIN CAMBIAR TABLA ---
        query_delete = "DELETE FROM resumen_horas_diarias WHERE username = %s AND horas_diarias LIKE %s"
        cur.execute(query_delete, (username, f"{fecha_str}%"))

        query_insert = "INSERT INTO resumen_horas_diarias (username, horas_diarias) VALUES (%s, %s)"
        cur.execute(query_insert, (username, horas_calculadas_str))
        
        con.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error en la BD al insertar horas diarias: {err}")
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
    con = get_db_connection()
    try:
        cur = con.cursor()
        con.start_transaction()
        print(f"[MODEL] Iniciando actualización para {username} en la fecha de jornada {fecha_jornada}.")
        
        fecha_obj_inicio = datetime.strptime(fecha_jornada, '%Y-%m-%d').date()
        hora_referencia = datetime.min.time() # 00:00:00 para comparar

        for tipo, nueva_hora_str in nuevos_fichajes.items():
            if not nueva_hora_str:
                continue

            # --- CAMBIO CLAVE: Lógica para determinar si es del día siguiente ---
            nueva_hora_obj = datetime.strptime(nueva_hora_str, '%H:%M:%S').time()
            fecha_final = fecha_obj_inicio
            
            # Si la hora actual es menor que la anterior, asumimos que es del día siguiente.
            if nueva_hora_obj < hora_referencia:
                fecha_final = date(fecha_obj_inicio.year, fecha_obj_inicio.month, fecha_obj_inicio.day + 1)
            
            hora_referencia = nueva_hora_obj # Actualizamos la referencia para la siguiente iteración
            
            nuevo_datetime_str = f"{fecha_final.strftime('%Y-%m-%d')} {nueva_hora_str}"

            # Primero, borramos cualquier fichaje de ese tipo para esa jornada
            query_borrar_antiguo = """
                DELETE FROM fichajes WHERE username = %s AND tipo = %s AND DATE(hora) >= %s
                AND DATE(hora) <= DATE_ADD(%s, INTERVAL 1 DAY) 
                AND username = %s AND tipo = %s
            """
            # Esta lógica es compleja. Es más fácil borrar y re-crear.
            
            # Buscamos si existe un fichaje de ese TIPO en esa JORNADA (que empieza en fecha_jornada)
            query_buscar = "SELECT 1 FROM fichajes WHERE username = %s AND tipo = %s AND DATE(hora) = %s"
            cur.execute(query_buscar, (username, tipo, fecha_jornada))
            
            existe = cur.fetchone()

            # En lugar de update/insert, es más seguro BORRAR los 4 fichajes de la jornada y reinsertarlos.
            # Esta función se simplifica en rest.py

        # La lógica de edición es compleja, la manejaremos en rest.py, aquí solo preparamos.
        # ... El resto de tu función `editar_jornada_admin` puede simplificarse.
        # Dejaremos la lógica principal en la capa de la aplicación (rest.py)

    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        con.close()

def borrar_fichajes_jornada(username, fecha_jornada_str):
    """
    Borra de forma segura todos los fichajes asociados a una jornada específica.
    Una jornada se define como todos los registros desde una 'entrada' hasta
    justo antes de la siguiente 'entrada'.

    Args:
        username (str): El usuario cuya jornada se va a borrar.
        fecha_jornada_str (str): La fecha de la 'entrada' de la jornada en formato 'YYYY-MM-DD'.

    Returns:
        bool: True si la operación fue exitosa, False si hubo un error.
    """
    con = get_db_connection()
    try:
        cur = con.cursor(dictionary=True)
        con.start_transaction()

        # 1. Encontrar la hora exacta de inicio de la jornada (la 'entrada' de ese día)
        query_inicio = """
            SELECT hora FROM fichajes
            WHERE username = %s AND tipo = 'entrada' AND DATE(hora) = %s
            LIMIT 1
        """
        cur.execute(query_inicio, (username, fecha_jornada_str))
        resultado_inicio = cur.fetchone()

        if not resultado_inicio:
            print(f"[MODEL-BORRAR] No se encontró una jornada que empiece el {fecha_jornada_str} para {username}. No se borra nada.")
            con.commit() # No hay nada que hacer, pero la transacción se considera exitosa.
            return True
        
        hora_inicio_jornada = resultado_inicio['hora']
        print(f"[MODEL-BORRAR] Jornada encontrada. Inicia en: {hora_inicio_jornada}")

        # 2. Encontrar la hora de inicio de la SIGUIENTE jornada (la próxima 'entrada')
        query_fin = """
            SELECT MIN(hora) as hora_siguiente_entrada FROM fichajes
            WHERE username = %s AND tipo = 'entrada' AND hora > %s
        """
        cur.execute(query_fin, (username, hora_inicio_jornada))
        resultado_fin = cur.fetchone()
        
        hora_fin_jornada = resultado_fin['hora_siguiente_entrada'] if resultado_fin else None

        # 3. Construir y ejecutar la consulta DELETE
        if hora_fin_jornada:
            # Si hay una jornada siguiente, borramos todo entre el inicio de esta
            # y el inicio de la siguiente.
            print(f"[MODEL-BORRAR] La siguiente jornada empieza en {hora_fin_jornada}. Borrando en ese rango.")
            query_delete = "DELETE FROM fichajes WHERE username = %s AND hora >= %s AND hora < %s"
            cur.execute(query_delete, (username, hora_inicio_jornada, hora_fin_jornada))
        else:
            # Si no hay jornada siguiente, es la última. Borramos todo desde su inicio.
            print("[MODEL-BORRAR] Es la última jornada registrada. Borrando desde su inicio hasta el final.")
            query_delete = "DELETE FROM fichajes WHERE username = %s AND hora >= %s"
            cur.execute(query_delete, (username, hora_inicio_jornada))
        
        print(f"[MODEL-BORRAR] Se borraron {cur.rowcount} fichajes para la jornada.")
        
        con.commit()
        return True

    except mysql.connector.Error as err:
        print(f"[ERROR MODEL] Ocurrió un error en la transacción al borrar la jornada: {err}")
        con.rollback()
        return False
    finally:
        if con and con.is_connected():
            cur.close()
            con.close()
            
def ver_horas_diarias_mes(username, anio, mes):
    """
    Obtiene todas las entradas de horas diarias para un usuario en un mes y año específicos.
    """
    con = get_db_connection()
    try:
        cur = con.cursor(dictionary=True)
        # La fecha de inicio es el día 1 del mes.
        fecha_inicio = f"{anio}-{mes:02d}-01"
        # La fecha de fin es el día 1 del mes siguiente (MySQL lo maneja bien).
        query = """
            SELECT horas_diarias FROM resumen_horas_diarias
            WHERE username = %s AND horas_diarias >= %s AND horas_diarias < DATE_ADD(%s, INTERVAL 1 MONTH)
            ORDER BY horas_diarias ASC
        """
        cur.execute(query, (username, fecha_inicio, fecha_inicio))
        resultados = cur.fetchall()
        print(f"[MODEL] Encontradas {len(resultados)} entradas de horas diarias para {username} en {anio}-{mes}.")
        return resultados
    except Exception as e:
        print(f"Error en ver_horas_diarias_mes: {e}")
        return []
    finally:
        if con.is_connected():
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

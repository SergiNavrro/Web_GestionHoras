import mysql.connector
from datetime import datetime

def init():
    con = None
    try:
        con = mysql.connector.connect(user='root', password='Root123!')  # Ajusta user/pass si hace falta
        cur = con.cursor()

        cur.execute("CREATE DATABASE IF NOT EXISTS paqui")
        cur.execute("USE paqui")

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

# Función para añadir usuario
def addUser(user):
    con = mysql.connector.connect(user='root', password='Root123!', database='paqui')
    try:
        cur = con.cursor()
        # Primero comprobamos si ya existe el usuario
        cur.execute("SELECT * FROM usuarios WHERE username = %s", (user['username'],))
        if cur.fetchone():
            return {"error": "El usuario ya existe"}

        # Si no existe, insertamos
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

# Función para añadir administrador
def addAdmin(admin):
    con = mysql.connector.connect(user='root', password='Root123!', database='paqui')
    try:
        cur = con.cursor()
        # Primero comprobamos si ya existe el administrador
        cur.execute("SELECT * FROM administradores WHERE username = %s", (admin['username'],))
        if cur.fetchone():
            return {"error": "El administrador ya existe"}

        # Si no existe, insertamos
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

# Función para comprobar login
def checkLogin(username, password, tipo):
    con = mysql.connector.connect(user="root", password="Root123!", host="localhost", database="paqui")
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
    """
    Inserta un nuevo fichaje separando la fecha y la hora en sus respectivas columnas.
    """
    con = mysql.connector.connect(user="root", password="Root123!", host="localhost", database="paqui")
    try:
        cur = con.cursor(dictionary=True)
        # La consulta ahora inserta en las columnas 'fecha' y 'hora'
        # usando las funciones nativas de MySQL CURDATE() y CURTIME()
        query = """
            INSERT INTO fichajes (username, tipo,hora)
            VALUES (%s, %s, NOW())
        """
        cur.execute(query, (username, tipo))
        con.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error en la base de datos: {err}")
        # Opcional: registrar el error o manejarlo de otra forma
        return False
    finally:
        con.close()

def listar_fichajes(username, fecha_busqueda=None):
    """
    Lista los fichajes de un usuario. Es una función dual:
    - Si no se proporciona 'fecha_busqueda', devuelve los últimos 4 fichajes (para el usuario).
    - Si se proporciona 'fecha_busqueda' (en formato 'YYYY-MM-DD'), devuelve todos los
      fichajes de ese día (para recálculos del admin).
    """
    con = mysql.connector.connect(user='root', password='Root123!', database='paqui')
    try:
        cur = con.cursor(dictionary=True)

        if fecha_busqueda:
            # --- COMPORTAMIENTO PARA BUSCAR POR FECHA (ADMIN) ---
            print(f"[MODEL - listar_fichajes] Buscando fichajes para '{username}' en la fecha {fecha_busqueda}")
            query = """
                SELECT tipo, hora, comentario 
                FROM fichajes 
                WHERE username = %s AND DATE(hora) = %s
                ORDER BY hora ASC
            """
            params = (username, fecha_busqueda)
        else:
            # --- COMPORTAMIENTO POR DEFECTO (USER) ---
            # print(f"[MODEL - listar_fichajes] Buscando últimos 4 fichajes para '{username}'")
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
    con = mysql.connector.connect(user='root', password='Root123!', database='paqui')
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

# En model.py

def insertar_horas_diarias(username, horas_calculadas_str):
    """
    Inserta o actualiza el resumen de horas para un día específico,
    manteniendo solo dos columnas en la tabla. La unicidad se gestiona
    mediante código.
    """
    
    # 1. Extraemos la fecha y la hora de la cadena 'YYYY-MM-DD - HH:MM:SS'
    try:
        fecha_str, tiempo_str = horas_calculadas_str.split(' - ')
    except (ValueError, AttributeError):
        print(f"Error: El formato de horas_calculadas_str ('{horas_calculadas_str}') no es válido.")
        return False

    con = mysql.connector.connect(user='root', password='Root123!', database='paqui')
    try:
        # Usamos un cursor con buffer para poder hacer múltiples execute sin problemas
        cur = con.cursor(buffered=True) 

        # 2. Buscamos si ya existe una entrada para ESE DÍA.
        #    Usamos LIKE para buscar cualquier fila que COMIENCE con la fecha del día.
        #    La consulta es 'SELECT horas_diarias FROM... WHERE username='...' AND horas_diarias LIKE 'YYYY-MM-DD %'
        query_buscar = "SELECT horas_diarias FROM resumen_horas_diarias WHERE username = %s AND horas_diarias LIKE %s"
        
        # El patrón de búsqueda será la fecha seguida de un espacio, un guion y un comodín '%'
        # Esto encontrará '2024-05-30 - 08:00:00', '2024-05-30 - 07:59:10', etc.
        patron_like = f"{fecha_str} - %"
        
        cur.execute(query_buscar, (username, patron_like))
        
        fila_existente = cur.fetchone()

        if fila_existente:
            # 3. Si existe, hacemos un UPDATE.
            #    Actualizamos la fila encontrada, reemplazando la antigua cadena con la nueva.
            print(f"[MODEL] Fila encontrada para {fecha_str}. Actualizando a: {horas_calculadas_str}")
            query_update = "UPDATE resumen_horas_diarias SET horas_diarias = %s WHERE username = %s AND horas_diarias = %s"
            # Identificamos la fila a actualizar por su contenido exacto anterior.
            cur.execute(query_update, (horas_calculadas_str, username, fila_existente[0]))

        else:
            # 4. Si no existe, hacemos un INSERT.
            print(f"[MODEL] No se encontró fila para {fecha_str}. Insertando nueva fila: {horas_calculadas_str}")
            query_insert = "INSERT INTO resumen_horas_diarias (username, horas_diarias) VALUES (%s, %s)"
            cur.execute(query_insert, (username, horas_calculadas_str))

        con.commit()
        return True

    except mysql.connector.Error as err:
        print(f"Error en la base de datos al insertar horas diarias: {err}")
        con.rollback() # Si algo falla, deshacemos para evitar inconsistencias
        return False
    finally:
        con.close()

def insertar_horas_totales(username, horas_totales):
    con = mysql.connector.connect(user="root", password="Root123!", host="localhost", database="paqui")
    try:
        cur = con.cursor()
        # Insertar o actualizar en la misma operación
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
    # La conexión debe estar definida en algún sitio, la incluyo aquí por claridad
    con = mysql.connector.connect(user="root", password="Root123!", host="localhost", database="paqui")
    try:
        cur = con.cursor(dictionary=True)

        query = "SELECT tipo FROM fichajes WHERE username = %s ORDER BY hora DESC LIMIT 1"
        cur.execute(query, (username,))
        result = cur.fetchone()

        if result:
            # Si se encuentra un resultado, devolvemos el valor de la columna 'tipo'.
            # Por ejemplo: 'parada_cenar'
            return result['tipo']
        else:
            # Si no hay ningún fichaje para ese usuario, devolvemos None.
            return None

    finally:
        con.close()
        
def ver_horas_diarias(username):
    con = None
    try:
        con = mysql.connector.connect(user='root', password='Root123!', database='paqui')

        cur = con.cursor(dictionary=True)

        query = "SELECT horas_diarias FROM resumen_horas_diarias WHERE username = %s ORDER BY horas_diarias DESC"
        
        # Ejecutamos la consulta de forma segura con un parámetro.
        cur.execute(query, (username,))
        
        # Recogemos todos los resultados encontrados.
        resultados = cur.fetchall()
        
        return resultados
    except Exception as e:
        # Si algo sale mal, imprimimos el error y devolvemos una lista vacía.
        print(f"Error en ver_horas_diarias: {e}")
        return []
    finally:
        # Nos aseguramos de que la conexión se cierre siempre.
        if con:
            con.close()

def insertar_comentario(username, hora, comentario):
    con = None
    try:
        con = mysql.connector.connect(user='root', password='Root123!', database='paqui')
        cur = con.cursor()

        query = "UPDATE fichajes SET comentario = %s WHERE username = %s AND hora = %s"
        
        print(f"[DEBUG MODELO] Intentando actualizar con: comentario='{comentario}', username='{username}', hora='{hora}'")

        cur.execute(query, (comentario, username, hora))
        
        # Comprobamos si la actualización afectó a alguna fila
        if cur.rowcount == 0:
            print("[DEBUG MODELO] ¡Advertencia! La consulta UPDATE no modificó ninguna fila. ¿La hora y el usuario coinciden exactamente?")
            return {"status": "error", "message": "No se encontró el fichaje para actualizar. Revisa la hora."}

        con.commit()
        
        # El f-string en la clave del diccionario es un poco raro, lo corrijo
        return {"status": "ok", "message": f"Comentario guardado: {comentario}"}

    except Exception as e:
        print(f"Error en guardar_comentario: {e}")
        # Si hay un error, es buena idea hacer rollback para deshacer cambios parciales
        if con:
            con.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if con:
            con.close()
            
def editar_jornada_admin(username, fecha_jornada, nuevos_fichajes):
    """
    Actualiza o inserta los fichajes de una jornada completa para un usuario.

    Esta función opera en una transacción: o se actualizan/insertan todos los fichajes 
    correctamente, o no se hace ningún cambio.

    Args:
        username (str): El nombre de usuario a modificar.
        fecha_jornada (str): La fecha de la jornada en formato 'YYYY-MM-DD'.
        nuevos_fichajes (dict): Un diccionario con los tipos de fichaje como clave 
                                y las nuevas horas ('HH:MM:SS') como valor.
                                Ejemplo: {'entrada': '08:00:00', 'salida': '17:00:00', ...}

    Returns:
        bool: True si la operación fue exitosa, False en caso de error.
    """

    con = mysql.connector.connect(user="root", password="Root123!", host="localhost", database="paqui")
    try:
        cur = con.cursor()

        # Iniciar una transacción. Esto es CRUCIAL para la integridad de los datos.
        con.start_transaction()

        print(f"[MODEL] Iniciando actualización para {username} en la fecha {fecha_jornada}.")

        # Iteramos sobre cada fichaje que nos llega del frontend (entrada, parada_cenar, etc.)
        for tipo, nueva_hora in nuevos_fichajes.items():

            # Si el admin borró la hora en el formulario, nos llegará un string vacío. Lo ignoramos.
            if not nueva_hora:
                print(f"[MODEL] Omitiendo el tipo '{tipo}' porque no tiene hora asignada.")
                continue

            # Construimos el DATETIME completo combinando la fecha de la jornada y la nueva hora
            nuevo_datetime_str = f"{fecha_jornada} {nueva_hora}"

            # --- Lógica de UPDATE o INSERT ---

            # 1. Buscamos si ya existe un fichaje de este TIPO en esta FECHA para este USUARIO.
            #    Usamos DATE(hora) para comparar solo la fecha.
            query_buscar = """
                SELECT COUNT(*) FROM fichajes 
                WHERE username = %s AND tipo = %s AND DATE(hora) = %s
            """
            cur.execute(query_buscar, (username, tipo, fecha_jornada))

            # cur.fetchone()[0] nos da el resultado del COUNT(*) (0 o 1)
            if cur.fetchone()[0] > 0:
                # 2. Si existe (COUNT > 0), hacemos un UPDATE.
                #    Actualizamos el campo 'hora' con el nuevo DATETIME completo.
                print(f"[MODEL] Existe un fichaje para '{tipo}'. Actualizando a {nuevo_datetime_str}...")
                query_actualizar = """
                    UPDATE fichajes 
                    SET hora = %s
                    WHERE username = %s AND tipo = %s AND DATE(hora) = %s
                """
                cur.execute(query_actualizar, (nuevo_datetime_str, username, tipo, fecha_jornada))
            else:
                # 3. Si no existe (COUNT = 0), hacemos un INSERT.
                print(f"[MODEL] No existe un fichaje para '{tipo}'. Insertando {nuevo_datetime_str}...")
                query_insertar = """
                    INSERT INTO fichajes (username, tipo, hora) 
                    VALUES (%s, %s, %s)
                """
                cur.execute(query_insertar, (username, tipo, nuevo_datetime_str))

        # Si todo ha ido bien, confirmamos todos los cambios en la base de datos
        con.commit()
        print("[MODEL] Transacción completada con éxito.")
        return True

    except mysql.connector.Error as err:
        # Si algo falla en cualquiera de las consultas (UPDATE o INSERT),
        # deshacemos TODOS los cambios realizados en esta transacción.
        print(f"[ERROR MODEL] Ocurrió un error en la transacción: {err}")
        con.rollback()
        return False

    finally:
        # Siempre cerramos la conexión al finalizar.
        cur.close()
        con.close()
# Ejecutar si se lanza directamente
if __name__ == "__main__":
    init()
    sergi = {"username": "Sergi", "password": "Sergi"}
    emily = {"username": "Emily", "password": "Emily"}
    juan = {"username": "Juan", "password": "Juan"}

    addUser(sergi)
    addUser(emily)
    addAdmin(juan)


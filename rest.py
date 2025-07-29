from flask import Flask, request, jsonify, render_template, session
import model  # Tu archivo model.py
from datetime import datetime, date, timezone
import pytz


app = Flask(__name__)
app.secret_key = 'clave_secreta_segura'  # Cambia esto por una clave segura en producción

user = False
admin = False

@app.route('/')
def home():
    return render_template("2index.html")  # Asegúrate de tenerlo en la carpeta templates

# Recibe si el botón pulsado ha sido admin o user
@app.route('/web_seguimiento/admin_user', methods=['POST'])
def inicio():
    global user, admin
    data = request.get_json()

    if data == 'user':
        user = True
        admin = False
        return jsonify({"message": "Botón pulsado: user"})
    elif data == 'admin':
        admin = True
        user = False
        return jsonify({"message": "Botón pulsado: admin"})
    else:
        return jsonify({"error": "Tipo inválido"}), 401


# Esta función determina cuál es el siguiente paso lógico basado en el último fichaje.
def determinar_siguiente_estado(username):
    ultimo_tipo = model.estado_fichaje(username)
    print(f"DEBUG: El último fichaje fue {ultimo_tipo}")
    if not ultimo_tipo:
        return 'entrada'

    secuencia = {
        'entrada': 'parada_cenar',
        'parada_cenar': 'salida_cenar',
        'salida_cenar': 'salida',
        'salida': 'finalizado'  # Un estado para indicar que la jornada ha terminado
    }

    # Devuelve el siguiente estado en la secuencia, o 'entrada' si algo va mal.
    return secuencia.get(ultimo_tipo, 'entrada')


@app.route('/web_seguimiento/login', methods=['POST'])
def login():
    global user, admin # Necesitamos leer estas variables globales

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Faltan datos"}), 400
    
    # La variable 'admin' (que es True o False) nos dice qué tipo de login es.
    # Se la pasamos a la función de chequeo.
    es_login_admin = admin

    # Ahora la llamada a la base de datos está separada y es clara.
    # checkLogin nos dirá si el usuario/contraseña es válido para ese tipo.
    login_valido = model.checkLogin(username, password, es_login_admin)

    # --- LÓGICA DE DECISIÓN CORREGIDA Y CLARA ---
    if login_valido:
        # Si el login es válido, guardamos la sesión.
        session['username'] = username
        session['tipo'] = 'admin' if es_login_admin else 'user'
        
        if es_login_admin:
            # Si era un admin, devolvemos la respuesta de admin.
            return jsonify({"status": "ok", "message": "Login exitoso del admin"})
        else:
            # Si era un usuario, calculamos su estado y devolvemos la respuesta de user.
            siguiente_estado = determinar_siguiente_estado(username)
            return jsonify({
                "status": "ok",
                "message": "Login exitoso del user",
                "siguiente_estado": siguiente_estado
            })
    else:
        # Si login_valido fue False, devolvemos error. Esto ahora funciona para AMBOS.
        return jsonify({"status": "error", "message": "Usuario o contraseña incorrectos"}), 401

@app.route('/web_seguimiento/area_privada')
def area_privada():
    if 'username' not in session:
        return "Acceso denegado. Inicia sesión.", 401
    return f"Hola {session['username']}, estás logueado como {session['tipo']}"

@app.route('/fichar/<username>', methods=['POST'])
def fichar_lista(username):
    data = request.get_json()
    tipo = data.get('boton_fichar')

    if tipo != 'listar':
        # --- ESTA ES LA PARTE IMPORTANTE ---
        # 1. Definimos la zona horaria correcta
        zona_horaria_madrid = pytz.timezone('Europe/Madrid')
        
        # 2. Obtenemos la hora actual en esa zona horaria
        hora_actual = datetime.now(zona_horaria_madrid)
        print(f"HORRAA ACUTAL ESSSS {hora_actual}")
        # 3. Llamamos a la función del modelo con la hora generada
        model.fichar(username, tipo, hora_actual)

    fichajes = model.listar_fichajes(username)
    print(f"Resultado del botón {tipo}")
    print(f"Fichajes devueltos para {username}: {fichajes}")

    if tipo == 'salida':
        hora_diaria = calcular_horas(fichajes)
        horas_totales = model.obtener_horas(username)
        print(f"Horas tablas totales {horas_totales}")
        if horas_totales == None:
            horas_totales_calculadas = hora_diaria
            print(f"HORAS TOTALES = {horas_totales_calculadas}, HORA DIARIA = {hora_diaria}")
        else:
            horas_totales_calculadas = sumar_horas_totales(hora_diaria, horas_totales)

        model.insertar_horas_diarias(username, hora_diaria)
        model.insertar_horas_totales(username, horas_totales_calculadas)

    return jsonify({"fichajes": fichajes})

# Ruta para consultar el estado (ahora corregida)
@app.route('/estado/<username>', methods=['GET'])
def estado_actual(username):
    # La llamada correcta debería ser a tu módulo de modelo
    ultimo_tipo = model.estado_fichajes(username)
    return jsonify({"ultimo_tipo": ultimo_tipo})

# Ruta para consultar el estado (ahora corregida)
'''@app.route('/hora/<username>', methods=['GET'])
def trabajo_actual(username):
    global hora_diaria
    # La llamada correcta debería ser a tu módulo de modelo
    hora = hora_diaria
    return jsonify({"Horas trabajas": hora})
'''

# --- FUNCIÓN LOGOUT CORREGIDA ---
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "ok", "message": "Sesión cerrada"})

def sumar_horas_totales(hora_diaria, horas_totales):
    # Extraer solo la parte de hora: 'HH:MM:SS'
    print(f"[FUNCION SUMAR HORAS] DIARIA {hora_diaria}, total {horas_totales}")
    tiempo1 = hora_diaria.split(" - ")[1]
    tiempo2 = horas_totales.split(" - ")[1]

    # Convertir a horas, minutos y segundos
    h1, m1, s1 = map(int, tiempo1.split(":"))
    h2, m2, s2 = map(int, tiempo2.split(":"))

    # Sumar
    total_segundos = s1 + s2
    total_minutos = m1 + m2
    total_horas = h1 + h2

    # Ajustar si hay desbordes
    if total_segundos >= 60:
        total_minutos += total_segundos // 60
        total_segundos %= 60

    if total_minutos >= 60:
        total_horas += total_minutos // 60
        total_minutos %= 60

    # Mantener formato 'YYYY-MM-DD - HH:MM:SS'
    fecha = date.today()
    resultado = f"{fecha} - {total_horas:02d}:{total_minutos:02d}:{total_segundos:02d}"
    print(f"[DEBUG] Total acumulado: {resultado}")
    return resultado

            
def calcular_horas(fichajes):
    entrada = parada_cena = salida_cena = salida = None

    for fichaje in fichajes:
        if fichaje['tipo'] == 'entrada':
            entrada = fichaje['hora']
        elif fichaje['tipo'] == 'parada_cenar':
            parada_cena = fichaje['hora']
        elif fichaje['tipo'] == 'salida_cenar':
            salida_cena = fichaje['hora']
        elif fichaje['tipo'] == 'salida':
            salida = fichaje['hora']

    if not all([entrada, parada_cena, salida_cena, salida]):
        print("Faltan fichajes")
        return None

    h1, m1, s1 = restar_horas_manual(entrada, parada_cena)
    h2, m2, s2 = restar_horas_manual(salida_cena, salida)

    total_segundos = s1 + s2
    total_minutos = m1 + m2
    total_horas = h1 + h2
    #pasar segunod->minutos/minutos->horas si sobrepasan
    if total_segundos >= 60:
        total_minutos += total_segundos // 60
        total_segundos %= 60

    if total_minutos >= 60:
        total_horas += total_minutos // 60
        total_minutos %= 60

    print(f"HORAS: {total_horas}, MINUTOS: {total_minutos}, SEGUNDOS{total_segundos}")
    fecha = date.today()
    hora_diaria = f"{fecha} - {total_horas:02d}:{total_minutos:02d}:{total_segundos:02d}"
    print(f"[DEBUG] HORA DIARIA CALCULADA-> {hora_diaria}")
    return hora_diaria

def horas_totales(): pass

def restar_horas_manual(inicio, fin):
    if fin < inicio:
        raise ValueError("La hora de fin no puede ser menor que la de inicio")

    horas = fin.hour - inicio.hour
    minutos = fin.minute - inicio.minute
    segundos = fin.second - inicio.second
    #sino estan en el mismos egundo/minuto
    if segundos < 0:
        segundos += 60
        minutos -= 1

    if minutos < 0:
        minutos += 60
        horas -= 1

    return horas, minutos, segundos


def logout():
    session.clear()
    return "Sesión cerrada"



# --- NUEVA RUTA para ver el resumen de horas diarias ---
@app.route('/horas_diarias/<username>', methods=['GET'])
def get_horas_diarias(username):
    if 'username' not in session or session['username'] != username:
        return jsonify({"status": "error", "message": "No autorizado"}), 401
    
    # Llamamos a la nueva función del modelo
    resumen = model.ver_horas_diarias(username)
    
    # formateamos la salida para que sea fácil de usar en JS
    # La función del modelo ya devuelve una lista de diccionarios, perfecto.
    return jsonify({"status": "ok", "resumen": resumen})


# --- RUTA PARA AÑADIR/EDITAR COMENTARIO (CORREGIDA PARA FORMATEAR LA FECHA) ---
@app.route('/comentario', methods=['POST'])
def anadir_comentario():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No se recibieron datos JSON'}), 400

    username = data.get('username')
    hora_fichaje_js = data.get('hora_fichaje') 
    comentario = data.get('comentario')

    if not all([username, hora_fichaje_js, comentario is not None]):
        return jsonify({'status': 'error', 'message': 'Faltan datos (username, hora_fichaje o comentario)'}), 400

    try:

        formato_js = "%a, %d %b %Y %H:%M:%S %Z"
        
        objeto_datetime = datetime.strptime(hora_fichaje_js, formato_js)

        hora_fichaje_db = objeto_datetime.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[DEBUG REST] Hora recibida: {hora_fichaje_js}")
        print(f"[DEBUG REST] Hora convertida para DB: {hora_fichaje_db}")
        
        resultado = model.insertar_comentario(username, hora_fichaje_db, comentario)

        if resultado:
             return jsonify({'status': 'ok'})
        else:
             return jsonify({'status': 'error', 'message': 'No se encontró el fichaje para actualizar.'}), 404

    except ValueError:
        # Este error salta si el formato de la fecha no coincide con `formato_js`.
        msg_error = f"El formato de la fecha recibido ('{hora_fichaje_js}') no es válido."
        print(f"ERROR: {msg_error}")
        return jsonify({'status': 'error', 'message': msg_error}), 400
    except Exception as e:
        print(f"Error inesperado al actualizar comentario: {e}")
        return jsonify({'status': 'error', 'message': f'Error interno del servidor: {e}'}), 500



'''                                                                                                                     
CODIGO PARA ADMINISTRADOR                                                                                               
'''
# --- RUTA PARA QUE EL ADMIN LISTE LOS FICHAJES DE CUALQUIER USUARIO ---
@app.route('/listar/admin', methods=['POST'])
def listar_users_admin():
    # Verifica que el admin ha iniciado sesión
    if 'username' not in session or session.get('tipo') != 'admin':
        return jsonify({'status': 'error', 'message': 'Acceso no autorizado'}), 401

    data = request.get_json()
    if not data or 'username' not in data:
        return jsonify({'status': 'error', 'message': 'Falta el nombre de usuario a buscar'}), 400

    username_a_buscar = data.get('username')
    
    # Llama a la función del modelo para obtener TODOS los fichajes (sin LIMIT 4)
    # Para esto, es mejor tener una función separada en el modelo
    fichajes = model.listar_fichajes(username_a_buscar) 
    
    print(f"[ADMIN] Fichajes devueltos para '{username_a_buscar}': {len(fichajes)} registros.")
    
    # Aunque no se encuentren fichajes, devolvemos un ok con una lista vacía
    return jsonify({'status': 'ok', 'fichajes': fichajes})


# --- RUTA PARA QUE EL ADMIN AÑADA UN NUEVO USUARIO ---
@app.route('/añadir_user/admin', methods=['POST'])
def añadir_user_admin():
    # Verifica que el admin ha iniciado sesión
    if 'username' not in session or session.get('tipo') != 'admin':
        return jsonify({'status': 'error', 'message': 'Acceso no autorizado'}), 401
    
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'status': 'error', 'message': 'Faltan datos (username, password)'}), 400

    # Llama a la función del modelo para añadir un usuario.
    # El nombre de la función en model.py es 'addUser'
    resultado = model.addUser(data)
    
    # addUser devuelve un diccionario con 'success' o 'error', lo pasamos directamente
    if "success" in resultado:
        print(f"[ADMIN] Usuario '{data.get('username')}' añadido correctamente.")
        return jsonify(resultado), 201 # 201 Creado
    else:
        print(f"[ADMIN] Error al añadir usuario '{data.get('username')}': {resultado.get('error')}")
        return jsonify(resultado), 409 # 409 Conflicto (usuario ya existe)



@app.route('/admin/editar_jornada', methods=['POST'])
def editar_jornada_admin():
    if 'username' not in session or session.get('tipo') != 'admin':
        return jsonify({'status': 'error', 'message': 'Acceso no autorizado'}), 401

    data = request.get_json()
    username_a_editar = data.get('username')
    fecha_jornada = data.get('fecha_jornada') # Formato 'YYYY-MM-DD'
    nuevos_fichajes = data.get('fichajes')

    if not all([username_a_editar, fecha_jornada, nuevos_fichajes]):
        return jsonify({'status': 'error', 'message': 'Faltan datos para la edición'}), 400

    try:
        # 1. Edita la jornada en la base de datos
        exito_edicion = model.editar_jornada_admin(username_a_editar, fecha_jornada, nuevos_fichajes)

        if exito_edicion:
            # 2. Obtenemos TODOS los fichajes DEL DÍA MODIFICADO usando nuestra nueva función dual
            #    Le pasamos la fecha_jornada para activar el modo de búsqueda por fecha.
            fichajes_del_dia_actualizado = model.listar_fichajes(username_a_editar, fecha_jornada)
            
            # 3. Recalculamos las horas de ESE DÍA con los fichajes actualizados
            if fichajes_del_dia_actualizado:
                # ¡OJO! Tu función calcular_horas necesita una pequeña adaptación si usa date.today()
                # Adaptación sugerida:
                horas_dia_recalculadas_str = calcular_horas(fichajes_del_dia_actualizado)
                
                if horas_dia_recalculadas_str:
                    # 4. Insertamos las horas diarias recién calculadas en su tabla
                    #    Asumo que tu función para insertar/actualizar horas diarias existe
                    #    y se encarga de hacer INSERT... ON DUPLICATE KEY UPDATE
                    model.insertar_horas_diarias(username_a_editar, horas_dia_recalculadas_str)

            # (Opcional) Aquí podrías llamar a la función que recalcula el total de todo el mes
            # recalcular_y_actualizar_total_mensual(username_a_editar, fecha_jornada)
            
            return jsonify({'status': 'ok', 'message': 'Jornada actualizada y horas diarias recalculadas.'})
        else:
            return jsonify({'status': 'error', 'message': 'No se pudo actualizar la jornada en la BD.'}), 500
    
    except Exception as e:
        print(f"Error en la ruta /admin/editar_jornada: {e}")
        return jsonify({'status': 'error', 'message': f'Error interno del servidor: {e}'}), 500

def recalcular_y_actualizar_total_mensual(username, fecha_jornada_str):
    """
    Recalcula el total de horas para un usuario en un mes específico y lo actualiza en la BD.
    
    Args:
        username (str): El usuario cuyo total se va a recalcular.
        fecha_jornada_str (str): Una fecha ('YYYY-MM-DD') dentro del mes que se debe recalcular.
    """
    print(f"[RECALCULAR] Iniciando recálculo para '{username}' en el mes de {fecha_jornada_str}")

    try:
        # Convertimos el string de la fecha a un objeto datetime para poder obtener el mes y el año
        fecha_obj = datetime.strptime(fecha_jornada_str, '%Y-%m-%d').date()
        mes = fecha_obj.month
        año = fecha_obj.year

        # 1. Obtenemos todas las horas diarias del usuario para el mes específico.
        #    Asumo que model.ver_horas_diarias(username, mes, año) existe o la creamos.
        #    Esta función debe devolver una lista de diccionarios, ej: [{'horas_diarias': '2024-05-30 - 08:01:15'}, ...]
        
        # Necesitaremos una función en model.py que pueda filtrar por mes/año
        # ej: model.ver_horas_diarias_mes(username, mes, año)
        resumen_mensual = model.ver_horas_diarias_mes(username, mes, año) 
        
        if not resumen_mensual:
            print(f"[RECALCULAR] No se encontraron horas diarias para '{username}' en {mes}/{año}. Total puesto a cero.")
            model.insertar_horas_totales(username, "00:00:00") # O manejarlo como prefieras
            return True

        total_general_segundos = 0
        
        # 2. Sumamos todas las horas
        for dia in resumen_mensual:
            # Extraemos la parte de la hora 'HH:MM:SS' de la cadena 'YYYY-MM-DD - HH:MM:SS'
            # Suponemos que dia['horas_diarias'] existe y tiene el formato correcto
            if 'horas_diarias' in dia and dia['horas_diarias'] and ' - ' in dia['horas_diarias']:
                tiempo_str = dia['horas_diarias'].split(' - ')[1]
                h, m, s = map(int, tiempo_str.split(':'))
                total_general_segundos += h * 3600 + m * 60 + s
        
        # 3. Convertimos el total de segundos de nuevo a formato HH:MM:SS
        total_horas = total_general_segundos // 3600
        total_minutos = (total_general_segundos % 3600) // 60
        total_segundos_final = total_general_segundos % 60
        
        horas_totales_calculadas = f"{total_horas:02d}:{total_minutos:02d}:{total_segundos_final:02d}"
        
        print(f"[RECALCULAR] Nuevo total de horas para '{username}' en {mes}/{año}: {horas_totales_calculadas}")

        # 4. Insertamos el nuevo total en la base de datos
        model.insertar_horas_totales(username, horas_totales_calculadas)
        return True

    except Exception as e:
        print(f"[RECALCULAR] Error grave durante el recálculo: {e}")
        return False
        
        
if __name__ == '__main__':

    model.init()
    
    app.run(host='0.0.0.0', port=5000, debug=True)

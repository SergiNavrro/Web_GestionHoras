from flask import Flask, request, jsonify, render_template, session
import model  # Tu archivo model.py
from datetime import datetime, date, timezone, timedelta 
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

# --- NUEVA FUNCIÓN DE CÁLCULO DE HORAS, A PRUEBA DE MEDIANOCHE ---
def calcular_horas_jornada(jornada):
    """Calcula las horas trabajadas para una única jornada (lista de fichajes)."""
    fichajes = {f['tipo']: f['hora'] for f in jornada}
    
    # Obtenemos los datetime de cada fichaje, si existen
    entrada = fichajes.get('entrada')
    parada_cena = fichajes.get('parada_cenar')
    salida_cena = fichajes.get('salida_cenar')
    salida = fichajes.get('salida')

    # Si falta la entrada o la salida, no se puede calcular
    if not entrada or not salida:
        return None
        
    tiempo_trabajado = timedelta(0) # Inicializamos un timedelta

    if parada_cena and salida_cena:
        # Jornada con pausa para cenar
        primer_tramo = parada_cena - entrada
        segundo_tramo = salida - salida_cena
        tiempo_trabajado = primer_tramo + segundo_tramo
    else:
        # Jornada sin pausa (o incompleta)
        tiempo_trabajado = salida - entrada

    # Convertimos el timedelta a un formato de string H:M:S
    total_seconds = int(tiempo_trabajado.total_seconds())
    if total_seconds < 0: return None # No debería pasar

    horas = total_seconds // 3600
    minutos = (total_seconds % 3600) // 60
    segundos = total_seconds % 60

    # La fecha de la jornada es la fecha de la entrada
    fecha_de_la_jornada = entrada.strftime('%Y-%m-%d')
    
    return f"{fecha_de_la_jornada} - {horas:02d}:{minutos:02d}:{segundos:02d}"

# --- NUEVA FUNCIÓN PARA AGRUPAR FICHAJES ---
def agrupar_fichajes_en_jornadas(fichajes):
    jornadas = []
    jornada_actual = []
    for fichaje in fichajes:
        if fichaje['tipo'] == 'entrada':
            # Si encontramos una 'entrada' y ya había una jornada empezada, la guardamos
            if jornada_actual:
                jornadas.append(jornada_actual)
            # Empezamos una nueva jornada
            jornada_actual = [fichaje]
        elif jornada_actual: # Si no es entrada, la añadimos a la jornada actual
            jornada_actual.append(fichaje)

    # Añadimos la última jornada que estaba en proceso
    if jornada_actual:
        jornadas.append(jornada_actual)

    # La función devolvía las jornadas en orden cronológico, la invertimos para mostrar las más nuevas primero
    jornadas.reverse()
    return jornadas
    
    
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

    fichajes_raw = model.listar_fichajes(username) # Obtenemos los fichajes
    
    # --- AÑADE ESTE BUCLE DE CONVERSIÓN ---
    fichajes = []
    for f in fichajes_raw:
        f_copy = f.copy()
        if isinstance(f_copy.get('hora'), datetime):
            f_copy['hora'] = f_copy['hora'].strftime('%Y-%m-%d %H:%M:%S')
        fichajes.append(f_copy)
    # --- FIN DEL BLOQUE AÑADIDO ---
    
    print(f"Fichajes devueltos para {username}: {fichajes}") # Esto ahora mostrará el texto

    if tipo == 'salida':
        # Buscamos la jornada completa que acabamos de terminar
        fichajes_todos = model.listar_fichajes_todos(username)
        jornadas_agrupadas = agrupar_fichajes_en_jornadas(fichajes_todos)
        jornada_finalizada = jornadas_agrupadas[0] # La más reciente

        # Recalculamos sus horas
        hora_diaria_str = calcular_horas_jornada(jornada_finalizada)
        if hora_diaria_str:
            model.insertar_horas_diarias(username, hora_diaria_str)
            # El recálculo total lo haremos en una tarea aparte o lo simplificamos
            # por ahora, para no complicar en exceso esta respuesta.
            # Puedes llamar aquí a la función que recalcula y guarda el total del mes.
            fecha_jornada = hora_diaria_str.split(' - ')[0]
            recalcular_y_actualizar_total_mensual(username, fecha_jornada)
            
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



# --- RUTA DE HORAS DIARIAS MEJORADA (PARA USUARIO) ---
@app.route('/horas_diarias/<username>', methods=['GET'])
def get_horas_diarias(username):
    if 'username' not in session or session['username'] != username:
        return jsonify({"status": "error", "message": "No autorizado"}), 401
    
    resumen_diario = model.ver_horas_diarias(username)
    horas_totales = model.obtener_horas(username)
    
    return jsonify({
        "status": "ok",
        "resumen": resumen_diario,
        "horas_totales": horas_totales # ¡Añadimos las horas totales!
    })


@app.route('/comentario', methods=['POST'])
def anadir_comentario():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No se recibieron datos JSON'}), 400

    username = data.get('username')
    # El JavaScript ahora envía el formato 'YYYY-MM-DD HH:MM:SS' directamente.
    hora_fichaje_js = data.get('hora_fichaje') 
    comentario = data.get('comentario')

    if not all([username, hora_fichaje_js, comentario is not None]):
        return jsonify({'status': 'error', 'message': 'Faltan datos (username, hora_fichaje o comentario)'}), 400

    # YA NO SE NECESITA NINGUNA CONVERSIÓN NI PARSEO DE FECHA AQUÍ.
    # El string que llega es exactamente el que la base de datos necesita.
    try:
        print(f"[DEBUG REST] Comentario recibido para la hora: '{hora_fichaje_js}'")
        
        # Pasamos la cadena de texto directamente a la función del modelo.
        resultado = model.insertar_comentario(username, hora_fichaje_js, comentario)

        # La función del modelo devuelve un diccionario, lo comprobamos.
        if resultado.get("status") == "ok":
             return jsonify({'status': 'ok'})
        else:
             # Devolvemos el mensaje de error que pueda venir del modelo
             return jsonify({'status': 'error', 'message': resultado.get('message', 'No se encontró el fichaje')}), 404

    except Exception as e:
        print(f"Error inesperado al actualizar comentario: {e}")
        return jsonify({'status': 'error', 'message': f'Error interno del servidor: {e}'}), 500



'''                                                                                                                     
CODIGO PARA ADMINISTRADOR                                                                                               
'''
# --- RUTA LISTAR PARA ADMIN TOTALMENTE REHECHA ---
@app.route('/listar/admin', methods=['POST'])
def listar_users_admin():
    if 'username' not in session or session.get('tipo') != 'admin':
        return jsonify({'status': 'error', 'message': 'Acceso no autorizado'}), 401

    data = request.get_json()
    username_a_buscar = data.get('username')
    
    fichajes_todos = model.listar_fichajes_todos(username_a_buscar) 
    
    # --- AÑADE ESTE BUCLE PARA FORMATEAR TODAS LAS HORAS ---
    for f in fichajes_todos:
        if isinstance(f.get('hora'), datetime):
            f['hora'] = f['hora'].strftime('%Y-%m-%d %H:%M:%S')
    # --- FIN DEL BLOQUE AÑADIDO ---
    
    # 2. Los agrupamos en jornadas lógicas
    jornadas_agrupadas = agrupar_fichajes_en_jornadas(fichajes_todos)
    
    # 3. Obtenemos los resúmenes y totales
    resumen_diario = model.ver_horas_diarias(username_a_buscar)
    horas_totales = model.obtener_horas(username_a_buscar)
    
    # Devolvemos todo bien estructurado
    return jsonify({
        'status': 'ok',
        'jornadas': jornadas_agrupadas,
        'resumen_diario': resumen_diario,
        'horas_totales': horas_totales
    })

@app.route('/admin/editar_jornada', methods=['POST'])
def editar_jornada_admin():
    if 'username' not in session or session.get('tipo') != 'admin':
        return jsonify({'status': 'error', 'message': 'Acceso no autorizado'}), 401

    data = request.get_json()
    username = data.get('username')
    fecha_jornada_str = data.get('fecha_jornada') # La fecha de la 'entrada' original
    nuevos_fichajes_hora = data.get('fichajes')

    # PASO 1: BORRAR DE FORMA SEGURA LA JORNADA ANTIGUA COMPLETA
    exito_borrado = model.borrar_fichajes_jornada(username, fecha_jornada_str)
    if not exito_borrado:
        return jsonify({'status': 'error', 'message': 'No se pudo borrar la jornada anterior para actualizar.'}), 500

    # PASO 2: RE-INSERTAR LOS NUEVOS FICHAJES
    # Esta lógica determina si la hora corresponde al día de la jornada o al siguiente
    jornada_reconstruida = []
    hora_referencia = None

    # Ordenamos por si el admin los pone desordenados. 'entrada' siempre primero.
    tipos_ordenados = ['entrada', 'parada_cenar', 'salida_cenar', 'salida']

    for tipo in tipos_ordenados:
        hora_str = nuevos_fichajes_hora.get(tipo)
        if hora_str:
            
            # --- INICIO DEL CÓDIGO CORREGIDO PARA EL MÓVIL ---
            # Normalizamos la hora para que SIEMPRE tenga segundos.
            if hora_str.count(':') == 1:  # Si solo hay un ':', es formato HH:MM (móvil)
                hora_str += ':00'         # Le añadimos los segundos para evitar errores.
            # --- FIN DEL CÓDIGO CORREGIDO ---

            fecha_actual_str = fecha_jornada_str
            # Esta línea ahora es segura, porque hora_str siempre tendrá el formato correcto HH:MM:SS.
            hora_obj_actual = datetime.strptime(hora_str, '%H:%M:%S').time()

            if hora_referencia and hora_obj_actual < hora_referencia:
                # Si la hora actual es menor que la anterior, es del día siguiente.
                fecha_dt = datetime.strptime(fecha_jornada_str, '%Y-%m-%d') + timedelta(days=1)
                fecha_actual_str = fecha_dt.strftime('%Y-%m-%d')
            
            hora_referencia = hora_obj_actual # Actualizamos la referencia

            # Construimos el objeto datetime completo y lo guardamos
            hora_completa = datetime.strptime(f"{fecha_actual_str} {hora_str}", "%Y-%m-%d %H:%M:%S")
            model.fichar(username, tipo, hora_completa)
            jornada_reconstruida.append({'tipo': tipo, 'hora': hora_completa})
    
    # PASO 3: RECALCULAR LAS HORAS DE ESA JORNADA Y GUARDARLAS
    if jornada_reconstruida:
        horas_dia_recalculadas_str = calcular_horas_jornada(jornada_reconstruida)
        if horas_dia_recalculadas_str:
            # La función insertar_horas_diarias ya debería manejar el UPDATE si existe.
            model.insertar_horas_diarias(username, horas_dia_recalculadas_str)

    # (Opcional) Aquí podrías recalcular el total de todo el mes
    recalcular_y_actualizar_total_mensual(username, fecha_jornada_str)
            
    return jsonify({'status': 'ok', 'message': 'Jornada actualizada y horas recalculadas.'})

def determinar_fecha_fichaje(fecha_inicio_jornada, hora_actual_str, jornada_parcial):
    """Determina si la hora pertenece al día de inicio o al siguiente."""
    fecha_inicio = datetime.strptime(fecha_inicio_jornada, '%Y-%m-%d').date()
    hora_actual = datetime.strptime(hora_actual_str, '%H:%M:%S').time()

    if not jornada_parcial: # Si es el primer fichaje (entrada), es la fecha de inicio
        return fecha_inicio.strftime('%Y-%m-%d')
    
    # Comparamos con la hora del último fichaje añadido
    ultimo_fichaje_hora = jornada_parcial[-1]['hora'].time()
    
    if hora_actual < ultimo_fichaje_hora:
        # La nueva hora es anterior a la última -> Es del día siguiente
        return (fecha_inicio + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        # La nueva hora es posterior -> Es del mismo día
        return jornada_parcial[-1]['hora'].strftime('%Y-%m-%d')


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


# --- AÑADE ESTA NUEVA FUNCIÓN DE LÓGICA DE NEGOCIO ---
def recalcular_y_actualizar_total_mensual(username, fecha_afectada_str):
    """
    Recalcula el total de horas para un usuario en un mes específico y lo actualiza en la BD.
    
    Args:
        username (str): El usuario cuyo total se va a recalcular.
        fecha_afectada_str (str): Una fecha ('YYYY-MM-DD') dentro del mes que se debe recalcular.
    """
    print(f"[RECALCULAR] Iniciando recálculo total para '{username}' en el mes de {fecha_afectada_str}")

    try:
        # 1. Obtener el mes y el año de la fecha afectada
        fecha_obj = datetime.strptime(fecha_afectada_str, '%Y-%m-%d')
        mes = fecha_obj.month
        anio = fecha_obj.year

        # 2. Pedir al modelo todas las horas diarias de ese mes
        resumen_mensual = model.ver_horas_diarias_mes(username, anio, mes) 
        
        total_general_segundos = 0
        
        # 3. Sumar todas las horas
        if resumen_mensual:
            for dia in resumen_mensual:
                # Extraemos la parte de la hora 'HH:MM:SS' de la cadena 'YYYY-MM-DD - HH:MM:SS'
                if 'horas_diarias' in dia and dia['horas_diarias'] and ' - ' in dia['horas_diarias']:
                    tiempo_str = dia['horas_diarias'].split(' - ')[1]
                    h, m, s = map(int, tiempo_str.split(':'))
                    total_general_segundos += h * 3600 + m * 60 + s
        
        # 4. Convertir el total de segundos de nuevo a formato string
        total_horas = total_general_segundos // 3600
        total_minutos = (total_general_segundos % 3600) // 60
        total_segundos_final = total_general_segundos % 60
        
        # Guardamos el total como un simple string "HH:MM:SS"
        horas_totales_calculadas_str = f"{total_horas:02d}:{total_minutos:02d}:{total_segundos_final:02d}"
        
        print(f"[RECALCULAR] Nuevo total para '{username}' en {mes}/{anio}: {horas_totales_calculadas_str}")

        # 5. Insertar el nuevo total en la base de datos
        model.insertar_horas_totales(username, horas_totales_calculadas_str)
        return True

    except Exception as e:
        print(f"[RECALCULAR] Error grave durante el recálculo total: {e}")
        return False
        
        
if __name__ == '__main__':

    model.init()
    
    app.run(host='0.0.0.0', port=5000, debug=True)

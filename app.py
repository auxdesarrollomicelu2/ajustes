import io
import time
from flask import Flask, json, jsonify, render_template, request
import numpy as np
import requests
import base64
import logging
import pandas as pd
from flask import request, jsonify
import tempfile
import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from sqlalchemy.exc import SQLAlchemyError
from flask_sqlalchemy import SQLAlchemy
 
logger = logging.getLogger(__name__)
 
app = Flask(__name__)

# Configuración de la base de datos PostgreSQL
app.config['SQLALCHEMY_BINDS'] = {
    'db3':'postgresql://postgres:vWUiwzFrdvcyroebskuHXMlBoAiTfgzP@junction.proxy.rlwy.net:47834/railway',
    #'db3':'postgresql://postgres:123@localhost:5432/facturas',
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
db = SQLAlchemy(app)

class Factura(db.Model):
    __tablename__ = 'facturas'
    __table_args__ = {'schema': 'plan_beneficios'}
    __bind_key__ = 'db3'
    
    codigo_factura = db.Column(db.String(50), index=True)
    nit = db.Column(db.String(100))
    nombre_cliente = db.Column(db.String(200))
    fecha_emision = db.Column(db.DateTime)
    fecha_vencimiento = db.Column(db.DateTime)
    bodega = db.Column(db.String(100))
    ciudad = db.Column(db.String(100))
    forma_pago = db.Column(db.String(50))
    item = db.Column(db.Text)  
    metodo_pago = db.Column(db.String(50))
    tipo_operacion = db.Column(db.String(50))
    nombre_vendedor = db.Column(db.String(200))
    total = db.Column(db.String(50))
    estado = db.Column(db.String(20))
    id = db.Column(db.Integer, primary_key=True)


 
ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"
ALEGRA_EMAIL = "tom@tomlampert.com" 
ALEGRA_TOKEN = "8bd83addb0947cad6691"
 
TIMEOUT_SECONDS = 30
 
def get_auth_headers():
    auth_string = f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}"
    auth_bytes = auth_string.encode('ascii')
    base64_auth = base64.b64encode(auth_bytes).decode('ascii')
    return {
        'Authorization': f'Basic {base64_auth}',
        'Accept': 'application/json'
    }
    
 
def validate_excel_data(df):
    required_columns = ['Ítem', 'AJUSTE', 'Costo promedio']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing_columns)}")
    return True
 
def get_alegra_items():
    items = []
    offset = 0
    limit = 30
   
    try:
        while True:
            response = requests.get(
                f"{ALEGRA_BASE_URL}/items",
                headers=get_auth_headers(),
                params={"limit": limit, "start": offset},
                timeout=TIMEOUT_SECONDS
            )
           
            if response.status_code != 200:
                raise Exception(f"Error al obtener ítems: {response.text}")
           
            current_items = response.json()
            if not current_items:
                break
           
            # Filtrar y procesar ítems
            items.extend(current_items)
            
            if len(current_items) < limit:
                break
           
            offset += limit
       
        # Proceso de eliminación de duplicados priorizando ítems activos
        unique_items = {}
        for item in items:
            clean_name = str(item.get('name', '')).upper().strip()
            
            # Si no existe el nombre o si el nuevo ítem está activo
            if (clean_name not in unique_items or 
                (item.get('status', '').lower() == 'active' and 
                 unique_items[clean_name].get('status', '').lower() != 'active')):
                unique_items[clean_name] = item
       
        # Convertir diccionario a lista, priorizando ítems activos
        final_items = list(unique_items.values())
       
        # Filtrar solo ítems activos
        active_items = [
            item for item in final_items 
            if item.get('status', '').lower() == 'active'
        ]
       
        return active_items
       
    except requests.exceptions.Timeout:
        raise Exception("Tiempo de espera agotado al obtener ítems")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error de conexión: {str(e)}")
   
@app.route('/')
def ajustes():
    return render_template('ajustes.html')
 
@app.route('/api/consultas', methods=['GET'])
def consultas():
    tipo = request.args.get('tipo')
   
    if not tipo:
        return jsonify({
            'success': False,
            'error': 'El parámetro "tipo" es requerido'
        })
   
    try:
        if tipo == 'consecutive':
            response = requests.get(
                f"{ALEGRA_BASE_URL}/inventory-adjustments",
                headers=get_auth_headers(),
                params={
                    'order_direction': 'DESC',
                    'limit': 30,
                    'order_field': 'date',
                    'metadata': 'true'
                }
            )
           
            if response.status_code == 200:
                data = response.json()
                adjustments = data.get('data', [])
                total = data.get('metadata', {}).get('total', 0)
               
                next_consecutive = 1
                if adjustments and len(adjustments) > 0:
                    last_number = adjustments[0].get('number')
                    if last_number:
                        next_consecutive = int(last_number) + 1
               
                return jsonify({
                    'success': True,
                    'next_consecutive': next_consecutive,
                    'adjustments': adjustments,
                    'total': total
                })
           
            return jsonify({
                'success': False,
                'error': 'No se pudo obtener los ajustes'
            })
           
        elif tipo == 'warehouses':
           
           
            response = requests.get(
                f"{ALEGRA_BASE_URL}/warehouses",
                headers=get_auth_headers()
            )
           
            if response.status_code == 200:
                warehouses = response.json()
                return jsonify({
                    'success': True,
                    'warehouses': warehouses
                })
           
            return jsonify({
                'success': False,
                'error': f'Error al obtener bodegas: {response.status_code}'
            })
       
        else:
            return jsonify({
                'success': False,
                'error': 'Tipo de consulta no válido'
            })
           
    except Exception as e:
        logger.exception(f"Error en consulta tipo: {tipo}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
       
@app.route('/api/inventory-adjustments', methods=['POST'])
def process_inventory_adjustments():
    """Procesa los ajustes de inventario desde un archivo Excel"""
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No se encontró archivo'
        })
   
    file = request.files['file']
    form_data = request.form.to_dict()
   
    # Validar campos requeridos
    required_fields = ['fecha', 'numero', 'bodega']
    missing_fields = [field for field in required_fields if not form_data.get(field)]
   
    if missing_fields:
        return jsonify({
            'success': False,
            'error': f'Campos requeridos faltantes: {", ".join(missing_fields)}'
        })
   
    try:
        # Leer y validar Excel
        file_contents = file.read()
        excel_data = io.BytesIO(file_contents)
        df = pd.read_excel(excel_data)
        validate_excel_data(df)
        #print("Datos del Excel:", df.head())
       
        # Obtener ítems de Alegra
        alegra_items = get_alegra_items()
        #print("Items de Alegra:", alegra_items)
        items_dict = {item['name'].strip(): item['id'] for item in alegra_items}
       
        # Filtrar solo filas con ajustes válidos
        df_filtered = df[df['AJUSTE'].notna() & (df['AJUSTE'] != 0)]
        print("Datos filtrados:", df_filtered)
       
        # Configuración de lotes
        BATCH_SIZE = 50
        total_rows = len(df_filtered)
        total_batches = (total_rows + BATCH_SIZE - 1) // BATCH_SIZE
       
        all_responses = []
        errors = []
       
        # Procesar por lotes
        for batch_num in range(total_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min((batch_num + 1) * BATCH_SIZE, total_rows)
            batch_df = df_filtered.iloc[start_idx:end_idx]
           
            inventory_items = {}
           
            # Procesar ajustes del lote actual
            for index, row in batch_df.iterrows():
                try:
                    ajuste = float(row['AJUSTE'])
                    costo = float(row['Costo promedio']) if pd.notna(row['Costo promedio']) else 0
                    item_name = str(row['Ítem']).strip()
                   
                    item_id = items_dict.get(item_name)
                    if not item_id:
                        errors.append(f"Ítem no encontrado: {item_name}")
                        continue
                   
                    if item_id in inventory_items:
                        existing_item = inventory_items[item_id]
                        net_quantity = (existing_item['quantity'] if existing_item['type'] == 'in' else -existing_item['quantity']) + ajuste
                        existing_item['type'] = 'in' if net_quantity > 0 else 'out'
                        existing_item['quantity'] = abs(net_quantity)
                    else:
                        inventory_items[item_id] = {
                            "id": str(item_id),
                            "type": "out" if ajuste < 0 else "in",
                            "quantity": abs(ajuste),
                            "unitCost": costo
                        }
                       
                except ValueError as e:
                    errors.append(f"Error en fila {index + 2}: {str(e)}")
           
            final_items = list(inventory_items.values())
            if final_items:
                # Preparar payload para Alegra con formato mejorado
                base_number = int(form_data['numero'])
                batch_identifier = str(batch_num).zfill(3)
                alegra_payload = {
                    "date": form_data['fecha'],
                    "number": int(f"{base_number}{batch_identifier}"),
                    "observations": f"GRUPO #{base_number} - LOTE {batch_num + 1}/{total_batches} - {form_data.get('observaciones', '')}",
                    "warehouse": {
                        "id": str(form_data['bodega'])
                    },
                    "items": final_items
                   
                }
                print("Payload a enviar a Alegra:", alegra_payload)

                # Intentar enviar con reintentos
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        response = requests.post(
                            f"{ALEGRA_BASE_URL}/inventory-adjustments",
                            headers=get_auth_headers(),
                            json=alegra_payload,
                            timeout=30  # Timeout aumentado para lotes grandes
                        )
                        print("Status Code:", response.status_code)
                        print("Respuesta completa de Alegra:", response.text)
                       
                        if response.status_code in [200, 201]:
                            all_responses.append(response.json())
                            break
                        elif response.status_code == 429 and retry < max_retries - 1:  # Rate limit
                            time.sleep(2 * (retry + 1))  # Espera exponencial
                            continue
                        else:
                            errors.append(f"Error en lote {batch_num + 1}: {response.text}")
                            break
                           
                    except requests.exceptions.RequestException as e:
                        if retry < max_retries - 1:
                            time.sleep(2 * (retry + 1))
                            continue
                        errors.append(f"Error de conexión en lote {batch_num + 1}: {str(e)}")
                        break
               
                # Pequeña pausa entre lotes para evitar rate limits
                time.sleep(1)
       
        # Preparar respuesta final
        if errors and not all_responses:
            return jsonify({
                'success': False,
                'error': 'Errores encontrados en todos los lotes',
                'details': errors
            })
        elif errors:
            return jsonify({
                'success': True,
                'warning': 'Proceso completado con algunos errores',
                'details': errors,
                'successful_batches': len(all_responses),
                'alegra_responses': all_responses
            })
        else:
            return jsonify({
                'success': True,
                'message': f'Ajustes de inventario creados exitosamente ({len(all_responses)} lotes)',
                'alegra_responses': all_responses
            })
           
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error al procesar: {str(e)}'
        })
       
 
@app.route('/api/preview-excel', methods=['POST'])
def preview_excel():
    """Endpoint para previsualizar datos del Excel"""
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No se encontró archivo'
        })
 
    file = request.files['file']
   
    try:
        # Leer Excel
        file_contents = file.read()
        excel_data = io.BytesIO(file_contents)
        df = pd.read_excel(excel_data)
       
        # Validar estructura
        validate_excel_data(df)
       
        # Filtrar solo ajustes válidos
        df = df[pd.notna(df['AJUSTE']) & (df['AJUSTE'] != 0)]
       
        # Preparar datos para preview
        preview_data = []
        for _, row in df.iterrows():
            preview_data.append({
                'item': str(row['Ítem']).strip(),
                'ajuste': float(row['AJUSTE']),
                'costo': float(row['Costo promedio']) if pd.notna(row['Costo promedio']) else 0
            })
       
        return jsonify({
            'success': True,
            'preview_data': preview_data
        })
       
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# implementacion api para facturas 
@app.route('/facturas')
def facturas_view():
    return render_template('facturas.html')
@app.route('/api/facturas', methods=['GET'])
def facturas():
    """
    Consulta las facturas de Alegra según los parámetros proporcionados
    """
    try:
        # Obtener todos los parámetros posibles de la solicitud
        params = {
            'start': request.args.get('start'),
            'limit': request.args.get('limit', '30'),
            'order_direction': request.args.get('order_direction', 'DESC'),
            'order_field': request.args.get('order_field', 'date'),
            'metadata': request.args.get('metadata', 'true'),
            'id': request.args.get('id'),
            'date': request.args.get('date'),
            'dueDate': request.args.get('dueDate'),
            'status': request.args.get('status'),
            'client_id': request.args.get('client_id'),
            'client_name': request.args.get('client_name'),
            'client_identification': request.args.get('client_identification'),
            'numberTemplate_fullNumber': request.args.get('numberTemplate_fullNumber'),
            'item_id': request.args.get('item_id'),
            'date_after': request.args.get('date_after'),
            'date_afterOrNow': request.args.get('date_afterOrNow'),
            'date_before': request.args.get('date_before'),
            'date_beforeOrNow': request.args.get('date_beforeOrNow'),
            'dueDate_after': request.args.get('dueDate_after'),
            'dueDate_afterOrNow': request.args.get('dueDate_afterOrNow'),
            'dueDate_before': request.args.get('dueDate_before'),
            'dueDate_beforeOrNow': request.args.get('dueDate_beforeOrNow'),
            'toReplace': request.args.get('toReplace'),
            'download': request.args.get('download'),
            'downloadType': request.args.get('downloadType'),
            'expand': request.args.get('expand', 'client,items,warehouse')
        }
        
        # Eliminar los parámetros que no tienen valor
        params = {k: v for k, v in params.items() if v is not None}
        
        # Realizar la petición a la API de Alegra
        response = requests.get(
            f"{ALEGRA_BASE_URL}/invoices",
            headers=get_auth_headers(),
            params=params,
            timeout=TIMEOUT_SECONDS
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Si se solicitaron metadatos, la respuesta ya viene en formato {data, metadata}
            # Si no, toda la respuesta son las facturas
            if 'metadata' in params and params['metadata'] == 'true':
                return jsonify({
                    'success': True,
                    'data': data.get('data', []),
                    'metadata': data.get('metadata', {})
                })
            else:
                return jsonify({
                    'success': True,
                    'data': data
                })
        
        # Si hay un error, devolver el mensaje de error de la API
        return jsonify({
            'success': False,
            'error': f'Error al obtener facturas: {response.status_code}',
            'message': response.text
        })
        
    except Exception as e:
        logger.exception("Error al consultar facturas")
        return jsonify({
            'success': False,
            'error': str(e)
        }) 
def get_facturas_by_date_range(start_date, end_date, page=0, page_size=30):
    """
    Obtiene facturas de Alegra por rango de fechas con paginación
    Respeta el límite máximo de 30 facturas por solicitud de la API
    """
    try:
        # Asegurar que el tamaño de página no exceda el límite de la API
        if page_size > 30:
            logger.warning("El tamaño de página excede el límite de la API. Ajustando a 30.")
            page_size = 30
            
        logger.info(f"Obteniendo facturas del {start_date} al {end_date}, página {page}, tamaño de página {page_size}")
        
        # Convertir fechas al formato requerido por la API
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Parámetros para la consulta
        params = {
            'start': page * page_size,
            'limit': page_size,
            'order_direction': 'DESC',
            'order_field': 'date',
            'metadata': 'true',
            'date_afterOrNow': start_date_str,
            'date_beforeOrNow': end_date_str,
            'expand': 'client,items,warehouse,seller'
        }
        
        logger.debug(f"Parámetros de consulta: {params}")
        
        # Realizar la petición a la API de Alegra
        logger.info(f"Realizando petición a {ALEGRA_BASE_URL}/invoices")
        response = requests.get(
            f"{ALEGRA_BASE_URL}/invoices",
            headers=get_auth_headers(),
            params=params,
            timeout=TIMEOUT_SECONDS
        )
        
        logger.info(f"Código de respuesta: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            facturas = data.get('data', [])
            metadata = data.get('metadata', {})
            total = metadata.get('total', 0)
            
            logger.info(f"Se encontraron {len(facturas)} facturas de un total de {total}")
            
            # Guardar facturas en la base de datos
            if facturas:
                logger.info(f"Guardando {len(facturas)} facturas en la base de datos")
                resultado_guardado = save_facturas_to_db(facturas)
                logger.info(f"Resultado del guardado: {resultado_guardado}")
            else:
                logger.info("No hay facturas para guardar en este rango de fechas y página")
            
            # Si hay más facturas, obtener la siguiente página de forma recursiva
            if (page + 1) * page_size < total:
                logger.info(f"Hay más facturas. Obteniendo página {page + 1}")
                # Esperar un poco para evitar límites de tasa
                time.sleep(1)
                # Llamada recursiva para la siguiente página
                siguiente_resultado = get_facturas_by_date_range(start_date, end_date, page + 1, page_size)
                
                # Combinar resultados
                if siguiente_resultado.get('success', False):
                    return {
                        'success': True,
                        'count': len(facturas) + siguiente_resultado.get('count', 0),
                        'total': total,
                        'message': f"Se procesaron {len(facturas) + siguiente_resultado.get('count', 0)} facturas del {start_date_str} al {end_date_str}"
                    }
            
            # Si no hay más páginas o hubo un error en la recursión
            return {
                'success': True,
                'count': len(facturas),
                'total': total,
                'message': f"Se procesaron {len(facturas)} facturas del {start_date_str} al {end_date_str}"
            }
        
        else:
            logger.error(f"Error al obtener facturas: {response.status_code} - {response.text}")
            return {
                'success': False,
                'error': f'Error al obtener facturas: {response.status_code}',
                'message': response.text
            }
            
    except Exception as e:
        logger.exception(f"Error al consultar facturas por rango de fechas: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
 #funcion para guardar las facturas en la base de datos
def save_facturas_to_db(facturas_data):
    """
    Guarda las facturas en la base de datos local
    """
    try:
        facturas_guardadas = 0
        facturas_actualizadas = 0
        
        for factura_data in facturas_data:
            # Verificar si la factura ya existe en la base de datos
            existing_factura = Factura.query.filter_by(codigo_factura=factura_data['id']).first()
            
            # Extraer datos de la factura
            fecha_emision = None
            fecha_vencimiento = None
            
            try:
                if 'date' in factura_data and factura_data['date']:
                    fecha_emision = datetime.fromisoformat(factura_data['date'].replace('Z', '+00:00'))
                if 'dueDate' in factura_data and factura_data['dueDate']:
                    fecha_vencimiento = datetime.fromisoformat(factura_data['dueDate'].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"Error al parsear fechas de factura {factura_data.get('id')}: {str(e)}")
            
            # Extraer información del cliente
            nombre_cliente = None
            nit = None
            ciudad = None
            
            if 'client' in factura_data and factura_data['client']:
                nombre_cliente = factura_data['client'].get('name')
                
                # Extraer NIT del cliente
                if 'identificationObject' in factura_data['client'] and factura_data['client']['identificationObject']:
                    id_type = factura_data['client']['identificationObject'].get('type', '')
                    id_number = factura_data['client']['identificationObject'].get('number', '')
                    nit = id_number if id_type and id_number else None
                
                # Extraer ciudad del cliente
                if 'city' in factura_data['client'] and factura_data['client']['city']:
                    ciudad = factura_data['client']['city']
                elif 'address' in factura_data['client'] and factura_data['client']['address'] and 'city' in factura_data['client']['address']:
                    ciudad = factura_data['client']['address']['city']
            
            # Extraer información de bodega
            bodega = None
            
            if 'warehouse' in factura_data and factura_data['warehouse']:
                bodega = factura_data['warehouse'].get('name')
            
            # Extraer información del vendedor
            nombre_vendedor = None
            
            if 'seller' in factura_data and factura_data['seller']:
                nombre_vendedor = factura_data['seller'].get('name')
            
            # Número de factura (código)
            codigo_factura = None
            if 'numberTemplate' in factura_data and factura_data['numberTemplate']:
                codigo_factura = factura_data['numberTemplate'].get('fullNumber')
            if not codigo_factura:
                codigo_factura = str(factura_data['id'])
            
            # Extraer SOLO los nombres de los items y unirlos en un string
            item_names = []
            if 'items' in factura_data and factura_data['items']:
                for item in factura_data['items']:
                    if 'name' in item and item['name']:
                        item_names.append(item['name'])
            
            # Unir los nombres con comas para formar un string
            item_string = ", ".join(item_names)
            
            # Extraer forma de pago, método de pago y tipo de operación
            forma_pago = factura_data.get('paymentForm')
            metodo_pago = factura_data.get('paymentMethod')
            tipo_operacion = factura_data.get('operationType')
            
            # Total de la factura
            total = factura_data.get('total')
            
            # Estado de la factura
            estado = factura_data.get('status')
            
            if existing_factura:
                # Actualizar factura existente
                existing_factura.codigo_factura = codigo_factura
                existing_factura.nit = nit
                existing_factura.nombre_cliente = nombre_cliente
                existing_factura.fecha_emision = fecha_emision
                existing_factura.fecha_vencimiento = fecha_vencimiento
                existing_factura.bodega = bodega
                existing_factura.ciudad = ciudad
                existing_factura.forma_pago = forma_pago
                existing_factura.item = item_string
                existing_factura.metodo_pago = metodo_pago
                existing_factura.tipo_operacion = tipo_operacion
                existing_factura.nombre_vendedor = nombre_vendedor
                existing_factura.total = total
                existing_factura.estado = estado
                
                facturas_actualizadas += 1
            else:
                # Crear nueva factura
                nueva_factura = Factura(
                    codigo_factura=codigo_factura,
                    nit=nit,
                    nombre_cliente=nombre_cliente,
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_vencimiento,
                    bodega=bodega,
                    ciudad=ciudad,
                    forma_pago=forma_pago,
                    item=item_string,
                    metodo_pago=metodo_pago,
                    tipo_operacion=tipo_operacion,
                    nombre_vendedor=nombre_vendedor,
                    total=total,
                    estado=estado
                )
                db.session.add(nueva_factura)
                facturas_guardadas += 1
        
        # Guardar cambios en la base de datos
        db.session.commit()
        logger.info(f"Facturas guardadas: {facturas_guardadas}, actualizadas: {facturas_actualizadas}")
        return {
            'success': True,
            'guardadas': facturas_guardadas,
            'actualizadas': facturas_actualizadas
        }
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error al guardar facturas en la base de datos: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
# Configurar el programador de tareas con la zona horaria de Bogotá
bogota_tz = pytz.timezone('America/Bogota')
scheduler = BackgroundScheduler(timezone=pytz.timezone('America/Bogota'))

def actualizar_facturas_primera_quincena():
    """
    Actualiza las facturas de la primera quincena del mes actual (1-15)
    Ejecuta el día 15 de cada mes a las 23:00 hora de Bogotá
    """
    with app.app_context():
        try:
            hoy = date.today()
            primer_dia = date(hoy.year, hoy.month, 1)
            ultimo_dia_quincena = date(hoy.year, hoy.month, 15)
            
            app.logger.info(f"Actualizando facturas de la primera quincena: {primer_dia} - {ultimo_dia_quincena}")
            resultado = get_facturas_by_date_range(primer_dia, ultimo_dia_quincena)
            
            app.logger.info(f"Resultado de la actualización primera quincena: {resultado}")
            return resultado
        except Exception as e:
            app.logger.exception(f"Error al actualizar facturas de la primera quincena: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def actualizar_facturas_segunda_quincena():
    """
    Actualiza las facturas de la segunda quincena del mes actual (16-fin de mes)
    Ejecuta el último día de cada mes a las 23:00 hora de Bogotá
    """
    with app.app_context():
        try:
            hoy = date.today()
            # Primer día de la segunda quincena
            primer_dia = date(hoy.year, hoy.month, 16)
            
            # Último día del mes
            if hoy.month == 12:
                siguiente_mes = date(hoy.year + 1, 1, 1)
            else:
                siguiente_mes = date(hoy.year, hoy.month + 1, 1)
            
            ultimo_dia = siguiente_mes - timedelta(days=1)
            
            app.logger.info(f"Actualizando facturas de la segunda quincena: {primer_dia} - {ultimo_dia}")
            resultado = get_facturas_by_date_range(primer_dia, ultimo_dia)
            
            app.logger.info(f"Resultado de la actualización segunda quincena: {resultado}")
            return resultado
        except Exception as e:
            app.logger.exception(f"Error al actualizar facturas de la segunda quincena: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def actualizar_facturas_diarias():
    """
    Actualiza las facturas del día actual
    Ejecuta diariamente a las 23:00 hora de Bogotá
    """
    with app.app_context():
        try:
            # Obtener la zona horaria de Bogotá
            bogota_tz = pytz.timezone('America/Bogota')

            # Obtener la fecha y hora actual en la zona horaria de Bogotá
            hoy = datetime.now(bogota_tz)

            # Calcular la fecha de ayer
            ayer = hoy - timedelta(days=1)

            # Obtener el rango de fechas para el día de ayer (solo el día completo)
            fecha_inicio = datetime(ayer.year, ayer.month, ayer.day, 0, 0, 0, tzinfo=bogota_tz)  # Inicio del día de ayer
            fecha_fin = fecha_inicio + timedelta(days=1)  # Fin del día de ayer

            app.logger.info(f"Consultando facturas para el día de ayer: {fecha_inicio.date()}")  # Solo la fecha

            # Llamar a la función con el rango de fechas para el día de ayer
            resultado = get_facturas_by_date_range(fecha_inicio, fecha_fin)

            app.logger.info(f"Resultado de la consulta: {resultado}")

            return resultado

        except Exception as e:
            app.logger.exception(f"Error al consultar facturas para el día de ayer: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Configuración del programador de tareas
def configurar_tareas_programadas():
    """
    Configura todas las tareas programadas relacionadas con facturas
    """
    try:
        # Programar la actualización de la primera quincena (día 15 a las 23:00)
        scheduler.add_job(
            actualizar_facturas_primera_quincena,
            'cron',
            day='15',
            hour='23',
            minute='0',
            timezone=bogota_tz,
            id='actualizar_facturas_primera_quincena',
            replace_existing=True
        )

        # Programar la actualización de la segunda quincena (último día del mes a las 23:00)
        scheduler.add_job(
            actualizar_facturas_segunda_quincena,
            'cron',
            day='last',
            hour='23',
            minute='0',
            timezone=bogota_tz,
            id='actualizar_facturas_segunda_quincena',
            replace_existing=True
        )

        # Programar la actualización diaria (todos los días a las 23:00)
        scheduler.add_job(
            actualizar_facturas_diarias,
            'cron',
            hour='23',
            minute='00',
            timezone=bogota_tz,
            id='actualizar_facturas_diarias',
            replace_existing=True
        )
        
        app.logger.info("Tareas de actualización de facturas configuradas correctamente")
        
    except Exception as e:
        app.logger.error(f"Error al configurar tareas programadas para facturas: {str(e)}")

# Iniciar el scheduler
try:
    # Configurar tareas
    configurar_tareas_programadas()
    
    # Iniciar el programador
    if not scheduler.running:
        scheduler.start()
        print(f"SCHEDULER INICIADO: {datetime.now(bogota_tz).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("El scheduler ya está en ejecución")
        
except Exception as e:
    import traceback
    error_msg = traceback.format_exc()
    print(f"Error al iniciar el scheduler: {error_msg}")
    app.logger.error(f"Error al iniciar el scheduler: {str(e)}")
 
# Función para validar el formato del Excel

# Función para validar el formato del Excel
def validar_excel_facturas(df):
    """Valida que el DataFrame tenga las columnas requeridas para facturas"""
    columnas_requeridas = [
        'codigo_factura', 'nit', 'nombre_cliente', 'fecha_emision', 
        'fecha_vencimiento', 'bodega', 'ciudad', 'forma_pago', 
        'item', 'metodo_pago', 'tipo_operacion', 'nombre_vendedor', 
        'total', 'estado'
    ]
    
    columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
    if columnas_faltantes:
        raise ValueError(f"Columnas faltantes en el Excel: {', '.join(columnas_faltantes)}")
    
    # Verificar que existan datos
    if df.empty:
        raise ValueError("El archivo Excel no contiene datos")
    
    # Verificar que los códigos de factura no estén vacíos
    if df['codigo_factura'].isna().any():
        raise ValueError("Existen códigos de factura vacíos")
    
    return True

# Vista para la página de carga
@app.route('/facturas/upload', methods=['GET'])
def upload_page():
    return render_template('upload_facturas.html')

# Ruta para cargar facturas desde Excel

if __name__ == '__app__':
    app.run(port=os.getenv("PORT", default=5000))
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
 
logger = logging.getLogger(__name__)
 
app = Flask(__name__)
 
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
           
            items.extend(current_items)
            if len(current_items) < limit:
                break
           
            offset += limit
       
        return items
       
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
 

if __name__ == '__app__':
    app.run(port=os.getenv("PORT", default=5000))
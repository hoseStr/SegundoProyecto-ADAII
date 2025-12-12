import re
import numpy as np
from typing import Tuple, List

import re
from typing import Tuple, List

def parse_minizinc_output(output_text: str) -> Tuple[str, List[int], List[List[List[int]]]]:
    """
    Parsea la salida de MiniZinc para el problema MinPol.
    
    Returns:
        - polarizacion (str): Valor de la polarización final
        - q_final (List[int]): Distribución final de personas por opinión
        - x_matrices (List[List[List[int]]]): 3 matrices de movimientos [k][i][j] para k=1,2,3
    """
    
    # NOTA: La zona de búsqueda ya no se usa para polarización/q_final porque estos
    # valores se imprimen antes del separador final de MiniZinc (==========).
    
    # 1. Delimitar la zona de búsqueda (solo útil si el output tiene múltiples soluciones)
    last_solution_start = output_text.rfind("----------")
    if last_solution_start == -1:
        last_solution_start = output_text.rfind("==========")
    
    if last_solution_start != -1:
        # Usamos solo el texto después del último separador de solución como fallback
        search_area = output_text[last_solution_start:]
    else:
        search_area = output_text # Si no hay separador, usar todo el output

    # --- 2. EXTRAER POLARIZACIÓN FINAL (Busca en todo el output_text) ---
    polarizacion = "Valor no encontrado"
    
    # 1. Patrón para el formato de etiqueta: 'Polarizacion final: X.X'
    pol_match = re.search(r"Polarizacion\s+final:\s*([0-9]+\.[0-9]+|[0-9]+)\s*", output_text, re.IGNORECASE)
    
    # 2. Fallback para formato de variable MiniZinc: 'polarizacion = X.X;'
    if not pol_match:
        pol_match = re.search(r"polarizacion\s*=\s*([0-9]+\.[0-9]+|[0-9]+)\s*;", output_text, re.IGNORECASE)
    
    if pol_match:
        # Captura el valor y limpia el ';' final si existe
        polarizacion = pol_match.group(1).strip().rstrip(';')

    # --- 3. EXTRAER DISTRIBUCIÓN FINAL (Busca en todo el output_text) ---
    q_final = []
    
    # 1. Patrón para el bloque de texto: 'Distribucion final...' hasta 'Mediana:', 'Costo total', o 'Movimientos'
    dist_block_match = re.search(
        r"Distribucion\s+final\s+de\s+personas\s+por\s+opinion:\s*\n(.+?)(?:Mediana:|Costo total|Movimientos totales)", 
        output_text, 
        re.DOTALL | re.IGNORECASE
    )
    
    if dist_block_match:
        dist_text = dist_block_match.group(1)
        # Buscar líneas con formato "Opinion X: Y personas"
        opinion_matches = re.findall(r"Opinion\s+\d+:\s*(\d+)\s+personas", dist_text, re.IGNORECASE)
        try:
            # Convertir a lista de enteros. Esto producirá [0, 10, 0] para tu ejemplo.
            q_final = [int(x) for x in opinion_matches]
        except ValueError:
            q_final = ["Error de parsing en bloque etiquetado"]

    # --- 4. EXTRAER MATRICES DE MOVIMIENTOS (Busca en todo el output_text, como debe ser) ---
    x_matrices = []
    
    for k in range(1, 4):  # k = 1, 2, 3
        # Patrones que buscan las etiquetas '=== MATRIZ DE MOVIMIENTOS...'
        if k == 1:
            pattern = r"=== MATRIZ DE MOVIMIENTOS \(Resistencia Baja, k=1\) ===\s*\n(.+?)(?:\n\n|=== MATRIZ DE MOVIMIENTOS \(Resistencia Media, k=2\)|===|\Z)"
        elif k == 2:
            pattern = r"=== MATRIZ DE MOVIMIENTOS \(Resistencia Media, k=2\) ===\s*\n(.+?)(?:\n\n|=== MATRIZ DE MOVIMIENTOS \(Resistencia Alta, k=3\)|===|\Z)"
        else:
            pattern = r"=== MATRIZ DE MOVIMIENTOS \(Resistencia Alta, k=3\) ===\s*\n(.+?)(?:\n\n|===|\Z)"
        
        matriz_match = re.search(pattern, output_text, re.DOTALL | re.IGNORECASE)
        
        if matriz_match:
            matriz_str = matriz_match.group(1).strip()
            filas = [f.strip() for f in matriz_str.split('\n') if f.strip()]
            
            matriz_k = []
            for fila in filas:
                # Quitar corchetes/espacios/etc. y SEPARAR POR COMAS o ESPACIOS MÚLTIPLES
                clean_fila = re.sub(r'[\[\]]', '', fila)
                elementos = [e.strip() for e in re.split(r',\s*|\s+', clean_fila) if e.strip()]
                
                try:
                    matriz_k.append([int(e) for e in elementos])
                except ValueError:
                    continue
            
            x_matrices.append(matriz_k)
        else:
            x_matrices.append([])
    
    return polarizacion, q_final, x_matrices


def parse_dzn_input(dzn_path: str) -> dict:
    # Esta función no se modificó ya que el parsing de DZN estaba correcto.
    params = {}
    
    try:
        with open(dzn_path, 'r') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"Error: Archivo DZN no encontrado en la ruta: {dzn_path}")
        return {}
    
    # ... (El resto del código de parse_dzn_input sigue aquí)
    lines = [line.strip() for line in content.split(';') if line.strip()]
    
    for line in lines:
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            if key == 'n':
                params['n'] = int(value)
            elif key == 'm':
                params['m'] = int(value)
            elif key == 'p':
                # Array de enteros: [3, 3, 4]
                params['p'] = [int(x.strip()) for x in value.strip('[]').split(',')]
            elif key == 'v':
                # Array de floats: [0.297, 0.673, 0.809]
                params['v'] = [float(x.strip()) for x in value.strip('[]').split(',')]
            elif key == 's':
                # Matriz 2D: [| 1,2,0 | 0,3,0 | 2,1,1 |]
                # Extraer contenido entre [| y |]
                start = value.find('[|')
                end = value.rfind('|]')
                if start != -1 and end != -1:
                    matrix_content = value[start+2:end]
                    filas = [f.strip() for f in matrix_content.split('|') if f.strip()]
                    
                    s_matrix = []
                    for fila in filas:
                        elementos = [int(x.strip()) for x in fila.split(',') if x.strip()]
                        s_matrix.append(elementos)
                    
                    params['s'] = s_matrix
            elif key == 'ct':
                params['ct'] = float(value)
            elif key == 'maxMovs':
                params['maxMovs'] = float(value)
    
    return params
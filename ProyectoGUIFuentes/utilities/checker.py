import numpy as np
from typing import List

def verificar_solucion(x: List[List[List[int]]], p: List[int], s: List[List[int]], 
                       v: List[float], n: int, m: int, ct_max: float, maxMovs: float) -> str:
    """
    Verifica la validez de una solución para el problema MinPol.
    
    Parámetros:
        x: Lista de 3 matrices m×m (una por nivel de resistencia k=1,2,3)
        p: Distribución inicial de personas por opinión
        s: Matriz m×3 con cantidad de personas por opinión y resistencia
        v: Valores de las opiniones
        n: Total de personas
        m: Número de opiniones
        ct_max: Costo total máximo permitido
        maxMovs: Movimientos máximos permitidos
    
    Returns:
        String con el reporte de verificación
    """
    
    result = []
    result.append("=" * 60)
    result.append("VERIFICACIÓN DE SOLUCIÓN - MinPol")
    result.append("=" * 60)
    result.append("")
    
    # Convertir a numpy arrays para facilitar cálculos
    x_arrays = [np.array(x[k]) for k in range(3)]  # x[0]=baja, x[1]=media, x[2]=alta
    p_array = np.array(p)
    s_array = np.array(s)
    v_array = np.array(v)
    
    # Factores de resistencia
    resistencia = [1.0, 1.5, 2.0]
    
    valido = True
    
    # ===== RESTRICCIÓN 1: No mover más personas de las disponibles por resistencia =====
    result.append("📋 Restricción 1: Conservación por resistencia")
    for k in range(3):
        for i in range(m):
            movimientos_desde_i = x_arrays[k][i].sum()
            disponibles = s_array[i][k]
            
            if movimientos_desde_i > disponibles:
                result.append(f"  ❌ Resistencia {k+1}, Opinión {i+1}: se mueven {movimientos_desde_i} "
                            f"pero solo hay {disponibles} disponibles")
                valido = False
    
    if valido:
        result.append("  ✅ Todas las restricciones de conservación se cumplen")
    result.append("")
    
    # ===== RESTRICCIÓN 2: No auto-movimientos =====
    result.append("📋 Restricción 2: No auto-movimientos")
    auto_movs = False
    for k in range(3):
        for i in range(m):
            if x_arrays[k][i][i] > 0:
                result.append(f"  ❌ Resistencia {k+1}, Opinión {i+1}: hay {x_arrays[k][i][i]} auto-movimientos")
                valido = False
                auto_movs = True
    
    if not auto_movs:
        result.append("  ✅ No hay auto-movimientos")
    result.append("")
    
    # ===== RESTRICCIÓN 3: Distribución final =====
    result.append("📋 Restricción 3: Distribución final")
    
    # Calcular salidas y llegadas para cada opinión
    q_final = []
    for i in range(m):
        salidas = sum(x_arrays[k][i].sum() for k in range(3))
        llegadas = sum(x_arrays[k][:, i].sum() for k in range(3))
        q_i = p[i] - salidas + llegadas
        q_final.append(int(q_i))
    
    result.append(f"  Distribución inicial: {p}")
    result.append(f"  Distribución final:   {q_final}")
    
    total_final = sum(q_final)
    if total_final != n:
        result.append(f"  ❌ La suma de la distribución final ({total_final}) no es igual a n ({n})")
        valido = False
    else:
        result.append(f"  ✅ Total de personas se conserva: {total_final}")
    result.append("")
    
    # ===== RESTRICCIÓN 4: Límite de costo total =====
    result.append("📋 Restricción 4: Límite de costo total")
    
    costo_total = 0.0
    for k in range(3):
        for i in range(m):
            for j in range(m):
                if i != j and x_arrays[k][i][j] > 0:
                    costo_movimiento = x_arrays[k][i][j] * abs(i - j) * resistencia[k]
                    costo_total += costo_movimiento
    
    result.append(f"  Costo total usado: {costo_total:.2f}")
    result.append(f"  Costo máximo permitido: {ct_max:.2f}")
    
    if costo_total > ct_max + 0.01:  # Pequeña tolerancia por redondeo
        result.append(f"  ❌ El costo total excede el límite")
        valido = False
    else:
        result.append(f"  ✅ Costo dentro del límite ({(costo_total/ct_max*100):.1f}% usado)")
    result.append("")
    
    # ===== RESTRICCIÓN 5: Límite de movimientos =====
    result.append("📋 Restricción 5: Límite de movimientos")
    
    movimientos_totales = 0
    for k in range(3):
        for i in range(m):
            for j in range(m):
                if i != j:
                    movimientos_totales += x_arrays[k][i][j] * abs(i - j)
    
    result.append(f"  Movimientos usados: {movimientos_totales}")
    result.append(f"  Movimientos máximos: {int(maxMovs)}")
    
    if movimientos_totales > maxMovs + 0.01:
        result.append(f"  ❌ Los movimientos exceden el límite")
        valido = False
    else:
        result.append(f"  ✅ Movimientos dentro del límite ({(movimientos_totales/maxMovs*100):.1f}% usado)")
    result.append("")
    
    # ===== CÁLCULO DE POLARIZACIÓN =====
    result.append("📊 Cálculo de Polarización")
    
    # Calcular mediana ponderada
    q_array = np.array(q_final)
    pos_mediana = (n + 1) // 2
    acum = 0
    mediana = v_array[0]
    
    for i in range(m):
        acum += q_final[i]
        if acum >= pos_mediana:
            mediana = v_array[i]
            break
    
    result.append(f"  Mediana ponderada: {mediana:.3f}")
    
    # Calcular polarización
    polarizacion = sum(q_final[i] * abs(v_array[i] - mediana) for i in range(m))
    
    result.append(f"  Polarización calculada: {polarizacion:.6f}")
    result.append("")
    
    # ===== RESUMEN FINAL =====
    result.append("=" * 60)
    if valido:
        result.append("🎉 RESULTADO: SOLUCIÓN VÁLIDA")
        result.append("   Todas las restricciones se cumplen correctamente")
    else:
        result.append("❌ RESULTADO: SOLUCIÓN INVÁLIDA")
        result.append("   Una o más restricciones fueron violadas")
    result.append("=" * 60)
    
    # ===== DETALLE DE MOVIMIENTOS =====
    result.append("")
    result.append("📝 Detalle de movimientos por resistencia:")
    result.append("")
    
    for k in range(3):
        nivel = ["Baja", "Media", "Alta"][k]
        result.append(f"  Resistencia {nivel} (k={k+1}):")
        
        hay_movimientos = False
        for i in range(m):
            for j in range(m):
                if x_arrays[k][i][j] > 0:
                    hay_movimientos = True
                    result.append(f"    • {x_arrays[k][i][j]} persona(s) de opinión {i+1} → opinión {j+1}")
        
        if not hay_movimientos:
            result.append(f"    (Sin movimientos)")
        result.append("")
    
    return "\n".join(result)
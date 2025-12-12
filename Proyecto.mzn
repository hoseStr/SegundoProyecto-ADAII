% ============================================================================
% Proyecto: Minimización de Polarización en una Población (MinPol)
% Análisis de Algoritmos II
% ============================================================================

% ============================================================================
% PARÁMETROS
% ============================================================================

% Número total de personas
int: n;

% Número de opiniones posibles
int: m;

% Distribución inicial de personas por opinión
array[1..m] of int: p;

% Valores de las opiniones
array[1..m] of float: v;

% Matriz de resistencias: s[i,k] = número de personas con opinión i y resistencia k
% k=1: baja, k=2: media, k=3: alta
array[1..m, 1..3] of int: s;

% Costo total máximo permitido
float: ct;

% Cantidad máxima de movimientos permitidos
float: maxMovs;

% Factores de resistencia
array[1..3] of float: resistencia = [1.0, 1.5, 2.0];

% ============================================================================
% VARIABLES DE DECISIÓN
% ============================================================================

% x[k,i,j] = número de personas con resistencia k que se mueven de opinión i a j
array[1..3, 1..m, 1..m] of var 0..n: x;

% q[i] = número final de personas con opinión i
array[1..m] of var 0..n: q;

% Variable auxiliar para la mediana
var min(v)..max(v): med;

% Variable auxiliar para la polarización (para facilitar la minimización)
var 0.0..100000.0: polarizacion;

% ============================================================================
% RESTRICCIONES
% ============================================================================

% Restricción 1: No se pueden mover más personas de las disponibles por resistencia
constraint forall(k in 1..3, i in 1..m)(
    sum(j in 1..m)(x[k,i,j]) <= s[i,k]
);

% Restricción 2: No hay auto-movimientos (de una opinión a sí misma)
constraint forall(k in 1..3, i in 1..m)(
    x[k,i,i] = 0
);

% Restricción 3: Cálculo de la distribución final
% q[i] = personas iniciales - salidas + entradas
constraint forall(i in 1..m)(
    q[i] = p[i] 
           - sum(k in 1..3, j in 1..m)(x[k,i,j])  % salidas
           + sum(k in 1..3, j in 1..m)(x[k,j,i])  % entradas
);

% Restricción 4: Límite de costo total
constraint sum(k in 1..3, i in 1..m, j in 1..m)(
    x[k,i,j] * abs(i - j) * resistencia[k]
) <= ct;

% Restricción 5: Límite de movimientos
constraint sum(k in 1..3, i in 1..m, j in 1..m)(
    x[k,i,j] * abs(i - j)
) <= maxMovs;

% Restricción 6: Cálculo de la mediana ponderada
% La mediana es el valor v[i] donde la suma acumulada alcanza n/2
constraint
    let {
        var 1..m: idx_mediana;  % índice de la opinión que contiene la mediana
        array[1..m] of var 0..n: acumulado;
    } in (
        % Calcular acumulados
        acumulado[1] = q[1] /\
        forall(i in 2..m)(
            acumulado[i] = acumulado[i-1] + q[i]
        ) /\
        
        % Encontrar el índice donde está la mediana
        % La mediana está en idx_mediana si:
        % - acumulado[idx_mediana-1] < n/2 (o idx_mediana = 1)
        % - acumulado[idx_mediana] >= n/2
        (idx_mediana = 1 \/ acumulado[idx_mediana-1] * 2 < n) /\
        acumulado[idx_mediana] * 2 >= n /\
        
        % Asignar el valor de la mediana
        med = v[idx_mediana]
    );

% Restricción 7: Cálculo de la polarización
constraint polarizacion = sum(i in 1..m)(
    q[i] * abs(v[i] - med)
);

% ============================================================================
% FUNCIÓN OBJETIVO
% ============================================================================

solve minimize polarizacion;

% ============================================================================
% SALIDA
% ============================================================================

output [
    "Polarizacion final: " ++ show(polarizacion) ++ "\n\n"
] ++
[
    "Distribucion final de personas por opinion:\n"
] ++
[
    "Opinion " ++ show(i) ++ ": " ++ show(q[i]) ++ " personas\n"
    | i in 1..m
] ++
[
    "\nMediana: " ++ show(med) ++ "\n\n"
] ++
[
    "Costo total usado: " ++ show(sum(k in 1..3, i in 1..m, j in 1..m)(
        x[k,i,j] * abs(i - j) * resistencia[k]
    )) ++ " de " ++ show(ct) ++ "\n"
] ++
[
    "Movimientos totales: " ++ show(sum(k in 1..3, i in 1..m, j in 1..m)(
        x[k,i,j] * abs(i - j)
    )) ++ " de " ++ show(maxMovs) ++ "\n\n"
] ++
[
    "=== MATRIZ DE MOVIMIENTOS (Resistencia Baja, k=1) ===\n"
] ++
[
    if j = 1 then "  " else "" endif ++
    show(x[1,i,j]) ++
    if j = m then "\n" else "," endif
    | i in 1..m, j in 1..m
] ++
[
    "\n=== MATRIZ DE MOVIMIENTOS (Resistencia Media, k=2) ===\n"
] ++
[
    if j = 1 then "  " else "" endif ++
    show(x[2,i,j]) ++
    if j = m then "\n" else "," endif
    | i in 1..m, j in 1..m
] ++
[
    "\n=== MATRIZ DE MOVIMIENTOS (Resistencia Alta, k=3) ===\n"
] ++
[
    if j = 1 then "  " else "" endif ++
    show(x[3,i,j]) ++
    if j = m then "\n" else "," endif
    | i in 1..m, j in 1..m
];

% ============================================================================
% FORMATO DE SALIDA PARA ARCHIVO (según especificación del proyecto)
% ============================================================================
% Para generar el archivo de salida .txt según formato especificado:
% Línea 1: polarización final (entero)
% Línea 2: nivel de resistencia (1)
% Siguientes m líneas: matriz de movimientos para resistencia baja
% Línea siguiente: nivel de resistencia (2)
% Siguientes m líneas: matriz de movimientos para resistencia media
% Línea siguiente: nivel de resistencia (3)
% Siguientes m líneas: matriz de movimientos para resistencia alta
%
% Para usar este formato, descomentar esta sección y comentar el output anterior

/*
output [
    show(floor(polarizacion)) ++ "\n"
] ++
[
    "1\n"
] ++
[
    show(x[1,i,j]) ++ if j < m then "," else "\n" endif
    | i in 1..m, j in 1..m
] ++
[
    "2\n"
] ++
[
    show(x[2,i,j]) ++ if j < m then "," else "\n" endif
    | i in 1..m, j in 1..m
] ++
[
    "3\n"
] ++
[
    show(x[3,i,j]) ++ if j < m then "," else "\n" endif
    | i in 1..m, j in 1..m
];
*/
import sys
import subprocess
import re
from typing import List
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QTextEdit,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import QColor, QIcon, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os
import glob
import platform
import PyQt6.QtCore as QtCore
from PyQt6.QtCore import QObject

# Importar utilities
from utilities.parser import parse_minizinc_output, parse_dzn_input
from utilities.checker import verificar_solucion

# ==================== WORKER ====================
class MinizincWorker(QObject):
    outputReady = pyqtSignal(str)
    finished = pyqtSignal(str, bool)
    errorOccurred = pyqtSignal(str)

    def __init__(self, model_path, dzn_path):
        super().__init__()
        self.model_path = model_path
        self.dzn_path = dzn_path
        self._is_interrupted = False
        self.process = None
        self._last_output_lines = []

    def interrupt(self):
        self._is_interrupted = True
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _find_gurobi_dll(self):
        """Busca automáticamente la DLL de Gurobi en PATH y ubicaciones comunes"""
        # Primero: Buscar en el PATH del sistema
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        
        if platform.system() == "Windows":
            dll_pattern = "gurobi*.dll"
            
            # Buscar en cada directorio del PATH
            for path_dir in path_dirs:
                if os.path.exists(path_dir):
                    dll_files = glob.glob(os.path.join(path_dir, dll_pattern))
                    if dll_files:
                        return dll_files[0]
            
            # Si no se encontró en PATH, buscar en ubicaciones comunes
            search_paths = [
                r"C:\gurobi*\win64\bin\gurobi*.dll",
                r"C:\Program Files\gurobi*\win64\bin\gurobi*.dll",
            ]
            
            # Si existe GUROBI_HOME, buscar ahí también
            gurobi_home = os.environ.get('GUROBI_HOME')
            if gurobi_home:
                search_paths.append(os.path.join(gurobi_home, 'bin', 'gurobi*.dll'))
            
            for pattern in search_paths:
                matches = glob.glob(pattern)
                if matches:
                    return matches[0]
        
        elif platform.system() == "Linux":
            so_pattern = "libgurobi*.so"
            
            # Buscar en PATH
            for path_dir in path_dirs:
                if os.path.exists(path_dir):
                    so_files = glob.glob(os.path.join(path_dir, so_pattern))
                    if so_files:
                        return so_files[0]
            
            # Buscar en LD_LIBRARY_PATH
            ld_path_dirs = os.environ.get('LD_LIBRARY_PATH', '').split(os.pathsep)
            for ld_dir in ld_path_dirs:
                if os.path.exists(ld_dir):
                    so_files = glob.glob(os.path.join(ld_dir, so_pattern))
                    if so_files:
                        return so_files[0]
            
            search_paths = [
                "/opt/gurobi*/linux64/lib/libgurobi*.so",
                "/usr/local/gurobi*/linux64/lib/libgurobi*.so",
            ]
            
            gurobi_home = os.environ.get('GUROBI_HOME')
            if gurobi_home:
                search_paths.append(os.path.join(gurobi_home, 'lib', 'libgurobi*.so'))
            
            for pattern in search_paths:
                matches = glob.glob(pattern)
                if matches:
                    return matches[0]
        
        elif platform.system() == "Darwin":  # macOS
            dylib_pattern = "libgurobi*.dylib"
            
            for path_dir in path_dirs:
                if os.path.exists(path_dir):
                    dylib_files = glob.glob(os.path.join(path_dir, dylib_pattern))
                    if dylib_files:
                        return dylib_files[0]
            
            search_paths = [
                "/Library/gurobi*/macos_universal2/lib/libgurobi*.dylib",
            ]
            
            gurobi_home = os.environ.get('GUROBI_HOME')
            if gurobi_home:
                search_paths.append(os.path.join(gurobi_home, 'lib', 'libgurobi*.dylib'))
            
            for pattern in search_paths:
                matches = glob.glob(pattern)
                if matches:
                    return matches[0]
        
        return None

    def _run_minizinc_command(self, command, suppress_dll_errors=False, cwd=None):
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                shell=True if os.name == 'nt' else False,
                cwd=cwd
            )

            dll_error_detected = False
            
            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is None:
                    break
                if line:
                    stripped = line.strip()

                    # Filtrar avisos de conflicto de nombre cuando el archivo local
                    # `Proyecto.mzn` existe intencionalmente en el directorio de trabajo
                    try:
                        if 'included from library' in stripped and os.path.basename(self.model_path) in stripped:
                            continue
                    except Exception:
                        pass
                    
                    # Detectar error de DLL de Gurobi
                    if "cannot load gurobi dll" in stripped.lower():
                        dll_error_detected = True
                        if suppress_dll_errors:
                            continue  # No mostrar este mensaje ni guardarlo
                    
                    self._last_output_lines.append(stripped)
                    
                    # Si suppress_dll_errors está activo y hay error de DLL, no mostrar nada
                    if not (suppress_dll_errors and dll_error_detected):
                        self.outputReady.emit(stripped + "\n")
                        
                if self._is_interrupted:
                    self.process.terminate()
                    break

            self.process.wait()
            
            # Si se detectó error de DLL, considerarlo como fallo
            if dll_error_detected:
                return False
                
            return self.process.returncode == 0

        except Exception as e:
            self.errorOccurred.emit(f"Excepción al ejecutar MiniZinc: {str(e)}")
            return False

    def run(self):
        success = False
        try:
            if not os.path.exists(self.model_path):
                self.errorOccurred.emit(f"Archivo modelo no encontrado: {self.model_path}")
                return

            if not os.path.exists(self.dzn_path):
                self.errorOccurred.emit(f"Archivo de datos no encontrado: {self.dzn_path}")
                return

            gurobi_available = self._check_solver_available("gurobi")
            
            if gurobi_available:
                self.outputReady.emit("🔍 Intentando con solver Gurobi...\n")
                
                # Buscar automáticamente la DLL de Gurobi
                gurobi_dll = self._find_gurobi_dll()
                
                if gurobi_dll:
                    self.outputReady.emit(f"   ✓ DLL encontrada: {os.path.basename(gurobi_dll)}\n")
                    command = [
                        "minizinc", "-I", os.path.dirname(self.model_path), "--solver", "gurobi", 
                        "--gurobi-dll", gurobi_dll,
                        self.model_path, self.dzn_path
                    ]
                else:
                    self.outputReady.emit("   Intentando sin especificar DLL...\n")
                    command = [
                        "minizinc", "-I", os.path.dirname(self.model_path), "--solver", "gurobi",
                        self.model_path, self.dzn_path
                    ]
                
                success = self._run_minizinc_command(command, suppress_dll_errors=True, cwd=os.path.dirname(self.model_path))
                
                # Si Gurobi falló, cambiar a Gecode
                if not success and not self._is_interrupted:
                    self.outputReady.emit("\n⚠️ Gurobi no disponible, usando Gecode...\n\n")
                    # Limpiar las líneas de salida de Gurobi
                    self._last_output_lines = []

            # Si Gurobi no estaba disponible o falló, usar Gecode
            if not success and not self._is_interrupted:
                if not gurobi_available:
                    self.outputReady.emit("🔍 Usando solver Gecode...\n")
                
                success = self._run_minizinc_command(
                    ["minizinc", "-I", os.path.dirname(self.model_path), "--solver", "gecode", "--time-limit", "120000", 
                    self.model_path, self.dzn_path],
                    suppress_dll_errors=False,
                    cwd=os.path.dirname(self.model_path)
                )

            if self._is_interrupted:
                if self._last_output_lines:
                    self.outputReady.emit("⏸️ Interrumpido por el usuario, última salida conocida:\n")
                else:
                    self.outputReady.emit("[Proceso interrumpido sin salida previa]")
            elif not success:
                self.errorOccurred.emit("❌ Ejecución fallida con todos los solvers disponibles")

        except Exception as e:
            self.errorOccurred.emit(f"Excepción general: {str(e)}")

        finally:
            output_str = "\n".join(self._last_output_lines) if self._last_output_lines else ""
            self.finished.emit(output_str, not self._is_interrupted and success)
    
    def _check_solver_available(self, solver_name):
        try:
            if solver_name.lower() == "gurobi":
                # Intenta una ejecución de prueba simple
                test_result = subprocess.run(
                    ["minizinc", "--solver", "gurobi", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Si hay error de DLL, retorna False
                if "cannot load gurobi dll" in test_result.stderr.lower():
                    return False
            
            result = subprocess.run(
                ["minizinc", "--solvers"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return solver_name.lower() in result.stdout.lower()
        except:
            return False

# ==================== STYLESHEET ====================
DARK_MODE_STYLESHEET = """
    /* === Ventana Principal === */
    QWidget#mainWindow {
        background-color: #1a1a1a;
        font-family: 'Segoe UI', 'Arial', sans-serif;
    }

    /* === Header === */
    QFrame#headerFrame {
        background-color: #242424;
        border-radius: 12px;
        border: 1px solid #333333;
        padding: 12px;
    }

    QLabel#headerTitle {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
    }

    QLabel#headerSubtitle {
        font-size: 13px;
        color: #a0a0a0;
        font-weight: 400;
    }

    /* === Tarjetas === */
    QFrame#cardFrame {
        background-color: #242424;
        border-radius: 12px;
        border: 1px solid #333333;
        padding: 3px;
    }

    QLabel#cardTitle {
        font-size: 18px;
        font-weight: 600;
        color: #ffffff;
        padding: 10px 15px;
        background-color: #2a2a2a;
        border-radius: 8px;
        margin: 6px;
    }

    /* === Botones === */
    QPushButton {
        border-radius: 8px;
        padding: 10px 18px;
        font-size: 14px;
        font-weight: 600;
        border: none;
        color: #ffffff;
    }

    QPushButton:disabled {
        background-color: #2a2a2a;
        color: #606060;
    }

    /* Botón Principal */
    QPushButton#primaryButton {
        background-color: #3b82f6;
        border: 1px solid #2563eb;
    }

    QPushButton#primaryButton:hover {
        background-color: #2563eb;
        border: 1px solid #1d4ed8;
    }

    QPushButton#primaryButton:pressed {
        background-color: #1d4ed8;
    }

    /* Botón Secundario */
    QPushButton#secondaryButton {
        background-color: #10b981;
        border: 1px solid #059669;
    }

    QPushButton#secondaryButton:hover {
        background-color: #059669;
        border: 1px solid #047857;
    }

    QPushButton#secondaryButton:pressed {
        background-color: #047857;
    }

    /* Botón Terciario */
    QPushButton#tertiaryButton {
        background-color: #2a2a2a;
        border: 1px solid #404040;
        color: #ffffff;
    }

    QPushButton#tertiaryButton:hover {
        background-color: #333333;
        border: 1px solid #4a4a4a;
    }

    QPushButton#tertiaryButton:pressed {
        background-color: #3a3a3a;
    }

    QPushButton#tertiaryButton:checked {
        background-color: #8b5cf6;
        border: 1px solid #7c3aed;
    }

    /* Botón de Detener */
    QPushButton#stopButton {
        background-color: #ef4444;
        border: 1px solid #dc2626;
    }

    QPushButton#stopButton:hover {
        background-color: #dc2626;
        border: 1px solid #b91c1c;
    }

    QPushButton#stopButton:pressed {
        background-color: #b91c1c;
    }

    /* === Contenedor READY === */
    QFrame#readyContainer {
        background-color: #1a2e1a;
        border-radius: 12px;
        border: 1px solid #10b981;
        padding: 20px;
        margin: 10px;
    }

    QLabel#readyText {
        color: #10b981;
        font-weight: 600;
        font-size: 15px;
    }

    /* === TextEdit === */
    QTextEdit {
        background-color: #1e1e1e;
        border: 1px solid #333333;
        border-radius: 8px;
        padding: 20px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 13px;
        color: #d4d4d4;
    }

    QTextEdit:focus {
        border: 1px solid #3b82f6;
    }

    /* === ScrollBar === */
    QScrollBar:vertical {
        background-color: #1e1e1e;
        width: 12px;
        border-radius: 6px;
        margin: 0px;
    }

    QScrollBar::handle:vertical {
        background-color: #404040;
        border-radius: 6px;
        min-height: 30px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #4a4a4a;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }

    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    /* === Labels === */
    QLabel {
        color: #ffffff;
    }

    QLabel#placeholderLabel {
        font-size: 16px;
        color: #808080;
        font-style: italic;
    }
"""

# ==================== CLASE GUI ====================
class MinPolGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("mainWindow")
        self.setWindowTitle("MinPol - Minimización de Polarización")
        self.setFixedSize(900, 750) 
        self.setStyleSheet(DARK_MODE_STYLESHEET)
        
        self.current_file_path = None
        self.current_dzn_path = None
        self.numero_prueba = None
        self.last_output = None
        self.last_x_matrices = None
        self.last_polarizacion = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # Header
        self.header = self._crear_header()
        main_layout.addWidget(self.header)
        
        # Contenido principal
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)

        left_column = QVBoxLayout()
        left_column.setSpacing(10)

        self.data_entry_card = self._crear_tarjeta_entrada_datos()
        self.actions_card = self._crear_tarjeta_acciones()
        self.results_card = self._crear_tarjeta_visualizacion()

        left_column.addWidget(self.data_entry_card)
        left_column.addWidget(self.actions_card)
        left_column.addStretch(1)

        columns_layout.addLayout(left_column, 1)
        columns_layout.addWidget(self.results_card, 2)

        main_layout.addLayout(columns_layout)

    def _crear_header(self):
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 12, 15, 12)
        header_layout.setSpacing(5)

        title_label = QLabel("MinPol")
        title_label.setObjectName("headerTitle")
        
        subtitle_label = QLabel("Minimización de Polarización en Poblaciones")
        subtitle_label.setObjectName("headerSubtitle")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        
        return self._apply_shadow(header_frame, 20)

    def _apply_shadow(self, widget, blur_radius=20):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur_radius)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        widget.setGraphicsEffect(shadow)
        return widget

    def _crear_tarjeta_entrada_datos(self):
        card = QFrame()
        card.setObjectName("cardFrame")
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 10)

        title = QLabel("Entrada de Datos")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        self.entry_buttons_container = QWidget()
        entry_layout = QVBoxLayout(self.entry_buttons_container)
        entry_layout.setContentsMargins(12, 10, 12, 10)
        entry_layout.setSpacing(8)

        self.import_txt_button = QPushButton("Importar Archivo TXT")
        self.import_txt_button.setObjectName("tertiaryButton")
        self.import_txt_button.setMinimumHeight(50)
        self.import_txt_button.clicked.connect(self._importar_archivo_txt)

        self.import_dzn_button = QPushButton("Importar Archivo DZN")
        self.import_dzn_button.setObjectName("tertiaryButton")
        self.import_dzn_button.setMinimumHeight(50)
        self.import_dzn_button.clicked.connect(self._importar_archivo_dzn)

        entry_layout.addWidget(self.import_txt_button)
        entry_layout.addWidget(self.import_dzn_button)

        layout.addWidget(self.entry_buttons_container)

        # Contenedor READY
        self.ready_container = QFrame()
        self.ready_container.setObjectName("readyContainer")
        ready_layout = QVBoxLayout(self.ready_container)
        ready_layout.setContentsMargins(20, 20, 20, 20)
        ready_layout.setSpacing(15)

        ready_header = QHBoxLayout()
        
        self.check_icon = QLabel("✅")
        self.check_icon.setStyleSheet("font-size: 28px;")
        
        self.ready_text = QLabel()
        self.ready_text.setObjectName("readyText")
        self.ready_text.setWordWrap(True)
        
        ready_header.addWidget(self.check_icon)
        ready_header.addWidget(self.ready_text, 1)
        
        self.back_button = QPushButton("Cambiar Archivo")
        self.back_button.setObjectName("tertiaryButton")
        self.back_button.setMinimumHeight(45)
        self.back_button.clicked.connect(self._volver_a_botones)

        ready_layout.addLayout(ready_header)
        ready_layout.addWidget(self.back_button)
            
        self.ready_container.setVisible(False)
        layout.addWidget(self.ready_container)

        return self._apply_shadow(card)

    def _crear_tarjeta_visualizacion(self):
        card = QFrame()
        card.setObjectName("cardFrame")
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 10)

        title = QLabel("Resultados y Salida")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        
        self.results_output = QTextEdit()
        self.results_output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.results_output.setReadOnly(True)
        self.results_output.setText("Ejecuta el modelo para ver los resultados aquí...")
        
        layout.addWidget(self.results_output, 1)
        
        return self._apply_shadow(card)
    
    def _crear_tarjeta_acciones(self):
        card = QFrame()
        card.setObjectName("cardFrame")
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 5)

        title = QLabel("Acciones Principales")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        buttons_container = QWidget()
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(12, 10, 12, 10)
        buttons_layout.setSpacing(8)

        self.execute_button = QPushButton("Ejecutar Modelo")
        self.execute_button.setObjectName("primaryButton")
        self.execute_button.setMinimumHeight(30)
        self.execute_button.setEnabled(False)
        self.execute_button.clicked.connect(self._ejecutar_modelo)

        self.check_button = QPushButton("Revisar Resultados")
        self.check_button.setObjectName("secondaryButton")
        self.check_button.setMinimumHeight(55)
        self.check_button.setEnabled(False)
        self.check_button.clicked.connect(self._revisar_resultados)

        self.stop_button = QPushButton("Detener Ejecución")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setMinimumHeight(55)
        self.stop_button.clicked.connect(self._stop_execution)
        self.stop_button.setVisible(False)

        buttons_layout.addWidget(self.execute_button)
        buttons_layout.addWidget(self.check_button)
        buttons_layout.addWidget(self.stop_button)

        layout.addWidget(buttons_container)
        
        return self._apply_shadow(card)

    # ==================== MÉTODOS LÓGICOS ====================
    
    def _extraer_numero_prueba(self, file_path: str) -> str:
        """
        Extrae el número de la prueba del nombre del archivo.
        Ejemplos: 'Prueba20.txt' -> '20', 'Prueba7.dzn' -> '7'
        """
        filename = os.path.basename(file_path)
        # Buscar patrón: Prueba{NUMERO} o cualquier número en el nombre
        match = re.search(r'Prueba(\d+)', filename, re.IGNORECASE)
        if match:
            return match.group(1)
        # Si no encuentra "Prueba", buscar cualquier número
        match = re.search(r'(\d+)', filename)
        if match:
            return match.group(1)
        return ""
    
    def _volver_a_botones(self):
        self.entry_buttons_container.setVisible(True)
        self.ready_container.setVisible(False)
        self.current_file_path = None
        self.current_dzn_path = None
        self.numero_prueba = None
        self.execute_button.setEnabled(False)
        self.check_button.setEnabled(False)
        self.results_output.setText("Ejecuta el modelo para ver los resultados aquí...")

    def _importar_archivo_txt(self):
        options = QFileDialog.Option.ReadOnly
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo TXT", "",
            "Archivos de Texto (*.txt);;Todos los archivos (*)", options=options
        )
        
        if file_path:
            self.current_file_path = file_path
            self.numero_prueba = self._extraer_numero_prueba(file_path)
            success = self._convertir_txt_a_dzn(file_path)
            
            if success:
                self.ready_text.setText(f"{os.path.basename(self.current_file_path)} correctamente cargado")
                self._mostrar_estado_listo()
            else:
                self._limpiar_estado_archivos()

    def _importar_archivo_dzn(self):
        options = QFileDialog.Option.ReadOnly
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo DZN", "",
            "Archivos DZN (*.dzn);;Todos los archivos (*)", options=options
        )
        
        if file_path:
            self.current_file_path = file_path
            self.current_dzn_path = file_path
            self.numero_prueba = self._extraer_numero_prueba(file_path)
            self.ready_text.setText(f"Archivo DZN cargado: {os.path.basename(file_path)}")
            self._mostrar_estado_listo()

    def _mostrar_estado_listo(self):
        self.entry_buttons_container.setVisible(False)
        self.ready_container.setVisible(True)
        self.execute_button.setEnabled(True)
        self.check_button.setEnabled(False)

    def _limpiar_estado_archivos(self):
        self.current_file_path = None
        self.current_dzn_path = None
        self.numero_prueba = None
        self.execute_button.setEnabled(False)
        self.check_button.setEnabled(False)

    def _convertir_txt_a_dzn(self, txt_file_path):
        try:
            import tempfile
            
            # Crear archivo DZN temporal sin crear directorios en BateriaPruebas
            base_name = os.path.splitext(os.path.basename(txt_file_path))[0]
            temp_dir = tempfile.gettempdir()
            dzn_file_path = os.path.join(temp_dir, f"{base_name}.dzn")
            self.current_dzn_path = dzn_file_path
            
            with open(txt_file_path, 'r') as txt_file:
                lines = [line.strip() for line in txt_file.readlines() if line.strip()]
            
            if len(lines) < 7:
                raise ValueError("El archivo no tiene el formato esperado (mínimo 7 líneas).")
            
            n = lines[0]
            m = int(lines[1])
            p = '[' + lines[2].replace(',', ', ') + ']'
            v = '[' + lines[3].replace(',', ', ') + ']'
            
            matrix_lines = []
            if len(lines) < 4 + m:
                raise ValueError(f"El valor de 'm' ({m}) no coincide con la cantidad de filas esperadas.")
                
            for i in range(m):
                matrix_lines.append(lines[4 + i])
            
            s_content = ' |\n        '.join(matrix_lines)
            s = f"[| {s_content} |]"
            
            ct = lines[4 + m]
            maxMovs = lines[5 + m]
            
            with open(dzn_file_path, 'w') as dzn_file:
                dzn_file.write(f"n = {n};\n")
                dzn_file.write(f"m = {m};\n\n")
                dzn_file.write(f"p = {p};\n\n")
                dzn_file.write(f"v = {v};\n\n")
                dzn_file.write(f"s = {s};\n\n")
                dzn_file.write(f"ct = {ct};\n\n")
                dzn_file.write(f"maxMovs = {maxMovs};")
                
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error de Conversión", f"Error al convertir archivo:\n{str(e)}")
            self.results_output.setText(f"❌ Error al convertir archivo:\n{str(e)}")
            return False

    def _ejecutar_modelo(self):
        self.import_txt_button.setEnabled(False)
        self.import_dzn_button.setEnabled(False)
        self.execute_button.setEnabled(False)
        self.check_button.setEnabled(False)
        
        if self.current_dzn_path and os.path.exists(self.current_dzn_path):
            try:
                self._set_ui_during_execution(True)
                self.results_output.clear()
                
                model_path = os.path.join(os.path.dirname(__file__), "../Proyecto.mzn")
                
                if not os.path.exists(model_path):
                    self.results_output.setText(f"❌ Error: No se encontró Proyecto.mzn")
                    self._set_ui_during_execution(False)
                    self.execute_button.setEnabled(True)
                    return

                # Crear directorio DatosProyecto y guardar los datos de prueba
                proyecto_dir = os.path.join(os.path.dirname(model_path), "DatosProyecto")
                try:
                    # Crear el directorio si no existe
                    os.makedirs(proyecto_dir, exist_ok=True)
                    
                    # Determinar el nombre del archivo DZN con el número de prueba
                    if self.numero_prueba:
                        dzn_filename = f"DatosProyecto{self.numero_prueba}.dzn"
                    else:
                        dzn_filename = "DatosProyecto.dzn"
                    
                    # Guardar el archivo DZN en el directorio
                    datos_proyecto_path = os.path.join(proyecto_dir, dzn_filename)
                    with open(self.current_dzn_path, 'r') as source_file:
                        dzn_content = source_file.read()
                    
                    with open(datos_proyecto_path, 'w') as target_file:
                        target_file.write(dzn_content)
                    
                    # Mostrar mensaje inicial con información del directorio creado
                    initial_message = f"Ejecutando modelo... Por favor espere.\n\n✓ Directorio DatosProyecto creado con {dzn_filename}\n\n"
                    self.results_output.setText(initial_message)
                    # Mover el cursor al final para que la salida de MiniZinc se agregue después
                    cursor = self.results_output.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    self.results_output.setTextCursor(cursor)
                    
                except Exception as e:
                    self.results_output.setText(f"❌ Error al crear directorio DatosProyecto:\n{str(e)}")
                    self._set_ui_during_execution(False)
                    self.execute_button.setEnabled(True)
                    return

                self.thread = QThread()
                self.worker = MinizincWorker(dzn_path=datos_proyecto_path, model_path=model_path)
                self.worker.moveToThread(self.thread)

                self.thread.started.connect(self.worker.run)
                self.worker.outputReady.connect(self._update_output)
                self.worker.finished.connect(self._on_minizinc_finished)
                self.worker.errorOccurred.connect(lambda err: self.results_output.append(f"🔴 ERROR: {err}\n"))

                self.worker.finished.connect(self.thread.quit)
                self.worker.finished.connect(self.worker.deleteLater)
                self.thread.finished.connect(self.thread.deleteLater)

                self.thread.start()
                
            except Exception as e:
                self.results_output.setText(f"❌ Error al ejecutar:\n{str(e)}")
                self._set_ui_during_execution(False)
                self.execute_button.setEnabled(True)
        else:
            self.results_output.setText("❌ Error: No hay archivo DZN válido.")
            self.execute_button.setEnabled(True)

    def _on_minizinc_finished(self, output, success):
        self.stop_button.setVisible(False)
        self.execute_button.setEnabled(True)
        
        try:
            if hasattr(self, 'worker'):
                del self.worker
            
            self.last_output = output
            self.results_output.append("\n" + "="*60 + "\n")
            self.results_output.append("Ejecución Finalizada\n")
            self.results_output.append("="*60 + "\n\n")
            
            if success:
                try:
                    pol_str, q_final, x_matrices = parse_minizinc_output(output)
                    self.last_x_matrices = x_matrices
                    self.last_polarizacion = pol_str

                    if pol_str == "0" and q_final == []:
                        result_text = "⚠️ ADVERTENCIA: Parser no extrajo resultados correctamente.\n"
                        result_text += "Revisa la salida completa arriba.\n"
                    else:
                        result_text = "ÉXITO!\n\n"
                        result_text += f"🎯 Polarización mínima: {pol_str}\n\n"
                        result_text += f"📊 Distribución final: {q_final}\n\n"
                        
                        # Guardar solución en archivo .txt con el formato requerido
                        try:
                            solucion_filename = self._guardar_solucion_txt(pol_str, x_matrices)
                            result_text += f"💾 Solución guardada en {solucion_filename}\n\n"
                        except Exception as e:
                            result_text += f"⚠️ Error al guardar solución: {str(e)}\n\n"
                        
                        result_text += "💡 Presiona 'Revisar Resultados' para verificar la solución.\n"
                    
                    self.results_output.append(result_text)
                    self.check_button.setEnabled(True)

                except Exception as e:
                    self.results_output.append(f"❌ ERROR al parsear:\n{str(e)}\n")
                    self.check_button.setEnabled(False)
            else:
                self.results_output.append("❌ EJECUCIÓN FALLIDA\n")
                self.results_output.append("Verifica que MiniZinc y los solvers estén correctamente instalados.\n")
                self.check_button.setEnabled(False)

        finally:
            self._set_ui_during_execution(False)
            
    def _update_output(self, text):
        # Usar append en lugar de insertPlainText para agregar al final
        self.results_output.moveCursor(self.results_output.textCursor().MoveOperation.End)
        self.results_output.insertPlainText(text)
        self.results_output.ensureCursorVisible()
    
    def _set_ui_during_execution(self, executing):
        self.import_txt_button.setEnabled(not executing)
        self.import_dzn_button.setEnabled(not executing)
        self.execute_button.setVisible(not executing)
        self.check_button.setVisible(not executing)
        self.stop_button.setVisible(executing)
    
    def _stop_execution(self):
        if hasattr(self, 'worker'):
            self.worker.interrupt()
        
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        
        self._set_ui_during_execution(False)
        self.results_output.append("\n\n🛑 EJECUCIÓN DETENIDA POR EL USUARIO\n")
        self.execute_button.setEnabled(True)
        self.check_button.setEnabled(False)
    
    def _guardar_solucion_txt(self, polarizacion_str: str, x_matrices: List[List[List[int]]]) -> str:
        """
        Guarda la solución en un archivo .txt con el formato requerido:
        1. Línea 1: polarización final (entero)
        2. Línea 2: nivel de resistencia (1)
        3. Líneas siguientes m: matriz de movimientos para resistencia baja
        4. Línea siguiente: nivel de resistencia (2)
        5. Líneas siguientes m: matriz de movimientos para resistencia media
        6. Línea siguiente: nivel de resistencia (3)
        7. Líneas siguientes m: matriz de movimientos para resistencia alta
        
        Returns:
            str: Nombre del archivo creado
        """
        try:
            # Convertir polarización a entero
            try:
                polarizacion_int = int(float(polarizacion_str))
            except (ValueError, TypeError):
                polarizacion_int = 0
            
            # Determinar el directorio donde guardar (mismo que DatosProyecto)
            model_path = os.path.join(os.path.dirname(__file__), "../Proyecto.mzn")
            proyecto_dir = os.path.join(os.path.dirname(model_path), "DatosProyecto")
            
            # Crear el directorio si no existe
            os.makedirs(proyecto_dir, exist_ok=True)
            
            # Obtener m (número de opiniones) del archivo DZN
            m = 3  # valor por defecto
            if self.current_dzn_path:
                try:
                    params = parse_dzn_input(self.current_dzn_path)
                    m = params.get('m', 3)
                except:
                    pass
            
            # Determinar el nombre del archivo de solución con el número de prueba
            if self.numero_prueba:
                solucion_filename = f"Solucion{self.numero_prueba}.txt"
            else:
                solucion_filename = "Solucion.txt"
            
            # Ruta del archivo de solución
            solucion_path = os.path.join(proyecto_dir, solucion_filename)
            
            # Escribir el archivo con el formato requerido
            with open(solucion_path, 'w') as f:
                # Línea 1: Polarización final (entero)
                f.write(f"{polarizacion_int}\n")
                
                # Para cada nivel de resistencia k = 1, 2, 3
                for k in range(3):  # k = 0, 1, 2 corresponde a resistencia 1, 2, 3
                    nivel_resistencia = k + 1
                    
                    # Línea con el nivel de resistencia
                    f.write(f"{nivel_resistencia}\n")
                    
                    # Obtener la matriz de movimientos para este nivel
                    if k < len(x_matrices) and x_matrices[k] and len(x_matrices[k]) > 0:
                        matriz_k = x_matrices[k]
                        
                        # Escribir las m filas de la matriz
                        for i in range(m):
                            if i < len(matriz_k):
                                fila = matriz_k[i]
                                # Asegurar que la fila tenga m columnas
                                valores = []
                                for j in range(m):
                                    if j < len(fila):
                                        valores.append(str(int(fila[j])))
                                    else:
                                        valores.append("0")
                                f.write(",".join(valores) + "\n")
                            else:
                                # Si falta la fila, escribir ceros
                                f.write(",".join(["0"] * m) + "\n")
                    else:
                        # Si no hay matriz, escribir m filas de ceros
                        for i in range(m):
                            f.write(",".join(["0"] * m) + "\n")
            
            return solucion_filename
            
        except Exception as e:
            raise Exception(f"Error al guardar solución: {str(e)}")
    
    def _revisar_resultados(self):
        if self.last_output and self.last_x_matrices:
            try:
                params = parse_dzn_input(self.current_dzn_path)

                verification_output = verificar_solucion(
                    x=self.last_x_matrices,
                    p=params['p'],
                    s=params['s'],
                    v=params['v'],
                    n=params['n'],
                    m=params['m'],
                    ct_max=params['ct'],
                    maxMovs=params['maxMovs']
                )
                
                self.results_output.clear()
                self.results_output.setText("🔍 VERIFICACIÓN DE RESULTADOS\n\n")
                self.results_output.append(verification_output)
                
                self.execute_button.setEnabled(False)
                self.check_button.setEnabled(False)
                
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error de Verificación", 
                    f"No se pudo verificar los resultados:\n{str(e)}"
                )
        else:
            QMessageBox.warning(
                self, 
                "Advertencia", 
                "No hay resultados disponibles para verificar.\nEjecuta el modelo primero."
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Aplicar fuente moderna en toda la aplicación
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MinPolGUI()
    window.show()
    sys.exit(app.exec())
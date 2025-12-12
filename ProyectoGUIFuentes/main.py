import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QTextEdit,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import QColor, QIcon, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os
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

    def _run_minizinc_command(self, command):
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                shell=True if os.name == 'nt' else False
            )

            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is None:
                    break
                if line:
                    stripped = line.strip()
                    self._last_output_lines.append(stripped)
                    self.outputReady.emit(stripped + "\n")
                if self._is_interrupted:
                    self.process.terminate()
                    break

            self.process.wait()
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
                success = self._run_minizinc_command([
                    "minizinc", "--solver", "gurobi", self.model_path, self.dzn_path
                ])

            if not success and not self._is_interrupted:
                if gurobi_available:
                    self.outputReady.emit("\n⚠️ Gurobi falló, usando Gecode...\n\n")
                else:
                    self.outputReady.emit("🔍 Usando solver Gecode...\n")
                
                success = self._run_minizinc_command([
                    "minizinc", "--solver", "gecode", "--time-limit", "120000", 
                    self.model_path, self.dzn_path
                ])

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
        padding: 20px;
    }

    QLabel#headerTitle {
        font-size: 32px;
        font-weight: 700;
        color: #ffffff;
    }

    QLabel#headerSubtitle {
        font-size: 14px;
        color: #a0a0a0;
        font-weight: 400;
    }

    /* === Tarjetas === */
    QFrame#cardFrame {
        background-color: #242424;
        border-radius: 12px;
        border: 1px solid #333333;
        padding: 5px;
    }

    QLabel#cardTitle {
        font-size: 20px;
        font-weight: 600;
        color: #ffffff;
        padding: 15px 20px;
        background-color: #2a2a2a;
        border-radius: 8px;
        margin: 10px;
    }

    /* === Botones === */
    QPushButton {
        border-radius: 8px;
        padding: 14px 24px;
        font-size: 15px;
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
        self.setGeometry(100, 100, 1400, 850)
        self.setStyleSheet(DARK_MODE_STYLESHEET)
        
        self.current_file_path = None
        self.current_dzn_path = None
        self.last_output = None
        self.last_x_matrices = None
        self.tree_mode = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)

        # Header
        self.header = self._crear_header()
        main_layout.addWidget(self.header)
        
        # Contenido principal
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(25)

        left_column = QVBoxLayout()
        left_column.setSpacing(20)

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
        header_layout.setContentsMargins(25, 20, 25, 20)
        header_layout.setSpacing(8)

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
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 10)

        title = QLabel("Entrada de Datos")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        self.entry_buttons_container = QWidget()
        entry_layout = QVBoxLayout(self.entry_buttons_container)
        entry_layout.setContentsMargins(20, 15, 20, 15)
        entry_layout.setSpacing(12)

        self.import_txt_button = QPushButton("Importar Archivo TXT")
        self.import_txt_button.setObjectName("tertiaryButton")
        self.import_txt_button.setMinimumHeight(50)
        self.import_txt_button.clicked.connect(self._importar_archivo_txt)

        self.import_dzn_button = QPushButton("Importar Archivo DZN")
        self.import_dzn_button.setObjectName("tertiaryButton")
        self.import_dzn_button.setMinimumHeight(50)
        self.import_dzn_button.clicked.connect(self._importar_archivo_dzn)

        self.tree_button = QPushButton("Modo Árbol: Desactivado")
        self.tree_button.setObjectName("tertiaryButton")
        self.tree_button.setMinimumHeight(50)
        self.tree_button.setCheckable(True)
        self.tree_button.clicked.connect(self._toggle_tree_mode)

        entry_layout.addWidget(self.import_txt_button)
        entry_layout.addWidget(self.import_dzn_button)
        entry_layout.addWidget(self.tree_button)

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
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 10)

        title = QLabel("Resultados y Salida")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        
        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        self.results_output.setText("Ejecuta el modelo para ver los resultados aquí...")
        
        layout.addWidget(self.results_output, 1)
        
        return self._apply_shadow(card)
    
    def _crear_tarjeta_acciones(self):
        card = QFrame()
        card.setObjectName("cardFrame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 10)

        title = QLabel("Acciones Principales")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        buttons_container = QWidget()
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(20, 15, 20, 15)
        buttons_layout.setSpacing(12)

        self.execute_button = QPushButton("Ejecutar Modelo")
        self.execute_button.setObjectName("primaryButton")
        self.execute_button.setMinimumHeight(55)
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
    
    def _volver_a_botones(self):
        self.entry_buttons_container.setVisible(True)
        self.ready_container.setVisible(False)
        self.current_file_path = None
        self.current_dzn_path = None
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
            success = self._convertir_txt_a_dzn(file_path)
            
            if success:
                self.ready_text.setText(f"Archivo TXT convertido a: {os.path.basename(self.current_dzn_path)}")
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
        self.execute_button.setEnabled(False)
        self.check_button.setEnabled(False)

    def _convertir_txt_a_dzn(self, txt_file_path):
        try:
            output_dir = os.path.join(os.path.dirname(txt_file_path), "Pruebas-dzn(Ejecutadas)")
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = os.path.splitext(os.path.basename(txt_file_path))[0]
            dzn_file_path = os.path.join(output_dir, f"{base_name}.dzn")
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
                self.results_output.setText("Ejecutando modelo... Por favor espere.\n\n")
                
                model_path = os.path.join(os.path.dirname(__file__), "../Proyecto.mzn")
                
                if not os.path.exists(model_path):
                    self.results_output.setText(f"❌ Error: No se encontró Proyecto.mzn")
                    self._set_ui_during_execution(False)
                    self.execute_button.setEnabled(True)
                    return

                if self.tree_mode:
                    self.results_output.append("Modo Árbol activado. Abriendo Gist...\n")
                    try:
                        fzn_file = os.path.join(os.path.dirname(self.current_dzn_path), "temp_tree.fzn")
                        compile_cmd = [
                            "minizinc", "--solver", "gecode", "--compile",
                            "-o", fzn_file, model_path, self.current_dzn_path
                        ]
                        subprocess.run(compile_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        gist_cmd = ["fzn-gecode", "-mode", "gist", fzn_file]
                        subprocess.Popen(gist_cmd)
                        self.results_output.append("Gist iniciado correctamente.\n")

                    except subprocess.CalledProcessError as e:
                        self.results_output.append(f"❌ Error al generar árbol:\n{e}\n")
                    except FileNotFoundError:
                        self.results_output.append("❌ Error: fzn-gecode no encontrado en PATH.\n")
                    finally:
                        self._set_ui_during_execution(False)
                        self.execute_button.setEnabled(True)
                        return
                else:
                    self.thread = QThread()
                    self.worker = MinizincWorker(dzn_path=self.current_dzn_path, model_path=model_path)
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

                    if pol_str == "0" and q_final == []:
                        result_text = "⚠️ ADVERTENCIA: Parser no extrajo resultados correctamente.\n"
                        result_text += "Revisa la salida completa arriba.\n"
                    else:
                        result_text = "ÉXITO!\n\n"
                        result_text += f"🎯 Polarización mínima: {pol_str}\n\n"
                        result_text += f"📊 Distribución final: {q_final}\n\n"
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
        self.results_output.insertPlainText(text)
        self.results_output.ensureCursorVisible()
    
    def _set_ui_during_execution(self, executing):
        self.import_txt_button.setEnabled(not executing)
        self.import_dzn_button.setEnabled(not executing)
        self.execute_button.setVisible(not executing)
        self.check_button.setVisible(not executing)
        self.stop_button.setVisible(executing)
    
    def _toggle_tree_mode(self):
        self.tree_mode = self.tree_button.isChecked()
        if self.tree_mode:
            self.tree_button.setText("Modo Árbol: Activado")
            QMessageBox.information(
                self, 
                "Modo Árbol Activado", 
                "El árbol de búsqueda se visualizará con Gist.\n\n"
                "Requiere 'fzn-gecode' en el PATH.\n"
                "Se abrirá una ventana separada."
            )
        else:
            self.tree_button.setText("Modo Árbol: Desactivado")
            
        if self.current_dzn_path:
            self.execute_button.setEnabled(True)
            self.check_button.setEnabled(False)
            
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
                self.results_output.setText("🔍 VERIFICACIÓN DE RESULTADOS\n")
                self.results_output.append("="*60 + "\n\n")
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
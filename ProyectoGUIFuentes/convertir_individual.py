"""
GUI simple para convertir archivos TXT individuales a DZN
para el problema de Minimización de Polarización (MinPol)
"""

import os
from tkinter import Tk, Button, Label, filedialog, messagebox
from tkinter import ttk

def convert_txt_to_dzn(txt_file_path, dzn_file_path):
    """Convierte un archivo TXT a DZN para MinPol"""
    try:
        with open(txt_file_path, 'r') as txt_file:
            lines = [line.strip() for line in txt_file.readlines() if line.strip()]
        
        if len(lines) < 7:
            raise ValueError("El archivo no tiene el formato esperado (mínimo 7 líneas)")
        
        # Extraer valores básicos
        n = lines[0]
        m = int(lines[1])
        
        # Procesar arrays
        p = '[' + lines[2].replace(',', ', ') + ']'
        v = '[' + lines[3].replace(',', ', ') + ']'
        
        # Procesar matriz s (resistencias)
        matrix_lines = []
        for i in range(m):
            matrix_lines.append(lines[4 + i])
        
        s_content = ' |\n       '.join(matrix_lines)
        s = f"[| {s_content} |]"
        
        # Extraer parámetros finales
        ct = lines[4 + m]
        maxMovs = lines[5 + m]
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(dzn_file_path), exist_ok=True)
        
        # Escribir archivo DZN
        with open(dzn_file_path, 'w') as dzn_file:
            dzn_file.write(f"n = {n};\n")
            dzn_file.write(f"m = {m};\n\n")
            dzn_file.write(f"p = {p};\n\n")
            dzn_file.write(f"v = {v};\n\n")
            dzn_file.write(f"s = {s};\n\n")
            dzn_file.write(f"ct = {ct};\n\n")
            dzn_file.write(f"maxMovs = {maxMovs};")
        
        return True, "Conversión exitosa"
        
    except Exception as e:
        return False, f"Error al convertir: {str(e)}"


def select_and_convert_file():
    """Abre diálogo para seleccionar y convertir archivo"""
    # Seleccionar archivo TXT
    txt_file_path = filedialog.askopenfilename(
        title="Seleccione un archivo TXT",
        filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
    )
    
    if not txt_file_path:
        return  # Usuario canceló
    
    # Obtener nombre base
    base_name = os.path.splitext(os.path.basename(txt_file_path))[0]
    
    # Definir carpeta de salida
    output_folder = "./Pruebas-dzn(Ejecutadas)"
    dzn_file_path = os.path.join(output_folder, f"{base_name}.dzn")
    
    # Convertir
    success, message = convert_txt_to_dzn(txt_file_path, dzn_file_path)
    
    if success:
        messagebox.showinfo(
            "Éxito", 
            f"Archivo convertido exitosamente!\n\n"
            f"Guardado en:\n{dzn_file_path}"
        )
    else:
        messagebox.showerror("Error", message)


def create_gui():
    """Crea la interfaz gráfica simple"""
    root = Tk()
    root.title("Conversor TXT → DZN - MinPol")
    root.geometry("400x250")
    root.resizable(False, False)
    
    # Configurar estilo
    style = ttk.Style()
    style.theme_use('clam')
    
    # Frame principal
    main_frame = ttk.Frame(root, padding="20")
    main_frame.grid(row=0, column=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
    
    # Título
    title_label = Label(
        main_frame,
        text="Conversor TXT → DZN",
        font=("Arial", 16, "bold"),
        fg="#007BFF"
    )
    title_label.grid(row=0, column=0, pady=(0, 10))
    
    # Subtítulo
    subtitle_label = Label(
        main_frame,
        text="Problema de Minimización de Polarización",
        font=("Arial", 10),
        fg="#666666"
    )
    subtitle_label.grid(row=1, column=0, pady=(0, 20))
    
    # Información
    info_label = Label(
        main_frame,
        text="Seleccione un archivo TXT para convertir\n"
             "al formato DZN de MiniZinc",
        font=("Arial", 9),
        fg="#333333",
        justify="center"
    )
    info_label.grid(row=2, column=0, pady=(0, 20))
    
    # Botón de conversión
    btn_convert = Button(
        main_frame,
        text="📁 Seleccionar y Convertir",
        command=select_and_convert_file,
        font=("Arial", 11, "bold"),
        bg="#007BFF",
        fg="white",
        padx=20,
        pady=12,
        cursor="hand2",
        relief="flat"
    )
    btn_convert.grid(row=3, column=0, pady=(0, 10))
    
    # Info adicional
    output_label = Label(
        main_frame,
        text="📂 Los archivos se guardarán en:\n./Pruebas-dzn(Ejecutadas)/",
        font=("Arial", 8),
        fg="#888888",
        justify="center"
    )
    output_label.grid(row=4, column=0, pady=(10, 0))
    
    # Centrar ventana
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()


if __name__ == "__main__":
    create_gui()
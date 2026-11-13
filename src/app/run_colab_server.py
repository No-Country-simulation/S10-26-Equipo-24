import os
import sys
import time
import subprocess
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()

def start_server():
    # 1. Directorio de trabajo
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../../"))
    os.chdir(project_root)
    print(f"📁 Directorio de trabajo configurado en: {project_root}")

    # 2. Limpieza de procesos anteriores
    print("🧹 Liberando puerto 8000 y matando procesos colgados...")
    subprocess.run(["fuser", "-k", "8000/tcp"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "uvicorn"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "ngrok"], stderr=subprocess.DEVNULL)
    time.sleep(2)

    # 3. Configurar Authtoken
    ngrok_token = os.getenv("NGROK_AUTHTOKEN", "3Ly3jiRSvfQoANiSqJ4DyAz2v6N_3xUgfbMiYy2VnHRNchxQ")
    try:
        ngrok.set_auth_token(ngrok_token)
    except Exception as e:
        if "already set" not in str(e).lower():
            print(f"⚠️ Advertencia token: {e}")

    # 4. Iniciar Uvicorn en segundo plano
    print("⚡ Iniciando servidor Uvicorn en el puerto 8000...")
    uvicorn_process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "src.app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000"
    ])

    time.sleep(2)

    # 5. Abrir el túnel HTTPS público
    try:
        public_url = ngrok.connect(8000)
        print("\n" + "=" * 60)
        print("🚀 API PÚBLICA DE OPENBRIDGE ONLINE EN:")
        print(f"👉 {public_url.public_url}")
        print("\n📄 Documentación Swagger interactiva:")
        print(f"👉 {public_url.public_url}/docs")
        print("=" * 60 + "\n")
        
        # 6. Mantener el proceso activo
        print("🟢 Servidor en ejecución... Presiona Ctrl+C o interrumpe la celda para detener.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Deteniendo servidor y liberando recursos...")
        uvicorn_process.terminate()
        ngrok.kill()
    except Exception as e:
        print(f"❌ Error en el servidor o túnel de ngrok: {e}")
        uvicorn_process.terminate()

if __name__ == "__main__":
    start_server()
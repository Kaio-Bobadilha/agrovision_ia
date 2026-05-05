import os
import cv2
import time
import uuid
import sqlite3
import threading
import numpy as np
import requests
from datetime import datetime
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ultralytics import YOLO

# =========================
# CONFIGURAÇÕES
# =========================
CAMERA_SOURCE = 0
# Se quiser testar com vídeo depois, troque por:
# CAMERA_SOURCE = "teste.mp4"

MODEL_PATH = "yolo11n.pt"
CONFIDENCE_THRESHOLD = 0.45
SAVE_DIR = "static/captures"
DB_PATH = "detections.db"

TARGET_CLASSES = {"person", "car", "motorcycle", "truck", "bus"}

MIN_CONSECUTIVE_FRAMES = 3
ALERT_COOLDOWN_SECONDS = 20

# =========================
# APP
# =========================
app = FastAPI(title="AgroVision AI")

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs(SAVE_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

jinja_env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=0,
)

model = YOLO(MODEL_PATH)

last_frame = None
last_frame_lock = threading.Lock()

detection_state = defaultdict(int)
last_alert_time = defaultdict(lambda: 0.0)

# =========================
# BANCO DE DADOS
# =========================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            event_time TEXT,
            label TEXT,
            confidence REAL,
            image_path TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_event(event_id: str, label: str, confidence: float, image_path: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO events (id, event_time, label, confidence, image_path)
        VALUES (?, ?, ?, ?, ?)
    """, (
        event_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        label,
        confidence,
        image_path
    ))
    conn.commit()
    conn.close()


def list_events(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, event_time, label, confidence, image_path
        FROM events
        ORDER BY event_time DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "event_time": r[1],
            "label": r[2],
            "confidence": r[3],
            "image_path": r[4]
        }
        for r in rows
    ]

# =========================
# FUNÇÕES DE DETECÇÃO
# =========================
def draw_box(frame, x1, y1, x2, y2, label, conf):
    text = f"{label} {conf:.2f}"
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.putText(
        frame,
        text,
        (x1, max(20, y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )


def should_alert(label: str):
    now = time.time()
    return (now - last_alert_time[label]) > ALERT_COOLDOWN_SECONDS


def process_stream():
    global last_frame

    # Try camera first
    cap = cv2.VideoCapture(CAMERA_SOURCE, cv2.CAP_DSHOW)
    use_camera = cap.isOpened()

    if not use_camera:
        cap = cv2.VideoCapture(CAMERA_SOURCE)
        use_camera = cap.isOpened()

    if use_camera:
        print("Câmera iniciada com sucesso.")
    else:
        print("Câmera não disponível. Usando imagens do dataset para simulação.")
        # Fallback to images from dataset
        image_dir = "dataset_agro/images/train"
        if os.path.exists(image_dir):
            image_files = [os.path.join(image_dir, f) for f in os.listdir(image_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
            if image_files:
                print(f"Usando {len(image_files)} imagens para simulação.")
            else:
                print("Nenhuma imagem encontrada no dataset. Thread encerrado.")
                return
        else:
            print("Dataset não encontrado. Thread encerrado.")
            return

    image_index = 0

    while True:
        if use_camera:
            ok, frame = cap.read()
            if not ok:
                print("Falha ao capturar frame da câmera. Tentando novamente.")
                time.sleep(1)
                continue
        else:
            # Load image from dataset
            if image_index >= len(image_files):
                image_index = 0
            frame = cv2.imread(image_files[image_index])
            if frame is None:
                image_index += 1
                continue
            image_index += 1
            time.sleep(0.5)  # Simulate frame rate

        results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

        found_labels_in_frame = set()
        best_conf_by_label = {}

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                label = model.names[cls_id]

                if label not in TARGET_CLASSES:
                    continue

                found_labels_in_frame.add(label)

                if label not in best_conf_by_label or conf > best_conf_by_label[label]:
                    best_conf_by_label[label] = conf

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                draw_box(frame, x1, y1, x2, y2, label, conf)

        for label in TARGET_CLASSES:
            if label in found_labels_in_frame:
                detection_state[label] += 1
            else:
                detection_state[label] = 0

        for label in found_labels_in_frame:
            if detection_state[label] >= MIN_CONSECUTIVE_FRAMES and should_alert(label):
                event_id = str(uuid.uuid4())[:8]
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}_{event_id}.jpg"
                filepath = os.path.join(SAVE_DIR, filename)

                cv2.imwrite(filepath, frame)
                image_path = f"/static/captures/{filename}"

                confidence = best_conf_by_label.get(label, 0.0)
                save_event(event_id, label, confidence, image_path)

                last_alert_time[label] = time.time()
                print(f"[ALERTA] {label} detectado. Evidência salva em {filepath}")

        with last_frame_lock:
            last_frame = frame.copy()

        time.sleep(0.05)

# =========================
# EVENTO DE INICIALIZAÇÃO
# =========================
@app.on_event("startup")
def startup_event():
    init_db()
    # Create default frame
    global last_frame
    placeholder_path = "static/placeholder.jpg"
    if not os.path.exists(placeholder_path):
        # Generate a simple placeholder
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (255, 255, 255)  # White background
        cv2.putText(
            frame,
            "No camera available",
            (50, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            2
        )
        cv2.imwrite(placeholder_path, frame)
    default_frame = cv2.imread(placeholder_path)
    with last_frame_lock:
        if last_frame is None:
            last_frame = default_frame.copy()
    thread = threading.Thread(target=process_stream, daemon=True)
    thread.start()

# =========================
# ROTAS
# =========================
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    events = list_events(20)
    html = jinja_env.get_template("index.html").render(request=request, events=events)
    return HTMLResponse(content=html)


@app.get("/health")
def health():
    return {"status": "ok", "service": "AgroVision AI"}


@app.get("/events")
def get_events():
    return JSONResponse(content=list_events(50))


@app.get("/video_feed")
def video_feed():
    def generate_frames():
        while True:
            with last_frame_lock:
                if last_frame is not None:
                    success, buffer = cv2.imencode('.jpg', last_frame)
                    if success:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.1)  # Adjust frame rate

    return StreamingResponse(generate_frames(), media_type='multipart/x-mixed-replace; boundary=frame')


@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        message = data.get("message", "")
        if not message:
            return JSONResponse(content={"answer": "Por favor, envie uma mensagem."})

        # Get context from last event
        events = list_events(1)
        context = ""
        if events:
            last_event = events[0]
            context = f"Último evento detectado: {last_event['label']} com confiança {last_event['confidence']:.2f} em {last_event['event_time']}."

        prompt = f"Você é um assistente para o sistema AgroVision AI. Contexto: {context}. Responda à pergunta: {message}"

        ollama_response = requests.post("http://localhost:11434/api/generate", json={
            "model": "tinyllama",
            "prompt": prompt,
            "stream": False
        })

        if ollama_response.status_code == 200:
            result = ollama_response.json()
            answer = result.get("response", "Erro ao gerar resposta.")
        else:
            answer = "Erro ao conectar com Ollama."

        return JSONResponse(content={"answer": answer})
    except Exception as e:
        return JSONResponse(content={"answer": f"Erro: {str(e)}"})
async def chat_stream(request: Request):
    try:
        data = await request.json()
        message = data.get("message", "")
        if not message:
            return JSONResponse(content={"error": "Mensagem vazia"})

        # Get context
        events = list_events(1)
        context = ""
        if events:
            last_event = events[0]
            context = f"Último evento detectado: {last_event['label']} com confiança {last_event['confidence']:.2f} em {last_event['event_time']}."

        prompt = f"Você é um assistente para o sistema AgroVision AI. Contexto: {context}. Responda à pergunta: {message}"

        def generate():
            try:
                response = requests.post("http://localhost:11434/api/generate", json={
                    "model": "tinyllama",
                    "prompt": prompt,
                    "stream": True
                }, stream=True)
                for line in response.iter_lines():
                    if line:
                        yield f"data: {line.decode('utf-8')}\n\n"
            except Exception as e:
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


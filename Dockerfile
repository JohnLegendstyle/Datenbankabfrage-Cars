FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py index.html script.js style.css start.sh ./
COPY catalog/characters.json ./catalog/characters.json
CMD ["sh", "start.sh"]

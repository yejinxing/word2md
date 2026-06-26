FROM python:3.11

WORKDIR /app

# LibreOffice — .doc → .docx
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install -e .

EXPOSE 8088

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8088"]

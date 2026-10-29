FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /var/data/uploads
ENV DB_PATH=/var/data/fdr.db UPLOAD_DIR=/var/data/uploads
EXPOSE 8000
CMD ["sh", "-c", "gunicorn --chdir backend app:app --workers 1 --threads 4 --bind 0.0.0.0:${PORT:-8000}"]

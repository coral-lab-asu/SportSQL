FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Set environment variable to force remote database in production
ENV FORCE_REMOTE_DB=true
CMD ["gunicorn", "-b", ":8080", "app:app"]

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# DB lives in a named volume so it survives container rebuilds
RUN mkdir -p /app/instance
RUN mkdir -p /app/uploads

EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:create_app()"]

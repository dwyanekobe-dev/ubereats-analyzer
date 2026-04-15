FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY simple_server.py .
RUN mkdir -p uploads
EXPOSE 8000
CMD ["python", "simple_server.py"]

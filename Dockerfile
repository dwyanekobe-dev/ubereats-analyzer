FROM python:3.12-slim
WORKDIR /app
COPY simple_server.py .
RUN mkdir -p uploads
EXPOSE 8000
CMD ["python", "simple_server.py"]

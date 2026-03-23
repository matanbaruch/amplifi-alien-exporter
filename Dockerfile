FROM python:3.11-slim
WORKDIR /app
COPY amplifi_exporter.py .
EXPOSE 9877
CMD ["python", "amplifi_exporter.py"]

FROM python:3.8-slim
WORKDIR /app
COPY notifier .
RUN pip install -r requirements.txt
CMD ["python", "fog_notifier.py"]
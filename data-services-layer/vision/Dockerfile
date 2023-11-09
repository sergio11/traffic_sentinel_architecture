FROM python:3.8-slim-buster
WORKDIR /app
COPY vision .
COPY common common
RUN pip install -r requirements.txt
EXPOSE 5002
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:app"]
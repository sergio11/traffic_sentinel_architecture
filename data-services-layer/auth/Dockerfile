FROM python:3.8-slim-buster
WORKDIR /app
COPY auth .
COPY common common
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

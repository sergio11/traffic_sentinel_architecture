FROM python:3.8-slim-buster
WORKDIR /app
COPY stream .
COPY common common
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "0", "app:app"]
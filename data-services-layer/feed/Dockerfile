# Use an official Python runtime as a parent image
FROM python:3.8
WORKDIR /app
COPY feed .
COPY common common
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["python", "app.py"]
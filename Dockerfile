FROM python:3.11

RUN mkdir /app
WORKDIR /app
ADD requirements.txt /app/
RUN pip install -r requirements.txt

ADD * /app/

CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8000"]

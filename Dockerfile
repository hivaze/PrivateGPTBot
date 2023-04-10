FROM python:3.11-bullseye

LABEL repository="https://github.com/hivaze/PrivateGPTBot"
LABEL website="https://github.com/hivaze/PrivateGPTBot"

WORKDIR /bot

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY main.py main.py
COPY app/ app/
COPY resources/ resources/

CMD ["python3", "main.py"]

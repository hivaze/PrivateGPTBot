FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

LABEL repository="https://github.com/hivaze/PrivateGPTBot"
LABEL website="https://github.com/hivaze/PrivateGPTBot"

RUN apt-get update && apt-get install -y tzdata

ENV TZ=Europe/Moscow
RUN echo $TZ > /etc/timezone && \
    dpkg-reconfigure -f noninteractive tzdata

WORKDIR /bot

RUN python -m pip install --upgrade pip
#RUN pip3 install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY main.py main.py
COPY start.sh start.sh
COPY app/ app/
COPY resources/ resources/

RUN chmod +x /bot/start.sh

ENTRYPOINT ["/bot/start.sh"]

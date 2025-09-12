# Docker file for TSB-AD usage
FROM python:3.12-slim
LABEL Maintainer="pablo"

RUN pip install --no-cache --extra-index-url https://download.pytorch.org/whl/cpu TSB-AD

VOLUME /vol/FFL
WORKDIR /vol/FFL

CMD [ "/bin/bash" ]

FROM python:3.10-slim

WORKDIR /nodes

COPY . /nodes

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["bash", "/nodes/entrypoint.sh"]
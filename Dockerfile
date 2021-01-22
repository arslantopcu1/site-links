FROM python:3.9-slim
WORKDIR /home/site-link/
ADD . .
ENTRYPOINT [ "python", "main.py" ]
CMD [ "--domain", "https://www.lipsum.com", "--worker", "1" ]
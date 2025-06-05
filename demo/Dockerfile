FROM python:3.12-slim-bookworm as base
WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y curl git && apt-get clean
ENV PDM_VERSION=2.24.0
ENV PDM_HOME=/opt/pdm
RUN curl -sSL https://pdm-project.org/install-pdm.py | python3 -


FROM python:3.12-slim-bookworm
WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y curl git && apt-get clean

COPY --from=base /opt/pdm /opt/pdm

ENV PATH="/opt/pdm/bin:$PATH"

# Setup project
COPY pyproject.toml pdm.lock README.md ./
RUN pdm install -G demo
RUN pdm add "acapy-controller @ git+https://github.com/Indicio-tech/acapy-minimal-example.git@main"
RUN pdm add acapy-controller

COPY ./demo_web_issuance/demo.py ./

ENTRYPOINT ["pdm", "run", "python", "-m", "demo"]

FROM ghcr.io/openwallet-foundation/acapy-agent:py3.12-1.2.2
#FROM acapy-vcdm

RUN mkdir acapy_did_web && touch acapy_did_web/__init__.py
ADD pyproject.toml README.md pdm.lock ./
RUN pip install -e .

ADD acapy_did_indy/ acapy_did_indy/

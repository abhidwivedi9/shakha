# Shakha runs real git against real repositories, so the image needs git itself.
# Nothing else: the server is Python standard library only, and the web UI has no
# build step.
FROM python:3.12-slim

# openssh-client and gnupg are not decoration: the signing scenarios cut real signed
# tags with ssh-keygen, and without them those lessons fail on the deployed site.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git ca-certificates openssh-client gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# git refuses to run without somewhere to put a config, and the sandbox layers its
# own throwaway global config on top of this per scenario.
ENV HOME=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# --multi-user is not optional here: on a public URL every browser must get its own
# sandboxes, or strangers commit into each other's repositories.
CMD ["sh", "-c", "python shakhactl.py dashboard --host 0.0.0.0 --port ${PORT} --multi-user --no-open"]

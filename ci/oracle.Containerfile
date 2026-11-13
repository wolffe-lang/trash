FROM docker.io/library/ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
ARG BUILD_CPUS=0
ENV DEBIAN_FRONTEND=noninteractive
COPY ci/apt-snapshot ci/packages.txt ci/build-requirements.txt ci/oracle-sdist.txt ci/oracle-requirements.txt ci/oracle-wheel.txt ci/snapshot-update.sh ci/snapshot-install.sh /pins/
ADD --checksum=sha256:f9fbacd417b515450b831032cc39d18059e9874e67525679a43c16071dabf9a0 https://snapshot.ubuntu.com/ubuntu/20261107T000000Z/pool/main/c/ca-certificates/ca-certificates_20260816ubuntu0.24.04.2_all.deb /pins/bootstrap-ca.deb
RUN taskset -c "$BUILD_CPUS" sh -ec ' \
  for read in 1 2; do printf "%s  %s\n" f9fbacd417b515450b831032cc39d18059e9874e67525679a43c16071dabf9a0 /pins/bootstrap-ca.deb | sha256sum -c -; done; \
  dpkg-deb -x /pins/bootstrap-ca.deb /pins/bootstrap-ca; \
  mkdir -p /etc/ssl/certs; \
  find /pins/bootstrap-ca/usr/share/ca-certificates -name "*.crt" -type f -exec cat {} + > /etc/ssl/certs/ca-certificates.crt; \
  test -s /etc/ssl/certs/ca-certificates.crt; \
  sh /pins/snapshot-update.sh "$(cat /pins/apt-snapshot)"; \
  sed "/^#/d; /^$/d" /pins/packages.txt | xargs sh /pins/snapshot-install.sh "$(cat /pins/apt-snapshot)"; \
  dpkg-query -W | tr "\t" "=" | sort > /opt/oracle-packages.txt; \
  python3 -m venv /opt/build; \
  /opt/build/bin/pip install --no-cache-dir --require-hashes --only-binary :all: -r /pins/build-requirements.txt; \
  SOURCE_DATE_EPOCH=1700000000 /opt/build/bin/pip wheel --no-cache-dir --no-deps --no-build-isolation --no-binary :all: \
    --require-hashes -r /pins/oracle-sdist.txt -w /opt/wheels; \
  python3 -m venv /opt/trash-cli; \
  /opt/trash-cli/bin/pip install --no-cache-dir --require-hashes --only-binary :all: -r /pins/oracle-requirements.txt; \
  /opt/trash-cli/bin/pip install --no-cache-dir --no-deps --no-index --find-links /opt/wheels --require-hashes -r /pins/oracle-wheel.txt; \
  rm -rf /opt/build /var/lib/apt/lists/*; \
  { cd /opt/wheels; sha256sum *.whl; printf "version %s\n" "$(/opt/trash-cli/bin/trash-put --version)"; \
    /opt/trash-cli/bin/python3 -m pip freeze --all | sort; } > /opt/oracle-manifest.txt'
WORKDIR /work

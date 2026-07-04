FROM busybox:1.36
RUN printf '#!/bin/sh\nexit 0\n' > /usr/local/bin/alembic && chmod +x /usr/local/bin/alembic


FROM golang@sha256:bbbb AS build
RUN go build ./...

FROM alpine@sha256:aaaa AS runtime
USER app

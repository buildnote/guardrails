# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 golang:1.22 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go build \
      -o /out/widget \
      ./cmd/widget

FROM gcr.io/distroless/static-debian12@%s AS runtime
COPY --from=build /out/widget /usr/local/bin/widget
EXPOSE 8080 9090/udp
USER 10001
HEALTHCHECK --interval=30s CMD ["/usr/local/bin/widget", "healthcheck"]
ENTRYPOINT ["/usr/local/bin/widget"]

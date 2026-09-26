
FROM golang:1.22@%s AS build
RUN go build -o /widget .

FROM scratch
COPY --from=build /widget /widget

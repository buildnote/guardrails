FROM gradle:8.14-jdk21 AS build
WORKDIR /home/gradle/widget
COPY settings.gradle.kts build.gradle.kts ./
COPY service ./service
RUN gradle --no-daemon --quiet :service:installDist

FROM eclipse-temurin:21.0.3_9-jre-alpine@sha256:4f2b3c1e9a0d5c7b8e6f1a2d3c4b5a69788899aabbccddeeff00112233445566 AS runtime
ARG WIDGET_VERSION=1.1.0
ENV WIDGET_PORT=8080 JAVA_TOOL_OPTIONS=-XX:MaxRAMPercentage=75
RUN addgroup -S widget && adduser -S widget -G widget
WORKDIR /opt/widget
COPY --from=build /home/gradle/widget/service/build/install/service ./
EXPOSE 8080/tcp
USER widget
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:8080/health || exit 1
ENTRYPOINT ["/opt/widget/bin/service"]

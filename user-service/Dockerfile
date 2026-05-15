FROM eclipse-temurin:17-jdk-alpine AS builder
WORKDIR /app

# Instala Gradle 8.5 diretamente — evita dependência do wrapper.jar
RUN apk add --no-cache wget unzip && \
    wget -q https://services.gradle.org/distributions/gradle-8.5-bin.zip -O /tmp/gradle.zip && \
    unzip -q /tmp/gradle.zip -d /opt && \
    rm /tmp/gradle.zip
ENV PATH="/opt/gradle-8.5/bin:$PATH"

COPY build.gradle.kts settings.gradle.kts ./
RUN gradle dependencies --no-daemon 2>/dev/null || true
COPY src ./src
RUN gradle bootJar --no-daemon -x test

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
RUN addgroup -S gymvision && adduser -S gymvision -G gymvision
COPY --from=builder /app/build/libs/*.jar app.jar
USER gymvision
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD wget -q --spider http://localhost:8081/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "-Dspring.profiles.active=docker", "app.jar"]

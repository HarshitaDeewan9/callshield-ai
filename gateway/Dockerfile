FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY gateway/pom.xml ./pom.xml
COPY gateway/src ./src
RUN mvn -B -DskipTests package
FROM eclipse-temurin:21-jre
RUN useradd --create-home --uid 10002 callshield
WORKDIR /service
COPY --from=build /build/target/gateway-1.0.0.jar app.jar
USER callshield
ENV BIND_ADDRESS=127.0.0.1
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=70", "-jar", "app.jar"]

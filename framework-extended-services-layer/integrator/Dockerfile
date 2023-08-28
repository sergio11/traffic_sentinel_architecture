# Use the official Maven image to build the application
FROM maven:3.8.4-openjdk-17 AS build

# Set the working directory
WORKDIR /app

# Copy the POM file and download dependencies
COPY pom.xml .
RUN mvn clean install -DskipTests

# Copy the source code
COPY src ./src

# Build the application
RUN mvn package

# Use the official OpenJDK image as the base image for the runtime image
FROM openjdk:17-jdk-slim

# Set the working directory
WORKDIR /app

# Copy the compiled JAR from the build stage
COPY --from=build /app/target/*.jar /app/app.jar

# Run the Java program
CMD ["java", "-jar", "app.jar"]
FROM ubuntu:24.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Java JRE (OpenJDK 25), curl, unzip, and ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-25-jre-headless \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory for extracted contents
WORKDIR /app

# Download and extract Interactive Brokers Client Portal Gateway
RUN curl -sSL https://download2.interactivebrokers.com/portal/clientportal.gw.zip -o clientportal.gw.zip \
    && unzip clientportal.gw.zip \
    && rm clientportal.gw.zip \
    && chmod +x bin/run.sh

# Expose port 5000
EXPOSE 5000

# Copy default configuration
COPY conf.yaml root/conf.yaml

# Set entrypoint to execute bin/run.sh with root/conf.yaml
ENTRYPOINT ["bin/run.sh", "root/conf.yaml"]
# Use an official Python image as the base
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current project files into the container
COPY . .

# Install dependencies (Make sure your requirements.txt includes pika)
RUN pip install --no-cache-dir -r requirements.txt


# Define the command to run the consumer (entry point)
CMD ["python", "utils/rabbitMQ_consumer.py"]

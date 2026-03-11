# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (git is needed if automating git pushes from the container)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run app.py using uvicorn when the container launches
# (Alternatively, you can run `python app.py` since it uses uvicorn.run internally)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

# Terrifix Mesh — Local AI Serving Stack

## 1. Project Overview

This project is a simplified local AI serving stack built for the Terrifix AI Platform Engineering take-home assignment.

The goal is to run a language model locally and make it accessible through a secure API gateway, rather than allowing users to communicate with the model server directly.

The application supports:

- Local AI inference using vLLM
- An OpenAI-compatible API
- API key authentication
- Streaming and non-streaming chat responses
- A browser-based chat interface
- Containerised deployment using Docker Compose

The entire inference process runs locally. No hosted AI model API is used.

### Technologies Used

| Technology            | Purpose                                                      |
| --------------------- | ------------------------------------------------------------ |
| Docker                | Packages applications and their dependencies into containers |
| Docker Compose        | Starts and connects multiple containers                      |
| vLLM                  | Runs the language model and generates responses              |
| Qwen2.5-0.5B-Instruct | Small language model suitable for CPU testing                |
| FastAPI               | Provides the API gateway                                     |
| HTTPX                 | Allows FastAPI to communicate with vLLM                      |
| HTML, CSS, JavaScript | Provides the browser chat interface                          |

The project uses the model alias `mesh-small`, which represents `Qwen/Qwen2.5-0.5B-Instruct`.

## 2. System Architecture

The application consists of three main parts:

1. **Frontend:** The browser interface where users enter an API key and send messages.
2. **Gateway:** A FastAPI application that authenticates requests and forwards them to vLLM.
3. **Inference server:** A vLLM container that runs the language model and generates responses.

### Request Flow

```text
User / Browser
      |
      | HTTP request + API key
      v
FastAPI Gateway (port 8080)
      |
      | Validate API key
      |
      | Forward request
      | Internal Docker network
      v
vLLM Server (port 8000 internally)
      |
      | Generate response
      v
FastAPI Gateway
      |
      | Return JSON or stream tokens
      v
User / Browser
```

### Why use a gateway?

The gateway acts as the entry point to the system.

Instead of exposing vLLM directly, users must send requests through FastAPI.

This allows the application to check API keys, handle errors, and control access to the inference server.

**Only port 8080 is published to the host, bound to localhost.** The vLLM service has no published host port.

Both containers communicate through a private Docker network using the internal address `http://vllm:8000`.

This is an important security boundary: clients cannot bypass gateway authentication through the published application interface.

## 3. Project Structure

```text
tfma/
├── compose.yaml
├── .env.example
├── .gitignore
├── README.md
├── gateway/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    └── index.html
```

**File explanations:**

- `compose.yaml`: Defines the containers, networking, storage, and startup configuration.
- `.env.example`: Shows the environment variables required to run the project.
- `.gitignore`: Excludes local secrets and temporary files from Git.
- `gateway/main.py`: Contains authentication, health checks, request forwarding, and streaming logic.
- `gateway/requirements.txt`: Lists Python dependencies.
- `gateway/Dockerfile`: Defines how to build the FastAPI container.
- `frontend/index.html`: Contains the chat interface and browser-side streaming code.

The actual `.env` file is not included in the repository because it contains a local API key.

## 4. Requirements

To run the application, you need:

- Docker Desktop with Docker Compose support
- A working Docker engine
- Enough available memory to load the language model
- Internet access for the initial Docker image and model downloads

This project was developed and tested on Windows 11 using an AMD Ryzen 7 8845HS CPU, 16 GB RAM, and no dedicated GPU.

Inference runs on the CPU, so responses may be slower than those from GPU-based systems.

## 5. Installation and Setup

### Step 1 — Get the project

Clone the repository or download the project folder.

Open PowerShell or a terminal inside the `tfma` directory.

### Step 2 — Configure the API key

Create a `.env` file in the main project directory.

You can copy `.env.example` and replace its placeholder value.

Example:

```dotenv
API_KEY=replace-with-your-own-key
```

Choose your own non-empty API key. This is the key the gateway will require when clients make requests.

For this local demonstration, the key is configured through an environment variable.

### Step 3 — Create the model cache volume

Run:

```powershell
docker volume create mesh-model-cache
```

This creates persistent storage for the model weights.

**Why is this necessary?**

The model needs to be downloaded before it can run.

Without persistent storage, removing the container could mean downloading the model again.

The Docker volume keeps the model files even if the vLLM container is recreated.

### Step 4 — Start the application

Run:

```powershell
docker compose up --build -d
```

Docker Compose will:

1. Build the FastAPI gateway image.
2. Start the vLLM container.
3. Download the model if it is not already cached.
4. Wait for vLLM to become healthy.
5. Start the gateway container.

The first startup can take several minutes, especially on a CPU.

### Step 5 — Check container status

Run:

```powershell
docker compose ps
```

The expected result is:

- `vllm`: Running and healthy
- `gateway`: Running

The vLLM health check queries `/v1/models`, rather than merely checking whether the port is open. This helps ensure that the model server is ready before the gateway starts.

### Step 6 — Open the chat interface

Open:

http://localhost:8080

Enter the API key from your `.env` file and type a message.

The model should generate a response directly in the browser.

## 6. API Endpoints

The gateway provides the following endpoints:

| Endpoint               | Method | Description              | API key required |
| ---------------------- | ------ | ------------------------ | ---------------- |
| `/`                    | GET    | Opens the chat interface | No               |
| `/health`              | GET    | Checks gateway health    | No               |
| `/v1/models`           | GET    | Returns available models | Yes              |
| `/v1/chat/completions` | POST   | Generates chat responses | Yes              |

### Example: Check gateway health

```powershell
Invoke-RestMethod http://localhost:8080/health
```

Expected response:

```json
{"status":"healthy"}
```

This checks the gateway itself, not the health of the entire inference stack.

### Example: List available models

```powershell
$headers = @{
    Authorization = "Bearer YOUR_API_KEY"
}

Invoke-RestMethod `
    -Uri "http://localhost:8080/v1/models" `
    -Headers $headers
```

Replace `YOUR_API_KEY` with the value configured in `.env`.

The response should contain the model alias `mesh-small`.

### Example: Generate a chat response

```powershell
$body = @{
    model = "mesh-small"
    messages = @(
        @{
            role = "user"
            content = "Explain Docker in two sentences."
        }
    )
    max_tokens = 100
} | ConvertTo-Json -Depth 5

$response = Invoke-RestMethod `
    -Uri "http://localhost:8080/v1/chat/completions" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body

$response.choices[0].message.content
```

The model's answer should appear in PowerShell.

## 7. Streaming Responses

The application supports two response modes.

**Non-streaming (`stream: false`):** The client waits until the model finishes generating the entire response. The gateway then returns the completed JSON response.

**Streaming (`stream: true`):** The model sends response chunks as they become available. The gateway forwards these chunks to the client without waiting for the complete answer.

Streaming uses Server-Sent Events (SSE).

A simplified example looks like:

```text
data: {"choices":[{"delta":{"content":"Hello"}}]}

data: {"choices":[{"delta":{"content":" there"}}]}

data: [DONE]
```

The `[DONE]` marker indicates the end of a completed stream.

The browser uses JavaScript's `fetch()` and `ReadableStream` functionality to process incoming events and update the displayed response progressively.

This provides a better user experience because users can see text appearing while the model is still generating it.

## 8. Gateway Design Decisions

### Proxying rather than fully rewriting the API

The gateway uses a proxy-style approach.

It accepts OpenAI-compatible requests, forwards their JSON payloads to vLLM, and returns the corresponding responses.

The gateway handles authentication and transport, while vLLM handles model inference.

**Why choose this approach?**

It keeps the gateway relatively small and avoids unnecessarily rebuilding functionality already provided by vLLM.

**Trade-off:** The gateway depends on the upstream API format and does not fully validate every possible OpenAI request field. A production gateway might use stricter schemas, request validation, and explicit model routing.

### Authentication

The gateway expects an HTTP authorization header:

```text
Authorization: Bearer YOUR_API_KEY
```

The key is read from an environment variable.

If the key is missing or incorrect, the gateway returns HTTP 401 with an OpenAI-shaped JSON error.

The client's authorization header is not forwarded to vLLM.

In this demonstration, vLLM does not use a separate upstream API credential. The gateway accesses it through the private Docker network.

### Security limitations

This authentication mechanism is suitable for a local demonstration, but not a production deployment.

Limitations include:

- A single shared static API key
- No user accounts or per-user permissions
- No key expiration or automatic rotation
- No rate limiting or usage quotas
- No HTTPS termination in the application
- No persistent audit logging

The browser holds the entered key in memory while the page is open.

For production, the first major improvement would be replacing the shared key with centrally managed, per-client credentials, including revocation and rotation.

Additional improvements would include HTTPS, rate limiting, monitoring, and stronger network restrictions.

## 9. Reliability and Failure Handling

### Incorrect API key

**Expected behaviour:** The gateway returns HTTP 401 with a structured JSON error.

This was tested successfully through the browser interface.

### Inference server unavailable

If vLLM is stopped, the gateway cannot forward inference requests.

**Expected behaviour:** The gateway returns HTTP 502 with an error indicating that the inference server is unavailable.

This was tested by stopping the vLLM container while leaving the gateway running.

After restarting vLLM and allowing the model to load, inference worked again.

### Startup readiness

vLLM can take time to load its model weights.

Docker Compose uses a health check and `depends_on` with `condition: service_healthy` to delay gateway startup until the model server responds to its readiness check.

This avoids relying only on the container being started or its port being open.

### Interrupted streaming

If the inference server disconnects after a stream has started, the gateway cannot change the already-sent HTTP status code to 502.

The current implementation does not provide complete recovery from a mid-stream failure. The browser's handling of an incomplete stream is also a known limitation.

A production implementation should detect missing stream completion, report interrupted responses, and handle cancellation and cleanup consistently.

## 10. Known Limitations

This project intentionally prioritises correct service boundaries and basic functionality over production-scale performance.

**Concurrency:** The vLLM server is configured with `--max-num-seqs 1`, limiting concurrent sequence processing. Multiple simultaneous requests may experience delays or resource contention.

**Context length:** The model is configured with `--max-model-len 2048`. Long conversations may exceed this limit and be rejected. The frontend does not currently truncate conversation history.

**CPU performance:** Running inference without a dedicated GPU is slower and limits practical throughput.

**Streaming failures:** A stream interrupted halfway through generation may leave the client with an incomplete response.

**Availability:** There is only one inference server and one gateway instance. There is no automatic failover.

**Compatibility:** The gateway implements the endpoints required for this exercise, not the entire OpenAI API.

**Offline operation:** Once the Docker images and model weights have been downloaded and cached, inference does not require a hosted model API. A fresh machine still needs the necessary images and model weights before it can operate offline.

## 11. What I Would Improve With Another Week

Given more development time, I would prioritise:

1. **Better authentication:** Per-client API keys, key rotation, and revocation.
2. **Request limits:** Rate limiting, timeouts, and concurrency controls to protect the model server.
3. **Streaming reliability:** Better handling of disconnected clients, cancelled requests, and incomplete SSE streams.
4. **Observability:** Structured logs, request metrics, inference latency, and health monitoring.
5. **Automated tests:** Integration tests for authentication, successful inference, upstream errors, and streaming.
6. **Model flexibility:** Configurable model aliases and support for additional models.

The main priority would be making the system safer and more reliable before attempting to scale it.

## 12. Stopping and Restarting the Application

To stop the containers:

```powershell
docker compose stop
```

To restart stopped containers:

```powershell
docker compose start
```

To stop and remove the containers and Compose network:

```powershell
docker compose down
```

To start everything again:

```powershell
docker compose up --build -d
```

The model cache is stored in a separate Docker volume and is not removed by the normal `docker compose down` command.

## 13. AI Assistance Disclosure

I used ChatGPT as a development assistant while working on this project.

AI assistance was used to help understand unfamiliar platform engineering concepts, plan the implementation, draft parts of the Docker and FastAPI configuration, troubleshoot issues, and prepare documentation.

I verified the implementation by running the application locally and testing the actual behaviour of the services.

These tests included:

- Confirming that vLLM could load the model and generate responses
- Checking the gateway health endpoint
- Confirming that missing or incorrect API keys return HTTP 401
- Confirming that valid keys allow model requests
- Testing non-streaming and SSE streaming responses
- Checking that the browser displays generated text
- Stopping vLLM to verify HTTP 502 error handling
- Restarting vLLM and confirming that inference works again

The project was developed as a learning exercise, with particular attention to understanding the purpose of each component and the boundaries between them.

---

## Summary

This project demonstrates a small, locally hosted AI serving stack with a FastAPI gateway in front of vLLM.

The main design decision is to keep the inference server private and make the gateway the only published entry point.

Although the implementation is not production-ready, it demonstrates the fundamental concepts of containerisation, authentication, service networking, readiness checks, streaming, and failure handling.

# 🧪 Kubernetes Lab

This repository is my personal Kubernetes home lab. It uses **[kind](https://kind.sigs.k8s.io/)** (Kubernetes in Docker) for fast,
local cluster creation and **[just](https://github.com/casey/just)** for simple command automation.

The goal is to have a clean, repeatable environment to experiment with different cloud-native tools.

## Prerequisites

Before you begin, make sure you have the following tools installed on your system:

* **[Docker](https://docs.docker.com/get-docker/)**: The container runtime used by `kind`.
* **[kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)**: The Kubernetes command-line tool.
* **[kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)**: The tool for running local Kubernetes clusters.
* **[just](https://github.com/casey/just#installation)**: A handy command runner.

## 🚀 Quickstart

1.  **Clone the repository:**
    ```bash
    git clone http://github.com/1995parham-learning/k8s-lab
    cd k8s-lab
    ```

2.  **Set up the cluster:**
    This single command will create a `kind` cluster and install the NGINX Ingress controller.
    ```bash
    just setup
    ```

3.  **Verify the setup:**
    This command deploys a sample application and tests that the Ingress is working correctly.
    ```bash
    just test
    ```

## 📂 Directory Structure

```
├── experiments/
│   └── nginx-ingress/
│       └── justfile      # <-- Self-contained logic for this tool
│   └── prometheus/       # <-- Future experiment
│       └── justfile
├── justfile              # <-- Root justfile for managing cluster and delegating
├── kind-config.yaml
└── README.md
```

## 🛠️ Experiments

This section documents the available tools. To add a new tool, simply create a new folder in this directory with its own `justfile` containing `install` and `remove` recipes.

### `nginx-ingress`

* **Purpose:** Manages external access to services in the cluster via HTTP/S routing.
* **Install:** `just install nginx-ingress`
* **Remove:** `just remove nginx-ingress`

## 🧹 Cleanup

When you're done, you can completely remove the cluster and all its resources with a single command:

```bash
just delete
```

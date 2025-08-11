cluster_name := "k8s-lab"
config_file := "kind-config.yaml"

# Show available commands
default:
    @echo "🚀 Kube Playground Commands:"
    @just --list

# Create the kind cluster
setup:
    @if ! kind get clusters | grep -q '^{{ cluster_name }}$'; then \
        echo "🚢 Creating kind cluster '{{ cluster_name }}'..."; \
        kind create cluster --name '{{ cluster_name }}' --config '{{ config_file }}'; \
    else \
        echo "✅ Cluster '{{ cluster_name }}' already exists."; \
    fi
    @echo "\n✅ Cluster is ready. Install tools with 'just install <tool_name>'"
    @just install traefik

# Install a tool by calling its own justfile
install tool:
    @if [ -d "experiments/{{ tool }}" ]; then \
        echo "▶️  Delegating to 'experiments/{{ tool }}/justfile'..."; \
        just experiments/{{ tool }}/install; \
    else \
        echo "❌ Error: Tool '{{ tool }}' not found in 'experiments/' directory."; \
        exit 1; \
    fi

# Remove a tool by calling its own justfile
remove tool:
    @if [ -d "experiments/{{ tool }}" ]; then \
        echo "▶️  Delegating to 'experiments/{{ tool }}/justfile'..."; \
        just experiments/{{ tool }}/tremove; \
    else \
        echo "❌ Error: Tool '{{ tool }}' not found in 'experiments/' directory."; \
        exit 1; \
    fi

# Delete the kind cluster
delete:
    @echo "🔥 Deleting kind cluster '{{ cluster_name }}'..."
    kind delete cluster --name '{{ cluster_name }}'

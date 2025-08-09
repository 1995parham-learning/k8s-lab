cluster_name := "k8s-lab"
config_file := "kind-config.yaml"

# Show available commands
default:
    @echo "🚀 Kube Playground Commands:"
    @echo
    @echo "  just setup                # Create the base kind cluster."
    @echo "  just install <tool>       # Install a tool (e.g., 'just install nginx-ingress')."
    @echo "  just remove <tool>        # Remove a tool (e.g., 'just remove nginx-ingress')."
    @echo "  just delete               # Delete the entire kind cluster."

# Create the kind cluster
setup:
    @if ! kind get clusters | grep -q '^{{ cluster_name }}$'; then \
        echo "🚢 Creating kind cluster '{{ cluster_name }}'..."; \
        kind create cluster --name '{{ cluster_name }}' --config '{{ config_file }}'; \
    else \
        echo "✅ Cluster '{{ cluster_name }}' already exists."; \
    fi
    @echo "\n✅ Cluster is ready. Install tools with 'just install <tool_name>'"
    @just install nginx-ingress

# Install a tool by calling its own justfile
install tool:
    @if [ -d "experiments/{{ tool }}" ]; then \
        echo "▶️  Delegating to 'experiments/{{ tool }}/justfile'..."; \
        just --justfile experiments/{{ tool }}/justfile install; \
    else \
        echo "❌ Error: Tool '{{ tool }}' not found in 'experiments/' directory."; \
        exit 1; \
    fi

# Remove a tool by calling its own justfile
remove tool:
    @if [ -d "experiments/{{ tool }}" ]; then \
        echo "▶️  Delegating to 'experiments/{{ tool }}/justfile'..."; \
        just --justfile experiments/{{ tool }}/justfile remove; \
    else \
        echo "❌ Error: Tool '{{ tool }}' not found in 'experiments/' directory."; \
        exit 1; \
    fi

# Delete the kind cluster
delete:
    @echo "🔥 Deleting kind cluster '{{ cluster_name }}'..."
    kind delete cluster --name '{{ cluster_name }}'

# Kafka Toolset Installation Guide

## 🚨 Error: "kafka-python library not installed"

If you're getting this error when using the Kafka toolsets, you need to install the required dependencies.

## 📦 Required Dependencies

The comprehensive Kafka toolset requires the following Python packages:

```bash
# Core Kafka client
pip install kafka-python>=2.0.0

# Alternative Kafka client (optional)
pip install confluent-kafka>=2.0.0

# Other InfraInsights dependencies
pip install requests>=2.28.0
pip install pydantic>=1.10.0
```

## 🔧 Installation Methods

### Method 1: Install from requirements file
```bash
cd holmes/plugins/toolsets/infrainsights
pip install -r requirements.txt
```

### Method 2: Install individual packages
```bash
pip install kafka-python requests pydantic
```

### Method 3: Install in HolmesGPT environment
If you're running HolmesGPT in a container or virtual environment:

```bash
# For Docker containers
docker exec -it <holmesgpt-container> pip install kafka-python

# For Kubernetes pods
kubectl exec -it <holmesgpt-pod> -- pip install kafka-python

# For virtual environments
source <venv-path>/bin/activate
pip install kafka-python
```

## 🐳 Docker Installation

If you're using Docker, add this to your Dockerfile:

```dockerfile
# Install Kafka dependencies
RUN pip install kafka-python>=2.0.0 requests>=2.28.0 pydantic>=1.10.0
```

## ☸️ Kubernetes Installation

For Kubernetes deployments, you can install dependencies using an init container or by modifying your deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: holmesgpt
spec:
  template:
    spec:
      initContainers:
      - name: install-deps
        image: python:3.9
        command: ['pip', 'install', 'kafka-python>=2.0.0']
        volumeMounts:
        - name: shared-deps
          mountPath: /usr/local/lib/python3.9/site-packages
      containers:
      - name: holmesgpt
        image: your-holmesgpt-image
        volumeMounts:
        - name: shared-deps
          mountPath: /usr/local/lib/python3.9/site-packages
      volumes:
      - name: shared-deps
        emptyDir: {}
```

## 🔍 Verification

After installation, verify that the library is available:

```python
try:
    from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
    print("✅ kafka-python library installed successfully")
except ImportError as e:
    print(f"❌ kafka-python library not found: {e}")
```

## 🧪 Test Commands

Once installed, test the Kafka toolset with:

```
Check the health of my Kafka instance "MT KAFKA"
```

## 🚨 Troubleshooting

### Common Issues:

1. **Permission Denied**: Use `pip install --user kafka-python`
2. **Version Conflicts**: Use `pip install --upgrade kafka-python`
3. **Container Environment**: Ensure you're installing in the correct container
4. **Virtual Environment**: Activate your virtual environment first

### Alternative Kafka Clients:

If `kafka-python` doesn't work, you can try:

```bash
# Confluent Kafka client
pip install confluent-kafka

# Or aiokafka for async support
pip install aiokafka
```

## 📋 Complete Dependencies List

For the full InfraInsights toolset, install:

```bash
pip install -r holmes/plugins/toolsets/infrainsights/requirements.txt
```

This includes:
- `kafka-python>=2.0.0` - Kafka client
- `elasticsearch>=8.0.0` - Elasticsearch client
- `pymongo>=4.0.0` - MongoDB client
- `redis>=4.0.0` - Redis client
- `requests>=2.28.0` - HTTP client
- `pydantic>=1.10.0` - Data validation 